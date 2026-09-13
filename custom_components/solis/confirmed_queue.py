"""Per-inverter desired state queue; no Home Assistant dependency.

A write is followed by at least 360 seconds and a later successful read.
Pending plans replace older plans instead of accumulating obsolete commands.
"""
from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timedelta
from .confirmed_controls import BY_KEY, MODE_KEYS, SLOT_CIDS, UNUSED_SLOT_CIDS, same, validate, value_for, wire_request

class ConfirmedCommandQueue:
    def __init__(self, interval=360):
        self.interval = max(360, float(interval))
        self.manual = OrderedDict()
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

    def restore(self, data):
        # Pending desires are deliberately not replayed after a restart.
        self.last_sent = float(data.get("last_sent", 0))
        self.active = data.get("active")
        self.last_confirmed = data.get("last_confirmed")
        self.state = "awaiting_confirmation" if self.active else "starting"

    def persistent(self):
        return {"last_sent": self.last_sent, "active": self.active, "last_confirmed": self.last_confirmed}

    def submit(self, key, value):
        self.manual[key] = self._validate(key, value)

    def _validate(self, key, value):
        value = validate(key, value)
        if key == "max_export_power" and value % self.export_power_unit_w:
            raise ValueError(f"Export power must use {self.export_power_unit_w} W steps")
        return value

    def set_plan(self, values, now, ttl=180):
        validated = {key: self._validate(key, value) for key, value in values.items()}
        self.plan = validated
        self.plan_expires = now + ttl

    def cancel_plan(self):
        self.plan = {}
        self.plan_expires = 0

    def desired(self, now):
        targets = dict(self.plan) if now <= self.plan_expires else {}
        targets.update(self.manual)
        return targets

    def snapshot(self, raw, now):
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
            if all(confirmed(k, v) for k, v in expected.items()) and all(
                self.raw.get(int(cid)) == str(value) for cid, value in raw_expected.items()
            ):
                self.last_confirmed = {"at": now, "key": self.active["key"], "expected": expected}
                for k, v in expected.items():
                    if self.manual.get(k) == v:
                        self.manual.pop(k, None)
                self.active = None
                self.state = "ready"
            else:
                self.state = "not_confirmed"
                self.error = "Command has not been confirmed by a later device read"
        elif self.active:
            self.state = "settling"
        else:
            self.state = "ready"

    def read_failed(self, error):
        self.read_ok = False
        self.error = str(error)
        self.state = "waiting_for_cloud"

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
        desired = self.desired(now)
        for key in list(self.manual):
            if same(key, self.manual[key], self.raw):
                self.manual.pop(key)
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
                    return {"key": f"unused_slot_{cid}", "cid": cid, "value": "0", "old_value": str(mask),
                            "expected": {}, "expected_raw": {str(cid): "0"}}
        # Disable an active slot before modifying its parameters or switching off.
        for kind in ("charge", "discharge"):
            key = f"slot1_{kind}"
            changes = any(k.startswith(key+"_") and not same(k, v, self.raw) for k, v in desired.items())
            must_stop = desired.get(key) is False or desired.get("inverter_on_off") is False or changes
            if must_stop and value_for(key, self.raw) is True:
                return self._prepare(key, False, desired)
        # Hidden/undesired slots are stopped before waking the inverter.
        if desired.get("inverter_on_off") is True and not same("inverter_on_off", True, self.raw):
            return self._prepare("inverter_on_off", True, desired)
        if desired.get("inverter_on_off") is False:
            if any(value_for(f"slot1_{kind}", self.raw) is not False for kind in ("charge", "discharge")):
                self.state = "waiting_for_cloud"
                return None
            if not same("inverter_on_off", False, self.raw):
                return self._prepare("inverter_on_off", False, desired)
            self.state = "idle"
            return None
        if any(desired.get(f"slot1_{kind}") is True for kind in ("charge", "discharge")):
            if value_for("storage_mode", self.raw) is None:
                self.state = "waiting_for_cloud"
                return None
            if not int(self.raw[636]) & 2:
                return self._prepare("storage_mode", desired.get("storage_mode", value_for("storage_mode", self.raw)), desired)
        # Scalar settings and mode first, slot enable last.
        keys = [*MODE_KEYS, "allow_export", *[k for k in desired if k not in MODE_KEYS and k not in
                 ("inverter_on_off", "allow_export", "slot1_charge", "slot1_discharge")], "slot1_charge", "slot1_discharge"]
        for key in keys:
            if key == "allow_export" and value_for("storage_mode", self.raw) != "Self-Use":
                continue
            if key in desired and not same(key, desired[key], self.raw):
                return self._prepare(key, desired[key], desired)
        self.state = "idle"
        return None

    def _prepare(self, key, target, desired):
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
        return request

    def mark_sent(self, request, now):
        if self.active or now < self.last_sent + self.interval:
            raise RuntimeError("A previous command is still outstanding")
        self.last_sent = now
        self.active = dict(request)
        self.state = "sending"
        self.error = None

    def write_result(self, accepted, error=None):
        self.state = "settling" if accepted else "awaiting_confirmation"
        self.error = error

    def clear(self):
        self.manual.clear()
        self.cancel_plan()
        self.active = None
        self.state = "cooldown"
        self.error = None
