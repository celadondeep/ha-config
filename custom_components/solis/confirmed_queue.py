"""Per-inverter desired state queue; no Home Assistant dependency.

A write is followed by at least 360 seconds and a later successful read.
Pending plans replace older plans instead of accumulating obsolete commands.
"""
from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timedelta
import time
from .confirmed_controls import BY_KEY, MODE_KEYS, SLOT_CIDS, UNUSED_SLOT_CIDS, same, validate, value_for, wire_request

class ConfirmedCommandQueue:
    def __init__(self, interval=360, wall=time.time):
        self.interval = max(360, float(interval))
        self.wall = wall
        self.manual = OrderedDict()
        self.manual_expires = {}
        self.plan = {}
        self.plan_expires = 0.0
        self.active = None
        self.last_sent = 0.0
        self.last_confirmed = None
        self.state = "starting"
        self.error = None
        self.raw = {}
        self.read_at = 0.0
        self.read_attempt_at = 0.0
        self.read_ok = False
        self.export_power_unit_w = 1
        self.last_failure = None
        self.recovery_count = 0
        self.retry_after = {}
        self.failure_counts = {}
        self.mismatch_at = None

    def restore(self, data):
        # Pending desires are deliberately not replayed after a restart.
        self.last_sent = float(data.get("last_sent", 0))
        self.active = data.get("active")
        self.last_confirmed = data.get("last_confirmed")
        self.last_failure = data.get("last_failure")
        self.recovery_count = int(data.get("recovery_count", 0))
        self.retry_after = dict(data.get("retry_after", {}))
        self.failure_counts = dict(data.get("failure_counts", {}))
        # Count two new, spaced readbacks after every process restart.
        self.mismatch_at = None
        self.state = "awaiting_confirmation" if self.active else "starting"

    def persistent(self):
        return {"last_sent": self.last_sent, "active": self.active, "last_confirmed": self.last_confirmed,
                "last_failure": self.last_failure, "recovery_count": self.recovery_count,
                "retry_after": self.retry_after, "failure_counts": self.failure_counts}

    def submit(self, key, value):
        self.manual[key] = self._validate(key, value)
        self.manual_expires[key] = self.wall() + 1800

    def _validate(self, key, value):
        value = validate(key, value)
        if key == "max_export_power" and value % self.export_power_unit_w:
            raise ValueError(f"Export power must use {self.export_power_unit_w} W steps")
        return value

    def set_plan(self, values, now, ttl=180):
        validated = {key: self._validate(key, value) for key, value in values.items()}
        if validated.get("slot1_charge") is True and validated.get("slot1_discharge") is True:
            raise ValueError("Charge and discharge cannot both be enabled")
        if validated.get("inverter_on_off") is False and any(
                validated.get(k) is True for k in ("slot1_charge", "slot1_discharge")):
            raise ValueError("A sleeping inverter cannot have an enabled slot target")
        self.plan = validated
        self.plan_expires = now + ttl

    def cancel_plan(self):
        self.plan = {}
        self.plan_expires = 0

    def desired(self, now):
        for key in list(self.manual):
            if now >= self.manual_expires.get(key, 0):
                self.manual.pop(key, None)
                self.manual_expires.pop(key, None)
        targets = dict(self.plan) if now <= self.plan_expires else {}
        targets.update(self.manual)
        return targets

    def snapshot(self, raw, now):
        if now < self.read_at:
            # Duplicate/rewound timestamps cannot provide another confirmation.
            return
        self.raw = {int(k): str(v) for k, v in raw.items() if v is not None}
        self.read_at = now
        self.read_ok = True
        self.error = None
        if self.active and now >= self.last_sent + self.interval:
            expected = self.active["expected"]
            def confirmed(key, target):
                if key != "inverter_time":
                    return same(key, target, self.raw)
                # A clock advances while the mandatory settling interval elapses.
                try:
                    observed = datetime.strptime(value_for(key, self.raw), "%Y-%m-%d %H:%M:%S")
                    wanted = datetime.strptime(target, "%Y-%m-%d %H:%M:%S")
                    wanted += timedelta(seconds=now - self.last_sent)
                    return abs((observed - wanted).total_seconds()) <= 90
                except (ValueError, TypeError):
                    return False
            raw_expected = self.active.get("expected_raw", {})
            mask = self.active.get("mode_mask")
            # Older persisted mode requests predate mode_mask. Preserve their
            # TOU requirement, but do not claim ownership of unrelated bits.
            if mask is None and self.active.get("cid") == 636:
                from .confirmed_controls import MODE_BITS
                mask = (1 | 4 | 64) if "storage_mode" in expected else 0
                for key, bit in MODE_BITS.items():
                    if key in expected:
                        mask |= 1 << bit
                if int(self.active["value"]) & 2:
                    mask |= 2
            def raw_matches(cid, value):
                if int(cid) == 636 and mask is not None:
                    try:
                        return int(self.raw[636]) & mask == int(value) & mask
                    except (KeyError, ValueError):
                        return False
                return self.raw.get(int(cid)) == str(value)
            complete = all(value_for(k, self.raw) is not None for k in expected) and all(
                int(cid) in self.raw for cid in raw_expected)
            if complete and all(confirmed(k, v) for k, v in expected.items()) and all(
                raw_matches(cid, value) for cid, value in raw_expected.items()):
                self.last_confirmed = {"at": now, "key": self.active["key"], "expected": expected}
                cid = str(self.active["cid"])
                self.retry_after.pop(cid, None)
                self.failure_counts.pop(cid, None)
                for k, v in expected.items():
                    if self.manual.get(k) == v:
                        self.manual.pop(k, None)
                        self.manual_expires.pop(k, None)
                self.active = None
                self.mismatch_at = None
                self.state = "ready"
            elif not complete:
                self.mismatch_at = None
                self.state = "waiting_for_cloud"
                self.error = "Confirmation registers are incomplete"
            else:
                self.state = "not_confirmed"
                self.error = "Command has not been confirmed by a later device read"
                if self.mismatch_at is None:
                    self.mismatch_at = now
                elif now - self.mismatch_at >= 300:
                    # A failed write is terminal after two complete reads, not
                    # a permanent global lock. Reconcile ONLY current desires.
                    cid = str(self.active["cid"])
                    count = self.failure_counts.get(cid, 0) + 1
                    self.failure_counts[cid] = count
                    self.retry_after[cid] = now + min(3600, 900 * 2 ** min(count - 1, 2))
                    self.last_failure = {"at": now, "key": self.active["key"],
                        "expected": expected, "outcome": "not_applied",
                        "retry_after": self.retry_after[cid], "attempt_failures": count}
                    self.active = None
                    self.mismatch_at = None
                    self.recovery_count += 1
                    self.state = "retry_wait"
        elif self.active:
            self.state = "settling"
        else:
            self.state = "ready"

    def read_failed(self, error):
        self.read_ok = False
        self.error = str(error)
        self.state = "waiting_for_cloud"
        self.mismatch_at = None

    def next_request(self, now):
        if self.active:
            self.state = "settling" if now < self.last_sent + self.interval else "not_confirmed"
            return None
        if now < self.last_sent + self.interval:
            self.state = "cooldown"
            return None
        if not self.read_ok or now - self.read_at > 660:
            self.state = "waiting_for_cloud"
            return None
        if self.raw.get(6798) != "43605":
            self.state = "unsupported_profile"
            self.error = "Single-slot controls require TOU V2 (CID 6798 = 43605)"
            return None
        self.desired(now)  # Expire manual targets before comparing them.
        for key in list(self.manual):
            if same(key, self.manual[key], self.raw):
                self.manual.pop(key)
                self.manual_expires.pop(key, None)
        desired = self.desired(now)
        if desired.get("slot1_charge") is True and desired.get("slot1_discharge") is True:
            self.state = "conflicting_targets"
            self.error = "Both charge and discharge targets are enabled"
            return None
        # Unknown power is not interpreted as on/off.
        if value_for("inverter_on_off", self.raw) is None and "inverter_on_off" in desired:
            self.state = "waiting_for_cloud"
            self.error = "Power register readback is incomplete"
            return None
        # No hidden slot may compete with the one exposed to the user.
        if any(key.startswith("slot1_") for key in desired) or "inverter_on_off" in desired:
            if any(self.raw.get(cid) not in ("0", "1") for cid in SLOT_CIDS):
                self.state = "waiting_for_cloud"
                self.error = "Slot switch snapshot is incomplete"
                return None
            for cid in UNUSED_SLOT_CIDS:
                if self.raw[cid] == "1":
                    mask = sum(1 << bit for bit, c in enumerate(SLOT_CIDS) if self.raw[c] == "1")
                    return self._eligible({"key": f"unused_slot_{cid}", "cid": cid, "value": "0", "old_value": str(mask),
                            "expected": {}, "expected_raw": {str(cid): "0"}}, now)
        # Disable an active slot before modifying its parameters or switching off.
        for kind in ("charge", "discharge"):
            key = f"slot1_{kind}"
            changes = any(k.startswith(key+"_") and not same(k, v, self.raw) for k, v in desired.items())
            opposite = "slot1_discharge" if kind == "charge" else "slot1_charge"
            must_stop = (desired.get(key) is False or desired.get("inverter_on_off") is False
                         or desired.get(opposite) is True or changes)
            if must_stop and value_for(key, self.raw) is True:
                return self._prepare(key, False, desired, now)
        # Hidden/undesired slots are stopped before waking the inverter.
        if desired.get("inverter_on_off") is True and not same("inverter_on_off", True, self.raw):
            return self._prepare("inverter_on_off", True, desired, now)
        if desired.get("inverter_on_off") is False:
            if any(value_for(f"slot1_{kind}", self.raw) is not False for kind in ("charge", "discharge")):
                self.state = "waiting_for_cloud"
                return None
            if not same("inverter_on_off", False, self.raw):
                return self._prepare("inverter_on_off", False, desired, now)
            self.state = "idle"
            return None
        if any(desired.get(f"slot1_{kind}") is True for kind in ("charge", "discharge")):
            if value_for("storage_mode", self.raw) is None:
                self.state = "waiting_for_cloud"
                return None
            if not int(self.raw[636]) & 2:
                return self._prepare("storage_mode", desired.get("storage_mode", value_for("storage_mode", self.raw)), desired, now)
        # Scalar settings and mode first, slot enable last.
        keys = [*MODE_KEYS, "allow_export", *[k for k in desired if k not in MODE_KEYS and k not in
                 ("inverter_on_off", "allow_export", "slot1_charge", "slot1_discharge")], "slot1_charge", "slot1_discharge"]
        for key in keys:
            if key == "allow_export" and value_for("storage_mode", self.raw) != "Self-Use":
                continue
            if key in desired and not same(key, desired[key], self.raw):
                return self._prepare(key, desired[key], desired, now)
        self.state = "idle"
        return None

    def _prepare(self, key, target, desired, now):
        if value_for(key, self.raw) is None:
            self.state = "waiting_for_cloud"
            self.error = f"Missing readback for {key}"
            return None
        try:
            request = wire_request(key, target, self.raw, desired)
        except (ValueError, KeyError) as error:
            self.state = "waiting_for_cloud"
            self.error = str(error)
            return None
        self.state = "ready"
        return self._eligible(request, now)

    def _eligible(self, request, now):
        if now < self.retry_after.get(str(request["cid"]), 0):
            self.state = "retry_wait"
            self.error = "Failed command is cooling down; a fresh read and current target are required"
            return None
        return request

    def mark_sent(self, request, now):
        if self.active or now < self.last_sent + self.interval:
            raise RuntimeError("A previous command is still outstanding")
        self.last_sent = now
        self.active = dict(request)
        self.mismatch_at = None
        self.state = "sending"
        self.error = None

    def write_result(self, accepted, error=None):
        self.state = "settling" if accepted else "awaiting_confirmation"
        self.error = error

    def clear(self):
        self.manual.clear()
        self.manual_expires.clear()
        self.cancel_plan()
        self.active = None
        self.mismatch_at = None
        self.state = "cooldown"
        self.error = None
