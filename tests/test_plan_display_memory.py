"""Recorded switch events and frozen forecast points survive plan recalculation."""
import unittest
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "appdaemon" / "apps"))
from energy_system.horizon_adapter import (
    _observe_night_events, _night_event_view,
    _encode_night_plan_state, _decode_night_plan_state,
)


class NightEventsTests(unittest.TestCase):
    def setUp(self):
        self.tz = ZoneInfo("Europe/Vilnius")
        self.dawn = datetime(2026, 10, 1, 8, tzinfo=self.tz)
        self.memory = {
            "night_plan_date": "2026-10-01", "night_plan_target_soc": 30,
            "evening_target_soc": 60, "night_split_enabled": True,
            "evening_done": False, "discharge_phase": "evening",
            "discharge_deadline": self.dawn.isoformat(),
            "pv_start_at": self.dawn.isoformat(), "discharge_committed": False,
        }

    def record(self, state, at, *, settling=False):
        return {"state": state, "last_changed": at.isoformat(),
                "attributes": {"pending_target": False,
                               "command_status": "settling" if settling else "verified",
                               "last_read": at.isoformat()}}

    def test_split_edges_are_latched_and_idempotent(self):
        eve = self.dawn-timedelta(hours=12)
        evening = {"pv_start_at": self.dawn.isoformat(),
                   "discharge_phase": "evening", "evening_done": False}
        start = _observe_night_events(self.memory, eve, self.record("on", eve),
                                     self.record("on", eve), evening, 130, 30)
        self.assertEqual(start["evening_actual_start_at"], eve.isoformat())
        _observe_night_events(self.memory, eve+timedelta(minutes=7),
                              self.record("on", eve, settling=True),
                              self.record("on", eve), evening, 130, 30)
        self.assertEqual(self.memory["night_events"][0], int(eve.timestamp()//60))
        stopped = eve+timedelta(hours=2)
        end = _observe_night_events(self.memory, stopped, self.record("off", stopped),
                                   self.record("off", stopped), dict(evening, evening_done=True), 130, 30)
        self.assertEqual(end["evening_actual_end_at"], stopped.isoformat())
        self.assertEqual(end["sleep_saved_actual_kwh"], 0)
        sampled = _observe_night_events(self.memory, stopped+timedelta(minutes=10),
                                        self.record("off", stopped), self.record("off", stopped),
                                        dict(evening, evening_done=True), 130, 30)
        self.assertAlmostEqual(sampled["sleep_saved_actual_kwh"], .017, places=3)
        stale = _observe_night_events(self.memory, stopped+timedelta(hours=1),
                                      self.record("off", stopped), self.record("off", stopped),
                                      dict(evening, evening_done=True), 130, 30)
        self.assertAlmostEqual(stale["sleep_saved_actual_kwh"], .033, places=3)
        wake = stopped+timedelta(hours=3)
        resumed = _observe_night_events(self.memory, wake, self.record("off", stopped),
                                        self.record("on", wake), dict(evening, evening_done=True), 130, 30)
        self.assertAlmostEqual(resumed["sleep_saved_actual_kwh"], 0.3)
        morning = dict(evening, discharge_phase="morning", evening_done=True, export_now=True)
        resumed = _observe_night_events(self.memory, wake, self.record("on", wake),
                                        self.record("on", wake), morning, 130, 30)
        self.assertEqual(resumed["morning_actual_start_at"], wake.isoformat())
        raw = _encode_night_plan_state(self.memory, wake.isoformat())
        self.assertIsNotNone(raw)
        self.assertLessEqual(len(raw), 255)
        restored = _decode_night_plan_state(raw)
        self.assertEqual(restored["night_events"], self.memory["night_events"])
        self.assertAlmostEqual(_night_event_view(restored, wake, 130, 30)["sleep_saved_actual_kwh"], 0.3)

        # After the morning export ends, a second observed OFF interval must
        # add to the evening/night saving, not replace it on the next replan.
        second_off = wake + timedelta(hours=1)
        second_on = second_off + timedelta(minutes=30)
        morning_done = dict(morning, export_now=False)
        during = _observe_night_events(restored, second_off + timedelta(minutes=10),
                                       self.record("off", second_off),
                                       self.record("off", second_off), morning_done, 130, 30)
        self.assertAlmostEqual(during["sleep_saved_actual_kwh"], .317, places=3)
        complete = _observe_night_events(restored, second_on,
                                         self.record("off", second_off),
                                         self.record("on", second_on), morning_done, 130, 30)
        self.assertAlmostEqual(complete["sleep_saved_actual_kwh"], .35, places=3)
        state = _encode_night_plan_state(restored, second_on.isoformat())
        self.assertIsNotNone(state)
        self.assertAlmostEqual(_night_event_view(_decode_night_plan_state(state),
                                                 second_on, 130, 30)["sleep_saved_actual_kwh"], .35)


if __name__ == "__main__":
    unittest.main()
