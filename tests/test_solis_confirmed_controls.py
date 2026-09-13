"""Device sequence regressions. Run with python -m unittest discover -s tests."""
import ast
import asyncio
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
import importlib
import logging
from pathlib import Path
import sys
import types
import time
import unittest
from unittest.mock import AsyncMock, Mock

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "solis"
package = types.ModuleType("confirmed_test")
package.__path__ = [str(ROOT)]
sys.modules[package.__name__] = package
controls = importlib.import_module("confirmed_test.confirmed_controls")
Queue = importlib.import_module("confirmed_test.confirmed_queue").ConfirmedCommandQueue
health_module = importlib.import_module("confirmed_test.cloud_health")
Health = health_module.CloudHealth
CloudDeferred = health_module.CloudDeferred


def snapshot(**changes):
    raw = {cid: "0" for cid in controls.SLOT_CIDS}
    raw.update({52: "190", 54: "190", 6798: "43605", 636: "35", 6962: "0",
                5964: "00:00-23:59", 5965: "70", 5967: "150", 5946: "00:00-00:00",
                5948: "150", 5928: "100", 157: "80", 158: "5", 160: "4",
                7229: "6", 7963: "100", 7224: "200", 7226: "220", 499: "10",
                376: "100", 6968: "2", 56: "2026-09-12 00:00:00"})
    raw.update({int(k): str(v) for k, v in changes.items()})
    return raw


