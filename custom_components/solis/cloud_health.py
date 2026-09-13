"""Shared request limits, circuit recovery and credential-free diagnostics."""
from __future__ import annotations

from collections import Counter, deque
from datetime import datetime, timezone
import time


class CloudDeferred(Exception):
    """No HTTP request was sent; a local request budget is still closed."""

    def __init__(self, seconds):
        self.seconds = max(1.0, float(seconds))
        super().__init__(f"Cloud request deferred for {self.seconds:.0f} seconds")


class CloudHealth:
    READ_ENDPOINTS = {
        "/v1/api/inverterList", "/v1/api/inverterDetail",
        "/v1/api/stationDetail", "/v2/api/atReadBatch", "/v2/api/atRead",
    }
    CONTROL = "/v2/api/control"

    def __init__(self, monotonic=time.monotonic, wall=time.time):
        self.monotonic = monotonic
        self.wall = wall
        self.started = wall()
        self.cooldown_until = 0.0
        self.startup_until = 0.0
        self.completed = {}
        self.events = deque(maxlen=4096)
        self.endpoint_counts = Counter()
        self.endpoint_failures = Counter()
        self.probing_needed = False
        self.requests = self.failures = self.successes = self.deferred = 0
        self.consecutive_failures = 0
        self.last_success = self.last_request = self.last_telemetry = None
        self.last_error = None
        self.in_flight = False

    def hold_startup(self, seconds=300):
        """Prevent a new client from bypassing its predecessor's read budget.

        A full quiet interval after shutdown is conservative across restart
        and wall-clock changes, without trusting restored source timestamps.
        """
        self.startup_until = max(self.startup_until, self.monotonic() + max(300, seconds))

    @staticmethod
    def identity(params):
        return str(params.get("inverterSn") or params.get("sn") or params.get("stationId") or params.get("id") or "account")

    def delay(self, endpoint=None, params=None):
        now = self.monotonic()
        remaining = max(self.cooldown_until, self.startup_until) - now
        if endpoint is not None:
            key = (endpoint, self.identity(params or {}))
            interval = 360 if endpoint == self.CONTROL else (300 if endpoint in self.READ_ENDPOINTS else 1)
            if key in self.completed:
                remaining = max(remaining, self.completed[key] + interval - now)
        return max(0.0, remaining)

    def begin(self, endpoint, params):
        delay = self.delay(endpoint, params)
        if endpoint == self.CONTROL and self.probing_needed:
            delay = max(delay, 300)
        if delay:
            self.deferred += 1
            raise CloudDeferred(delay)
        self.requests += 1
        self.endpoint_counts[endpoint] += 1
        self.last_request = self.wall()
        self.events.append((self.monotonic(), endpoint, self.identity(params)))
        self.in_flight = True

    def finish(self, endpoint, params, success, error=None, *, cancelled=False):
        now = self.monotonic()
        self.completed[(endpoint, self.identity(params))] = now
        self.in_flight = False
        if cancelled:
            return
        if success:
            self.successes += 1
            self.last_success = self.wall()
            self.consecutive_failures = 0
            self.cooldown_until = 0.0
            self.last_error = None
            self.endpoint_failures[(endpoint, self.identity(params))] = 0
            if endpoint in self.READ_ENDPOINTS:
                self.probing_needed = False
        else:
            self.failures += 1
            self.consecutive_failures += 1
            self.endpoint_failures[(endpoint, self.identity(params))] += 1
            self.probing_needed = True
            # One failed probe closes the entire account channel again.
            # No time-setting writes or reload loops are used as keep-alives.
            failures = max(self.consecutive_failures, self.endpoint_failures[(endpoint, self.identity(params))])
            delay = min(1200, 300 * 2 ** min(failures - 1, 2))
            self.cooldown_until = now + delay
            self.last_error = str(error or "request_failed")[:160]

    def write_confirmed(self, serial):
        self.endpoint_failures[(self.CONTROL, str(serial))] = 0

    def telemetry(self, timestamp):
        try:
            value = float(timestamp)
            if value > 1e12:
                value /= 1000
            if 0 < value <= self.wall() + 60:
                self.last_telemetry = value
        except (ValueError, TypeError):
            pass

    def diagnostics(self, serial):
        now = self.monotonic()
        recent = [e for e in self.events if now - e[0] < 3600]
        writes = [e for e in recent if e[1] == self.CONTROL and e[2] == str(serial)]
        writes_5m = sum(now - e[0] < 300 for e in writes)
        age = max(0, self.wall() - self.last_telemetry) if self.last_telemetry else None
        delay = self.delay()
        state = ("write_rate_alert" if writes_5m > 1
                 else "starting" if now < self.startup_until else "backoff" if delay
                 else "starting" if self.last_success is None
                 else "stale_telemetry" if age is None or age > 900
                 else "recovering" if any(self.endpoint_failures.values()) else "healthy")
        def iso(value):
            return datetime.fromtimestamp(value, timezone.utc).isoformat() if value else None
        return {
            "state": state,
            "requests_total": self.requests,
            "successes_total": self.successes,
            "failures_total": self.failures,
            "blocked_requests_total": self.deferred,
            "requests_last_5min": sum(now - e[0] < 300 for e in recent),
            "writes_last_5min": writes_5m,
            "writes_last_hour": len(writes),
            "consecutive_failures": self.consecutive_failures,
            "next_retry": iso(self.wall() + delay) if delay else None,
            "last_success": iso(self.last_success),
            "last_request": iso(self.last_request),
            "last_error": self.last_error,
            "telemetry_age_seconds": round(age) if age is not None else None,
            "request_in_progress": self.in_flight,
            "request_counts": dict(self.endpoint_counts),
            "endpoint_failures": {path: max(count for (p, _), count in self.endpoint_failures.items() if p == path)
                                  for path, _ in self.endpoint_failures},
            "monitor_started": iso(self.started),
            "minimum_read_interval": 300,
            "minimum_write_interval": 360,
            "minimum_startup_quiet_interval": 300,
        }
