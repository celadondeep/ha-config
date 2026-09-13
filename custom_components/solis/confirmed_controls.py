"""Single-slot TOU V2 controls. Modified 2026-09-12.

Register semantics checked against Solis' command workbook and
mkuthan/solis-cloud-control. Only the requested controls are exposed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
import re

MODE_OPTIONS = ("Self-Use", "Feed-In Priority", "Off-Grid")
SLOT_CIDS = tuple(range(5916, 5928))
UNUSED_SLOT_CIDS = tuple(c for c in SLOT_CIDS if c not in (5916, 5922))
MODE_BITS = {"battery_reserve": 4, "allow_grid_charging": 5, "grid_peak_shaving": 11}
MODE_KEYS = ("storage_mode", *MODE_BITS)

@dataclass(frozen=True)
class Control:
    key: str
    name: str
    platform: str
    cid: int
    unit: str | None = None
    minimum: float = 0
    maximum: float = 100
    step: float = 1
    icon: str = "mdi:tune"

CONTROLS = (
    Control("inverter_on_off", "Inverter On/Off", "switch", 5161, icon="mdi:power"),
    Control("storage_mode", "Storage Mode", "select", 636, icon="mdi:solar-power"),
    Control("allow_export", "Allow Export", "switch", 6962, icon="mdi:transmission-tower-export"),
    Control("allow_grid_charging", "Allow Grid Charging", "switch", 636),
    Control("battery_reserve", "Battery Reserve", "switch", 636),
    Control("grid_peak_shaving", "Grid Peak Shaving", "switch", 636),
    Control("battery_reserve_soc", "Battery Reserve SOC", "number", 157, "%"),
    Control("battery_over_discharge_soc", "Battery Over Discharge SOC", "number", 158, "%"),
    Control("battery_force_charge_soc", "Battery Force Charge SOC", "number", 160, "%"),
    Control("battery_recovery_soc", "Battery Recovery SOC", "number", 7229, "%"),
    Control("battery_max_charge_soc", "Battery Max Charge SOC", "number", 7963, "%"),
    Control("battery_max_charge_current", "Battery Max Charge Current", "number", 7224, "A", 0, 1000),
    Control("battery_max_discharge_current", "Battery Max Discharge Current", "number", 7226, "A", 0, 1000),
    Control("max_export_power", "Max Export Power", "number", 499, "W", 0, 1000000),
    Control("max_output_power", "Max Output Power", "number", 376, "%"),
    Control("export_calibration", "Export Calibration", "number", 6968, "W", -1000, 1000),
    Control("inverter_time", "Inverter Time", "datetime", 56, icon="mdi:clock"),
    Control("slot1_charge", "Slot1 Charge", "switch", 5916),
    Control("slot1_charge_time", "Slot1 Charge Time", "text", 5946),
    Control("slot1_charge_current", "Slot1 Charge Current", "number", 5948, "A", 0, 1000),
    Control("slot1_charge_soc", "Slot1 Charge SOC", "number", 5928, "%"),
    Control("slot1_discharge", "Slot1 Discharge", "switch", 5922),
    Control("slot1_discharge_time", "Slot1 Discharge Time", "text", 5964),
    Control("slot1_discharge_current", "Slot1 Discharge Current", "number", 5967, "A", 0, 1000),
    Control("slot1_discharge_soc", "Slot1 Discharge SOC", "number", 5965, "%"),
)
BY_KEY = {c.key: c for c in CONTROLS}
# Upstream has two power commands. Detect the newer 5162 through actual
# read support rather than assuming a hexadecimal HMI version threshold.
READ_CIDS = sorted({c.cid for c in CONTROLS if c.cid != 5161} | set(SLOT_CIDS) | {52, 54, 5162, 6798})
TIME_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d-(?:[01]\d|2[0-3]):[0-5]\d$")

def value_for(key, raw):
    """Decode only actual register data, never the requested target."""
    c = BY_KEY[key]
    value = raw.get(c.cid)
    if key == "inverter_on_off":
        a, b = raw.get(52), raw.get(54)
        current = raw.get(5162)
        if current in ("190", "222"):
            return current == "190" if all(v is None or v == current for v in (a, b)) else None
        return (a == "190") if a == b and a in ("190", "222") else None
    if value is None:
        return None
    try:
        if key in MODE_KEYS:
            bits = int(value)
            if key in MODE_BITS:
                return bool(bits & (1 << MODE_BITS[key]))
            # Some older readbacks retain self-use along with off-grid.
            if bits & 4:
                return "Off-Grid"
            if bits & 64:
                return "Feed-In Priority"
            if bits & 1:
                return "Self-Use"
            return None
        if key == "allow_export":
            return {"0": True, "1": False}.get(value)
        if c.platform == "switch":
            return {"0": False, "1": True}.get(value)
        if c.platform == "number":
            number = float(value)
            return number if math.isfinite(number) else None
        return str(value)
    except (ValueError, TypeError):
        return None

def validate(key, value):
    c = BY_KEY[key]
    if c.platform == "switch":
        if type(value) is not bool:
            raise ValueError(f"{key} needs a boolean")
    elif c.platform == "select":
        if value not in MODE_OPTIONS:
            raise ValueError("Unknown storage mode")
    elif c.platform == "number":
        if isinstance(value, bool):
            raise ValueError("Boolean is not a numeric setting")
        value = float(value)
        if not math.isfinite(value) or not c.minimum <= value <= c.maximum or value % c.step:
            raise ValueError(f"{key} is outside its range or step")
    elif c.platform == "text":
        if not isinstance(value, str) or not TIME_PATTERN.fullmatch(value):
            raise ValueError("Use HH:MM-HH:MM (00:00 through 23:59)")
    elif c.platform == "datetime":
        datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    return value

def same(key, expected, raw):
    actual = value_for(key, raw)
    if actual is None:
        return False
    if BY_KEY[key].platform == "number":
        return abs(float(actual) - float(expected)) < 0.01
    return actual == expected

def wire_request(key, target, raw, desired):
    """Calculate masked writes from the most recent confirmed snapshot."""
    c = BY_KEY[key]
    write_cid = c.cid
    old_value = None
    expected = {key: target}
    expected_raw = {}
    if key in MODE_KEYS:
        bits = int(raw[636])
        expected = {k: v for k, v in desired.items() if k in MODE_KEYS}
        expected[key] = target
        if "storage_mode" in expected:
            bits &= ~(1 | 4 | 64)
            bits |= {"Self-Use": 1, "Feed-In Priority": 64, "Off-Grid": 4}[expected["storage_mode"]]
        for name, bit in MODE_BITS.items():
            if name in expected:
                bits = bits | (1 << bit) if expected[name] else bits & ~(1 << bit)
        if desired.get("slot1_charge") is True or desired.get("slot1_discharge") is True:
            bits |= 2
        value = str(bits)
        expected_raw = {"636": value}
    elif key == "inverter_on_off":
        if raw.get(5162) in ("190", "222"):
            write_cid = 5162
        value = "190" if target else "222"
    elif key == "allow_export":
        current = value_for(key, raw)
        if current is None:
            raise ValueError("Export state is unknown")
        old_value = "80" if current else "88"
        value = "0" if target else "1"
    elif c.cid in SLOT_CIDS:
        if any(raw.get(cid) not in ("0", "1") for cid in SLOT_CIDS):
            raise ValueError("Incomplete slot switch snapshot")
        old_value = str(sum((1 << bit) for bit, cid in enumerate(SLOT_CIDS) if raw[cid] == "1"))
        value = "1" if target else "0"
    elif c.platform == "number":
        value = str(int(target))
    else:
        value = str(target)
    return {"key": key, "cid": write_cid, "value": value, "old_value": old_value,
            "expected": expected, "expected_raw": expected_raw}