class CommandSequences(unittest.TestCase):
    def setUp(self):
        self.now = 10000
        self.q = Queue()
        self.raw = snapshot()
        self.q.snapshot(self.raw, self.now)

    def send(self):
        request = self.q.next_request(self.now)
        self.assertIsNotNone(request)
        self.q.mark_sent(request, self.now)
        return request

    def confirm(self, **changes):
        self.now += 360
        self.raw.update({int(k): str(v) for k, v in changes.items()})
        self.q.snapshot(self.raw, self.now)

    def test_no_next_write_until_six_minutes_and_new_read(self):
        self.q.submit("inverter_on_off", False)
        self.assertEqual(self.send()["cid"], 5161)
        self.q.submit("storage_mode", "Feed-In Priority")
        self.raw.update({52: "222", 54: "222"})
        self.q.snapshot(self.raw, self.now + 359)
        self.assertIsNotNone(self.q.active)
        self.assertIsNone(self.q.next_request(self.now + 600))
        self.q.snapshot(self.raw, self.now + 600)
        self.assertIsNone(self.q.active)
        self.assertEqual(self.q.next_request(self.now + 600)["cid"], 636)

    def test_timeout_keeps_actual_state_and_never_retries_write(self):
        self.q.submit("inverter_on_off", False)
        self.send()
        self.q.write_result(False, "timeout")
        self.confirm()
        self.assertTrue(controls.value_for("inverter_on_off", self.q.raw))
        self.assertIsNone(self.q.next_request(self.now + 1800))
        self.assertEqual(self.q.state, "not_confirmed")

    def test_late_confirmation_does_not_create_catch_up_write_credits(self):
        self.q.submit("inverter_on_off", False)
        self.send()
        self.q.submit("storage_mode", "Feed-In Priority")
        self.raw.update({52: "222", 54: "222"})
        self.now += 900  # Several nominal five-minute frames have passed.
        self.q.snapshot(self.raw, self.now)
        second = self.send()
        self.assertEqual(second["cid"], 636)
        self.q.submit("max_output_power", 80)
        self.assertIsNone(self.q.next_request(self.now + 1))
        self.assertIsNone(self.q.next_request(self.now + 359))

    def test_timeout_can_be_confirmed_later(self):
        self.q.submit("inverter_on_off", False)
        self.send()
        self.q.write_result(False, "timeout")
        self.confirm(**{"52": "222", "54": "222"})
        self.assertIsNone(self.q.active)

    def test_disagreeing_power_readback_blocks(self):
        self.raw[54] = "222"
        self.q.snapshot(self.raw, self.now)
        self.q.submit("inverter_on_off", False)
        self.assertIsNone(self.q.next_request(self.now))

    def test_readable_new_power_command_takes_precedence_over_legacy(self):
        self.raw[5162] = "190"
        self.q.snapshot(self.raw, self.now)
        self.q.submit("inverter_on_off", False)
        self.assertEqual(self.send()["cid"], 5162)
        self.confirm(**{"52": "222", "54": "222", "5162": "222"})
        self.assertIsNone(self.q.active)
        self.assertFalse(controls.value_for("inverter_on_off", self.q.raw))

    def test_failed_or_stale_read_blocks(self):
        self.q.submit("storage_mode", "Feed-In Priority")
        self.assertIsNone(self.q.next_request(self.now + 661))
        self.q.read_failed("502")
        self.assertIsNone(self.q.next_request(self.now))

    def test_mode_write_preserves_unrelated_bits_and_merges_flags(self):
        self.raw[636] = str(1 | 2 | 16 | 32 | 2048 | 256)
        self.q.snapshot(self.raw, self.now)
        self.q.set_plan({"storage_mode": "Feed-In Priority", "allow_grid_charging": False}, self.now)
        request = self.send()
        self.assertEqual(int(request["value"]), 64 | 2 | 16 | 2048 | 256)
        self.assertEqual(set(request["expected"]), {"storage_mode", "allow_grid_charging"})

    def test_only_requested_three_modes(self):
        self.assertEqual(controls.MODE_OPTIONS, ("Self-Use", "Feed-In Priority", "Off-Grid"))
        with self.assertRaises(ValueError):
            self.q.submit("storage_mode", "Self-Use + TOU")

    def test_new_plan_replaces_old_pending_values(self):
        self.q.set_plan({"slot1_discharge": True, "slot1_discharge_soc": 40}, self.now)
        self.assertEqual(self.send()["value"], "40")
        self.q.set_plan({"slot1_discharge": False, "storage_mode": "Self-Use"}, self.now + 300)
        self.confirm(**{"5965": "40"})
        self.assertIsNone(self.q.next_request(self.now))
        self.assertNotIn("slot1_discharge_soc", self.q.desired(self.now))

    def test_expired_plan_does_not_enable_slot_after_confirmation(self):
        self.q.set_plan({"slot1_discharge": True, "slot1_discharge_soc": 40}, self.now)
        self.send()
        self.confirm(**{"5965": "40"})
        self.assertIsNone(self.q.next_request(self.now))

    def test_restart_keeps_uncertain_command_but_drops_pending_desires(self):
        self.q.submit("inverter_on_off", False)
        self.send()
        self.q.submit("storage_mode", "Off-Grid")
        other = Queue()
        other.restore(self.q.persistent())
        other.snapshot(self.raw, self.now + 400)
        self.assertEqual(other.desired(self.now + 400), {})
        self.assertIsNone(other.next_request(self.now + 400))
        self.assertEqual(other.active["cid"], 5161)

    def test_unused_slot_must_be_confirmed_off(self):
        self.raw[5917] = "1"
        self.q.snapshot(self.raw, self.now)
        self.q.submit("slot1_discharge", True)
        request = self.send()
        self.assertEqual(request["cid"], 5917)
        self.assertEqual(request["old_value"], "2")
        self.confirm()
        self.assertIsNotNone(self.q.active)
        self.assertIsNone(self.q.next_request(self.now))
        self.q.snapshot({**self.raw, 5917: "0"}, self.now + 300)
        self.assertIsNone(self.q.active)

    def test_unknown_hidden_slot_prevents_masked_write(self):
        self.raw.pop(5927)
        self.q.snapshot(self.raw, self.now)
        self.q.submit("slot1_discharge", True)
        self.assertIsNone(self.q.next_request(self.now))

    def test_slot_changes_stop_configure_then_start(self):
        self.raw[5922] = "1"
        self.q.snapshot(self.raw, self.now)
        target = {"slot1_discharge": True, "slot1_discharge_soc": 40}
        self.q.set_plan(target, self.now)
        request = self.send()
        self.assertEqual((request["cid"], request["value"]), (5922, "0"))
        self.confirm(**{"5922": "0"})
        self.q.set_plan(target, self.now)
        self.assertEqual(self.send()["cid"], 5965)
        self.confirm(**{"5965": "40"})
        self.q.set_plan(target, self.now)
        request = self.send()
        self.assertEqual((request["cid"], request["value"]), (5922, "1"))

    def test_power_off_stops_slot_first(self):
        self.raw[5922] = "1"
        self.q.snapshot(self.raw, self.now)
        self.q.submit("inverter_on_off", False)
        self.assertEqual(self.send()["cid"], 5922)
        self.confirm(**{"5922": "0"})
        self.assertEqual(self.send()["cid"], 5161)

    def test_clock_confirmation_accounts_for_elapsed_time(self):
        self.q.submit("inverter_time", "2026-09-12 01:00:00")
        self.send()
        self.confirm(**{"56": "2026-09-12 01:06:05"})
        self.assertIsNone(self.q.active)
        self.assertNotIn("inverter_time", self.q.manual)

    def test_no_write_if_value_already_matches(self):
        self.q.submit("slot1_discharge_soc", 70)
        self.assertIsNone(self.q.next_request(self.now))

    def test_tou_enabled_before_slot(self):
        self.raw[636] = "1"
        self.q.snapshot(self.raw, self.now)
        self.q.submit("slot1_discharge", True)
        request = self.send()
        self.assertEqual((request["cid"], request["value"]), (636, "3"))

    def test_input_validation(self):
        for key, value in [("slot1_discharge_soc", 101), ("slot1_charge_current", -1),
                           ("slot1_charge_soc", float("nan")), ("inverter_on_off", "on"),
                           ("slot1_charge_time", "24:00-25:00"), ("slot1_discharge_soc", 1.5)]:
            with self.subTest(key=key, value=value), self.assertRaises((ValueError, TypeError)):
                self.q.submit(key, value)


