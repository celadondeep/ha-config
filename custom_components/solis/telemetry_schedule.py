"""Source-aligned telemetry with one bounded late-data retry per cycle."""
from __future__ import annotations

from collections import deque
from math import floor, isfinite
from statistics import median


class TelemetrySchedule:
    def __init__(self, monotonic, wall):
        self.monotonic = monotonic
        self.wall = wall
        self.period = 300.0
        self.margin = 15.0
        self.intervals = deque(maxlen=6)
        self.source = None
        self.target = None
        self.deadline = 0.0
        self.phase = "initial"
        self.extra_reads = 0
        self.stable = 0

    def delay(self):
        return max(0.0, self.deadline - self.monotonic())

    def started(self):
        if self.phase == "late_retry":
            self.extra_reads += 1

    def _next_normal(self):
        now = self.wall()
        target = (self.source + self.period + self.margin
                  if self.source is not None else now + self.period)
        if target <= now:
            target += (floor((now - target) / self.period) + 1) * self.period
        self.target = target
        self.deadline = self.monotonic() + max(60.0, target - now)
        self.phase = "scheduled"

    def observe(self, timestamp):
        now = self.wall()
        try:
            source = float(timestamp)
            if source > 1e12:
                source /= 1000
            valid = isfinite(source) and 0 < source <= now + 60
        except (ValueError, TypeError):
            valid = False
        if not valid:
            self.failed(300)
            return
        if self.source is None or source > self.source:
            was_extra = self.phase == "late_retry"
            if self.source is not None:
                delta = source - self.source
                normalized = delta / max(1, round(delta / 300))
                # Missing samples do not turn a 5-minute period into 10 minutes.
                # A phase correction (e.g. 246 s) changes the anchor, not cadence.
                if 285 <= normalized <= 315:
                    self.intervals.append(normalized)
                    self.period = median(self.intervals)
            if self.phase == "late_retry":
                self.margin = min(90.0, self.margin + 15.0)
                self.stable = 0
            else:
                self.stable += 1
                if self.stable >= 3:
                    self.margin = max(15.0, self.margin - 5.0)
                    self.stable = 0
            self.source = source
            self._next_normal()
            if not was_extra and source + self.period + self.margin <= now:
                # A newly observed but already one-period-old sample also
                # merits one bounded late-data read, not another full period.
                self.deadline = self.monotonic() + 60
                self.phase = "late_retry"
        elif self.phase != "late_retry":
            self.deadline = self.monotonic() + 60.0
            self.phase = "late_retry"
            self.stable = 0
        else:
            # Still old after the single retry: wait for the next predicted
            # normal cycle, with no immediate or recursive retry sequence.
            self.margin = min(90.0, self.margin + 15.0)
            self._next_normal()

    def failed(self, delay):
        self.deadline = max(self.deadline, self.monotonic() + max(300.0, delay))
        self.phase = "error_wait"
        self.stable = 0
