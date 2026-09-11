#!/usr/bin/env python3
"""Analyze Eimo SolisCloud request/control failures from Home Assistant logs.

Usage:
  ha core logs | python3 /config/scripts/analyze_eimo_cloud_log.py
  python3 scripts/analyze_eimo_cloud_log.py home-assistant.log

The analyzer correlates every B0072/timeout/read failure with Eimo control CIDs
seen during the preceding 5/15/30 minutes and prints an hourly traffic summary.
"""

from __future__ import annotations

import re
import sys
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

EIMO_SN = "1033300254190112"

CID_NAMES = {
    636: "storage_mode",
    5922: "slot1_discharge_switch",
    5964: "slot1_discharge_time",
    5967: "slot1_discharge_current",
    5965: "slot1_discharge_soc",
    52: "storage_control",
    54: "time_of_use_control",
    56: "device_time",
    6798: "tou_v2_mode",
}

TS_RE = re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?)")
CONTROL_RE = re.compile(
    rf"SolisCloud control SN={EIMO_SN} CID=(?P<cid>\d+) value=(?P<value>\S+)"
)
SKIP_RE = re.compile(
    rf"SolisCloud control skipped .*SN={EIMO_SN} CID=(?P<cid>\d+) value=(?P<value>\S+)"
)
B0072_RE = re.compile(r"B0072|device is offline", re.I)
TIMEOUT_RE = re.compile(r"Timeout accessing .*soliscloud", re.I)
UPDATE_FAIL_RE = re.compile(r"Update of Solis Cloud Control|Error communicating", re.I)
BATCH_SUCCESS_RE = re.compile(r"Finished fetching Solis Cloud Control data .*success: True", re.I)
CONTROL_FINISH_RE = re.compile(r"SolisCloud control request finished in (?P<secs>[0-9.]+)s", re.I)


@dataclass
class ControlEvent:
    ts: datetime
    cid: int
    value: str
    skipped: bool = False


def parse_ts(line: str) -> datetime | None:
    m = TS_RE.search(line)
    if not m:
        return None
    raw = m.group("ts").replace(" ", "T")
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def read_lines() -> list[str]:
    if len(sys.argv) > 1:
        return Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace").splitlines()
    return sys.stdin.read().splitlines()


def label(cid: int) -> str:
    return f"{cid}:{CID_NAMES.get(cid, 'unknown')}"


def main() -> int:
    lines = read_lines()
    controls: list[ControlEvent] = []
    incidents: list[tuple[datetime, str, str]] = []
    hourly = defaultdict(Counter)
    control_latencies: list[float] = []

    for line in lines:
        ts = parse_ts(line)
        if ts is None:
            continue

        hour = ts.replace(minute=0, second=0, microsecond=0)

        m = SKIP_RE.search(line)
        if m:
            cid = int(m.group("cid"))
            value = m.group("value")
            controls.append(ControlEvent(ts, cid, value, True))
            hourly[hour]["control_skipped"] += 1
            hourly[hour][f"skip:{cid}"] += 1
            continue

        m = CONTROL_RE.search(line)
        if m:
            cid = int(m.group("cid"))
            value = m.group("value")
            controls.append(ControlEvent(ts, cid, value, False))
            hourly[hour]["control_sent"] += 1
            hourly[hour][f"cid:{cid}"] += 1

        m = CONTROL_FINISH_RE.search(line)
        if m:
            control_latencies.append(float(m.group("secs")))

        if B0072_RE.search(line):
            incidents.append((ts, "B0072", line.strip()))
            hourly[hour]["B0072"] += 1
        elif TIMEOUT_RE.search(line):
            incidents.append((ts, "timeout", line.strip()))
            hourly[hour]["timeout"] += 1
        elif UPDATE_FAIL_RE.search(line):
            incidents.append((ts, "update_fail", line.strip()))
            hourly[hour]["update_fail"] += 1

        if BATCH_SUCCESS_RE.search(line):
            hourly[hour]["batch_success"] += 1

    print("=== EIMO SOLISCLOUD HOURLY SUMMARY ===")
    if not hourly:
        print("No timestamped SolisCloud events found.")
    for hour in sorted(hourly):
        c = hourly[hour]
        cid_bits = []
        for key, count in sorted(c.items()):
            if key.startswith("cid:"):
                cid = int(key.split(":", 1)[1])
                cid_bits.append(f"{label(cid)}={count}")
        print(
            f"{hour:%Y-%m-%d %H:00}  sent={c['control_sent']:3d} "
            f"skipped={c['control_skipped']:3d} batch_ok={c['batch_success']:3d} "
            f"B0072={c['B0072']:3d} timeout={c['timeout']:3d} "
            f"update_fail={c['update_fail']:3d}"
            + ("  CIDs[" + ", ".join(cid_bits) + "]" if cid_bits else "")
        )

    print("\n=== FAILURE CORRELATION ===")
    if not incidents:
        print("No B0072/timeout/update-failure incidents found.")
    for ts, kind, line in incidents:
        print(f"\n{ts.isoformat(sep=' ')}  {kind}")
        for minutes in (5, 15, 30):
            start = ts - timedelta(minutes=minutes)
            recent = [e for e in controls if start <= e.ts <= ts and not e.skipped]
            counts = Counter(e.cid for e in recent)
            detail = ", ".join(f"{label(cid)}×{n}" for cid, n in counts.most_common()) or "none"
            print(f"  controls previous {minutes:2d} min: {len(recent):2d}  {detail}")
        recent = [e for e in controls if ts - timedelta(minutes=15) <= e.ts <= ts and not e.skipped]
        if recent:
            print("  last controls:")
            for e in recent[-10:]:
                print(f"    {e.ts:%H:%M:%S}  {label(e.cid)}  value={e.value}")
        print(f"  log: {line[:300]}")

    print("\n=== CONTROL LATENCY ===")
    if control_latencies:
        vals = sorted(control_latencies)
        avg = sum(vals) / len(vals)
        p95 = vals[min(len(vals) - 1, int(len(vals) * 0.95))]
        print(f"count={len(vals)} avg={avg:.2f}s p95={p95:.2f}s max={max(vals):.2f}s")
    else:
        print("No paced-control latency records found (expected before new integration is live).")

    print("\n=== KNOWN EIMO SLOT1 CIDS ===")
    for cid in (5922, 5964, 5967, 5965, 636):
        print(f"  {label(cid)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