def load_methods(file, class_name, names, namespace):
    """Exercise real methods independently of the installed HA runtime."""
    tree = ast.parse((ROOT / file).read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == class_name)
    cls.bases = []
    cls.decorator_list = []
    cls.body = [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]
    module = ast.Module(body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0), cls], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(ROOT / file), "exec"), namespace)
    return namespace[class_name]


class ApiRegressions(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        ns = dict(__package__="confirmed_test", asyncio=asyncio, HTTPStatus=HTTPStatus,
                  async_timeout=types.SimpleNamespace(timeout=asyncio.timeout), ClientError=ConnectionError,
                  _LOGGER=logging.getLogger("test"), _DIAGNOSTICS=logging.getLogger("test"),
                  SUCCESS="success", CONTENT="content", MESSAGE="message", STATUS_CODE="status",
                  CONTROL="/v2/api/control", CloudDeferred=CloudDeferred)
        cls = load_methods("soliscloud_api.py", "SoliscloudAPI",
                           {"read_confirmed_controls", "send_confirmed_control", "_checked_control_response",
                            "_post_data_json", "_post_data_json_once", "export_power_unit_w"}, ns)
        self.api = cls()
        self.api._token = "test-token"
        self.api._inverter_models = {}
        self.api.health = Health()

    async def test_failure_blocks_a_hundred_concurrent_followup_requests(self):
        api = self.api
        api._single_slot_control = True
        api._request_lock = asyncio.Lock()
        api._next_request_at = 0
        api._post_data_json_once = AsyncMock(return_value={"success": False, "status": 502})
        results = await asyncio.gather(*(api._post_data_json("/v1/api/inverterDetail", {"sn": "test"}) for _ in range(100)))
        api._post_data_json_once.assert_awaited_once()
        self.assertEqual(api.health.requests, 1)
        self.assertEqual(api.health.deferred, 99)
        self.assertEqual(sum("defer_seconds" in r for r in results), 99)

    async def test_model_3330_export_scaling_and_wire_steps(self):
        self.api._inverter_models = {"test": "3330"}
        self.api._post_data_json = AsyncMock(return_value={"success": True, "content": {
            "code": "0", "data": [[{"cid": 499, "msg": "10"}]]}})
        self.assertEqual(await self.api.read_confirmed_controls("test"), {499: "1000.0"})
        self.api._post_data_json.return_value["content"]["data"] = [{"code": "0"}]
        await self.api.send_confirmed_control("test", {"cid": 499, "value": "1000"})
        self.assertEqual(self.api._post_data_json.call_args.args[1]["value"], "10")
        with self.assertRaises(ValueError):
            await self.api.send_confirmed_control("test", {"cid": 499, "value": "1001"})
        self.assertEqual(self.api.export_power_unit_w("another-model"), 1)

    async def test_pending_read_is_not_a_confirmed_snapshot(self):
        self.api._post_data_json = AsyncMock(return_value={"success": True, "content": {
            "code": "0", "data": [[{"cid": 52, "msg": "222", "needLoop": "true"}]]}})
        with self.assertRaises(ValueError):
            await self.api.read_confirmed_controls("test")

    async def test_nested_control_error_is_not_success(self):
        self.api._post_data_json = AsyncMock(return_value={"success": True, "content": {"code": "0", "data": [{"code": "B0173"}]}})
        with self.assertRaises(ValueError):
            await self.api.send_confirmed_control("test", {"cid": 5161, "value": "222"})
        self.api._post_data_json.assert_awaited_once()

    async def test_success_does_not_immediately_read(self):
        self.api._post_data_json = AsyncMock(return_value={"success": True, "content": {"code": "0", "data": [{"code": "0"}]}})
        self.assertTrue(await self.api.send_confirmed_control("test", {"cid": 5161, "value": "222"}))
        self.api._post_data_json.assert_awaited_once()
        self.assertEqual(self.api._post_data_json.call_args.args[1]["cid"], "5161")

    async def test_empty_batch_rejected_and_item_errors_ignored(self):
        self.api._post_data_json = AsyncMock(return_value={"success": True, "content": {"code": "0", "data": []}})
        with self.assertRaises(ValueError):
            await self.api.read_confirmed_controls("test")
        self.api._post_data_json.return_value["content"]["data"] = [[{"cid": "52", "msg": "190"}, {"cid": "54", "msg": "error", "code": "B0600"}]]
        self.assertEqual(await self.api.read_confirmed_controls("test"), {52: "190"})

    async def test_token_expiry_clears_token(self):
        with self.assertRaises(ValueError):
            self.api._checked_control_response({"success": True, "content": {"code": "Z0001"}})
        self.assertEqual(self.api._token, "")

    async def test_cancelled_network_request_propagates(self):
        api = self.api
        api._single_slot_control = True
        api._prepare_header = Mock(return_value={})
        api._request_count = 0
        api.config = types.SimpleNamespace(domain="https://example.invalid")
        api._session = types.SimpleNamespace(post=AsyncMock(side_effect=asyncio.CancelledError))
        with self.assertRaises(asyncio.CancelledError):
            await api._post_data_json_once("/test", {})

    async def test_timeout_does_not_start_while_waiting_in_local_queue(self):
        api = self.api
        api._single_slot_control = True
        api._request_lock = asyncio.Lock()
        api._next_request_at = 0
        api._post_data_json_once = AsyncMock(return_value={})
        await api._request_lock.acquire()
        task = asyncio.create_task(api._post_data_json("/test", {}))
        await asyncio.sleep(0)
        api._post_data_json_once.assert_not_awaited()
        api._request_lock.release()
        await task
        api._post_data_json_once.assert_awaited_once()


class LifecycleRegressions(unittest.IsolatedAsyncioTestCase):
    async def test_wall_clock_jump_cannot_start_confirmation_read_before_monotonic_deadline(self):
        cls = load_methods("confirmed_hub.py", "ConfirmedControlHub", {"refresh"},
                           dict(asyncio=asyncio, time=types.SimpleNamespace(time=lambda: 90000)))
        q = Queue()
        q.active = {"key": "inverter_on_off"}
        q.last_sent = 10000
        device = types.SimpleNamespace(lock=asyncio.Lock(), queue=q,
                    not_before_monotonic=asyncio.get_running_loop().time()+360)
        hub = cls()
        hub.closed = False
        hub.devices = {"test": device}
        hub.service = types.SimpleNamespace(api=Mock())
        await hub.refresh("test", force=True)
        hub.service.api.health.delay.assert_not_called()

    async def test_startup_discovery_waits_without_attempting_http(self):
        cls = load_methods("service.py", "InverterService", {"_run_discovery"}, {})
        svc = cls()
        svc.confirmed_hub = object()
        health = Health()
        health.hold_startup()
        svc._api = types.SimpleNamespace(health=health)
        svc._discovery_callback = object()
        svc._discovery_cookie = {"test": True}
        svc._do_discover = AsyncMock()
        svc.schedule_discovery = Mock()
        await svc._run_discovery()
        svc._do_discover.assert_not_awaited()
        svc.schedule_discovery.assert_called_once()

    async def test_stopped_worker_is_restarted_once_at_the_next_read_cycle(self):
        cls = load_methods("confirmed_hub.py", "ConfirmedControlHub", {"refresh_all"},
                           dict(_LOGGER=logging.getLogger("test")))
        hub = cls()
        hub.closed = False
        old = asyncio.create_task(asyncio.sleep(0))
        await old
        device = types.SimpleNamespace(worker=old, worker_restarts=0)
        hub.devices = {"test": device}
        event = asyncio.Event()
        hub._worker = lambda device: event.wait()
        hub.hass = types.SimpleNamespace(async_create_background_task=lambda coro, name: asyncio.create_task(coro))
        hub.refresh = AsyncMock()
        await hub.refresh_all()
        restarted = device.worker
        await hub.refresh_all()
        self.assertIs(device.worker, restarted)
        self.assertEqual(device.worker_restarts, 1)
        event.set()
        await restarted

    async def test_locally_blocked_write_retains_target_without_uncertain_command(self):
        cls = load_methods("confirmed_hub.py", "ConfirmedControlHub", {"_worker"},
                           dict(asyncio=asyncio, time=time, CloudDeferred=CloudDeferred, _LOGGER=logging.getLogger("test")))
        hub = cls()
        hub.closed = False
        q = Queue()
        q.snapshot(snapshot(), time.time())
        q.submit("storage_mode", "Feed-In Priority")
        device = types.SimpleNamespace(serial="test", queue=q, lock=asyncio.Lock(), wake=asyncio.Event(),
                    storage_failed=False, not_before_monotonic=0, read_not_before_monotonic=0,
                    store=types.SimpleNamespace(async_save=AsyncMock()))
        hub.service = types.SimpleNamespace(api=types.SimpleNamespace(health=Health(),
                    send_confirmed_control=AsyncMock(side_effect=CloudDeferred(120))))
        def finish_iteration():
            hub.closed = True
            device.wake.set()
        hub.changed = finish_iteration
        await hub._worker(device)
        self.assertIsNone(q.active)
        self.assertEqual(q.last_sent, 0)
        self.assertEqual(q.manual["storage_mode"], "Feed-In Priority")
        self.assertEqual(q.state, "cloud_backoff")
        self.assertGreater(device.not_before_monotonic, asyncio.get_running_loop().time())

    async def test_failed_read_does_not_retry_on_concurrent_or_forced_refresh(self):
        clock = types.SimpleNamespace(time=lambda: 10000)
        ns = dict(asyncio=asyncio, time=clock, CloudDeferred=CloudDeferred, _LOGGER=logging.getLogger("test"))
        cls = load_methods("confirmed_hub.py", "ConfirmedControlHub", {"refresh"}, ns)
        hub = cls()
        hub.closed = False
        queue = Queue()
        device = types.SimpleNamespace(lock=asyncio.Lock(), queue=queue,
                    store=types.SimpleNamespace(async_save=AsyncMock()),
                    wake=asyncio.Event(), read_not_before_monotonic=0)
        hub.devices = {"test": device}
        hub.changed = Mock()
        api = types.SimpleNamespace(read_confirmed_controls=AsyncMock(side_effect=TimeoutError()), health=Health())
        hub.service = types.SimpleNamespace(_login=AsyncMock(return_value=True), api=api)
        await asyncio.gather(hub.refresh("test"), hub.refresh("test", force=True))
        await hub.refresh("test", force=True)
        api.read_confirmed_controls.assert_awaited_once()
        self.assertEqual(queue.read_attempt_at, 10000)
        self.assertFalse(queue.read_ok)
        # Once the attempt budget expires, a new read can recover normally.
        device.read_not_before_monotonic = 0
        api.read_confirmed_controls.side_effect = None
        api.read_confirmed_controls.return_value = snapshot()
        await hub.refresh("test")
        self.assertEqual(api.read_confirmed_controls.await_count, 2)
        self.assertTrue(queue.read_ok)

    async def test_reload_cancels_timers_and_running_requests(self):
        timers = []
        def track(*args):
            cancel = Mock()
            timers.append(cancel)
            return cancel
        ns = dict(asyncio=asyncio, timedelta=timedelta, _LOGGER=logging.getLogger("test"),
                  dt_util=types.SimpleNamespace(utcnow=lambda: datetime.now(timezone.utc)),
                  async_track_point_in_utc_time=track)
        cls = load_methods("service.py", "InverterService", {"schedule_update", "schedule_discovery", "_cancel_timer", "shutdown"}, ns)
        svc = cls()
        svc._stopped = False
        svc._discovery_complete = False
        svc._hass = object()
        svc.confirmed_hub = types.SimpleNamespace(shutdown=AsyncMock(), changed=Mock())
        svc._api = types.SimpleNamespace(health=Health())
        svc._cancel_update = svc._cancel_discovery = None
        svc.async_update = svc.async_discover = AsyncMock()
        svc._logout = AsyncMock()
        svc._subscriptions = {"test": {}}
        running = asyncio.create_task(asyncio.Event().wait())
        svc._active_tasks = {running}
        svc.schedule_update(timedelta(seconds=300))
        svc.schedule_update(timedelta(seconds=300))
        timers[0].assert_called_once()
        svc.schedule_discovery(None, {}, 300)
        await svc.shutdown()
        self.assertTrue(running.cancelled())
        for timer in timers:
            timer.assert_called_once()
        svc.schedule_update(timedelta(seconds=1))
        self.assertEqual(len(timers), 3)
        svc.confirmed_hub.shutdown.assert_awaited_once()


class RecoveryBudget(unittest.TestCase):
    def setUp(self):
        self.now = 10000.0
        self.wall = 1700000000.0
        self.h = Health(lambda: self.now, lambda: self.wall)
        self.endpoint = "/v1/api/inverterDetail"
        self.params = {"sn": "test"}

    def test_backoff_grows_to_twenty_minutes_then_success_recovers(self):
        for delay in (300, 600, 1200, 1200):
            self.h.begin(self.endpoint, self.params)
            self.h.finish(self.endpoint, self.params, False, "HTTP 502")
            self.assertEqual(self.h.delay(), delay)
            with self.assertRaises(CloudDeferred):
                self.h.begin("/v2/api/atReadBatch", self.params)
            self.now += delay
        self.h.begin(self.endpoint, self.params)
        self.h.finish(self.endpoint, self.params, True)
        self.assertEqual(self.h.delay(), 0)
        self.assertEqual(self.h.consecutive_failures, 0)

    def test_read_window_starts_at_response_end(self):
        self.h.begin(self.endpoint, self.params)
        self.now += 30
        self.h.finish(self.endpoint, self.params, True)
        self.now += 299
        self.assertEqual(self.h.delay(self.endpoint, self.params), 1)
        with self.assertRaises(CloudDeferred):
            self.h.begin(self.endpoint, self.params)
        self.now += 1
        self.h.begin(self.endpoint, self.params)

    def test_new_client_is_quiet_for_full_300_seconds_even_after_clock_jump(self):
        self.h.hold_startup()
        self.wall += 86400
        self.now += 299
        for path in (self.endpoint, self.h.CONTROL, "/v2/api/login"):
            with self.assertRaises(CloudDeferred):
                self.h.begin(path, self.params)
        self.assertEqual(self.h.requests, 0)
        self.assertEqual(self.h.diagnostics("test")["state"], "starting")
        self.now += 1
        self.h.begin(self.endpoint, self.params)

    def test_recovery_probe_must_be_a_read_and_endpoint_failures_survive_other_successes(self):
        self.h.begin(self.endpoint, self.params)
        self.h.finish(self.endpoint, self.params, False)
        self.now += 300
        with self.assertRaises(CloudDeferred):
            self.h.begin(self.h.CONTROL, self.params)
        other = "/v1/api/stationDetail"
        self.h.begin(other, self.params)
        self.h.finish(other, self.params, True)
        self.h.begin(self.endpoint, self.params)
        self.h.finish(self.endpoint, self.params, False)
        self.assertEqual(self.h.delay(), 600)

    def test_write_guard_is_independent_of_queue_and_wall_clock(self):
        self.h.begin(self.h.CONTROL, self.params)
        self.now += 30
        self.h.finish(self.h.CONTROL, self.params, True)
        self.wall += 86400  # NTP/wall-clock step cannot bypass the limit.
        self.now += 359
        with self.assertRaises(CloudDeferred):
            self.h.begin(self.h.CONTROL, self.params)
        self.now += 1
        self.h.begin(self.h.CONTROL, self.params)

    def test_successful_http_does_not_make_old_telemetry_fresh(self):
        self.h.begin(self.endpoint, self.params)
        self.h.finish(self.endpoint, self.params, True)
        self.h.telemetry((self.wall - 1200) * 1000)
        self.assertEqual(self.h.diagnostics("test")["state"], "stale_telemetry")
        self.h.telemetry(self.wall - 10)
        self.assertEqual(self.h.diagnostics("test")["state"], "healthy")

    def test_early_telemetry_does_not_advance_read_or_write_deadlines(self):
        for endpoint, interval in ((self.endpoint, 300), (self.h.CONTROL, 360)):
            self.h.begin(endpoint, self.params)
            self.h.finish(endpoint, self.params, True)
            before = self.h.delay(endpoint, self.params)
            self.h.telemetry(self.wall - 246.5)
            self.h.telemetry(self.wall)
            self.assertEqual(self.h.delay(endpoint, self.params), before)
            self.assertEqual(before, interval)

    def test_late_or_repeated_telemetry_does_not_postpone_an_open_deadline(self):
        self.h.begin(self.endpoint, self.params)
        self.h.finish(self.endpoint, self.params, True)
        self.now += 300
        for _ in range(10):
            self.h.telemetry(self.wall - 514.66)
        self.assertEqual(self.h.delay(self.endpoint, self.params), 0)
        self.h.begin(self.endpoint, self.params)


if __name__ == "__main__":
    unittest.main()
