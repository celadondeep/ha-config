"""Failures seen in Eimo production, reproduced without any cloud writes."""
import asyncio
import logging
import types
import time
import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock
from zoneinfo import ZoneInfo

from test_solis_confirmed_controls import Queue, snapshot, controls, load_methods, Health, CloudDeferred


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.now = 10000
        self.q = Queue(wall=lambda: self.now)
        self.raw = snapshot(**{'636': '66'})
        self.q.snapshot(self.raw, self.now)

    def send_mode(self):
        self.q.set_plan({'storage_mode': 'Self-Use'}, self.now)
        r = self.q.next_request(self.now)
        self.q.mark_sent(r, self.now)
        self.q.write_result(False, '502')

    def retire(self):
        self.q.snapshot(self.raw, self.now+360)
        self.q.snapshot(self.raw, self.now+660)

    def test_two_distinct_spaced_reads_retire_failed_command_without_claiming_success(self):
        self.send_mode()
        self.q.snapshot(self.raw, self.now+360)
        for offset in (360, 400, 659):
            self.q.snapshot(self.raw, self.now+offset)
            self.assertIsNotNone(self.q.active)
        self.q.snapshot(self.raw, self.now+660)
        self.assertIsNone(self.q.active)
        self.assertIsNone(self.q.last_confirmed)
        self.assertEqual(self.q.last_failure['outcome'], 'not_applied')
        self.assertEqual(self.q.recovery_count, 1)

    def test_failed_or_incomplete_reads_cannot_resolve_uncertain_write(self):
        self.send_mode()
        self.q.snapshot(self.raw, self.now+360)
        partial = dict(self.raw); partial.pop(636)
        self.q.snapshot(partial, self.now+660)
        self.q.snapshot(self.raw, self.now+960)
        self.assertIsNotNone(self.q.active)
        self.q.read_failed('timeout')
        self.q.snapshot(self.raw, self.now+1260)
        self.assertIsNotNone(self.q.active)
        self.q.snapshot(self.raw, self.now+1560)
        self.assertIsNone(self.q.active)

    def test_night_off_can_proceed_while_failed_mode_is_cooling_down(self):
        self.send_mode(); self.retire()
        self.q.set_plan({'inverter_on_off': False, 'slot1_charge': False,
                         'slot1_discharge': False, 'storage_mode': 'Self-Use'}, self.now+660)
        r = self.q.next_request(self.now+660)
        self.assertEqual(r['key'], 'inverter_on_off')
        self.assertEqual(r['value'], '222')

    def test_retry_requires_backoff_fresh_read_and_current_plan(self):
        self.send_mode(); self.retire()
        deadline = self.q.retry_after['636']
        self.q.set_plan({'storage_mode': 'Self-Use'}, deadline-1)
        self.q.snapshot(self.raw, deadline-1)
        self.assertIsNone(self.q.next_request(deadline-1))
        self.assertEqual(self.q.state, 'retry_wait')
        self.q.cancel_plan()
        self.assertIsNone(self.q.next_request(deadline))
        self.q.set_plan({'storage_mode': 'Self-Use'}, deadline+700)
        self.assertIsNone(self.q.next_request(deadline+700))
        self.q.snapshot(self.raw, deadline+700)
        self.assertEqual(self.q.next_request(deadline+700)['value'], '3')

    def test_retry_backoff_survives_restart_and_target_changes(self):
        self.send_mode(); self.retire()
        other = Queue(wall=lambda: self.now+660)
        other.restore(self.q.persistent())
        other.snapshot(self.raw, self.now+660)
        other.set_plan({'storage_mode': 'Off-Grid'}, self.now+660)
        self.assertIsNone(other.next_request(self.now+660))
        self.assertEqual(other.retry_after, self.q.retry_after)
        self.assertEqual(other.failure_counts['636'], 1)

    def test_success_resets_failure_budget(self):
        self.send_mode(); self.retire()
        at = self.q.retry_after['636']
        self.q.snapshot(self.raw, at)
        self.q.set_plan({'storage_mode': 'Self-Use'}, at)
        self.q.mark_sent(self.q.next_request(at), at)
        self.q.snapshot(snapshot(**{'636': '3'}), at+360)
        self.assertNotIn('636', self.q.failure_counts)
        self.assertIsNotNone(self.q.last_confirmed)

    def test_old_persisted_mode_confirms_when_only_unrelated_bits_changed(self):
        self.send_mode()
        self.q.active.pop('mode_mask')
        self.q.snapshot(snapshot(**{'636': str(1 | 2 | 256)}), self.now+360)
        self.assertIsNone(self.q.active)
        self.assertIsNotNone(self.q.last_confirmed)

    def test_requested_mode_flags_and_tou_still_require_confirmation(self):
        self.q.set_plan({'storage_mode': 'Self-Use', 'allow_grid_charging': False,
                         'slot1_discharge': True}, self.now)
        self.q.mark_sent(self.q.next_request(self.now), self.now)
        self.q.snapshot(snapshot(**{'636': '35'}), self.now+360)
        self.assertIsNotNone(self.q.active)
        self.q.snapshot(snapshot(**{'636': '1'}), self.now+660)
        self.assertIsNone(self.q.active)
        self.assertIsNone(self.q.last_confirmed)
        self.assertEqual(self.q.last_failure['outcome'], 'not_applied')

    def test_unsent_manual_command_expires(self):
        self.q.submit('inverter_on_off', False)
        self.q.snapshot(self.raw, self.now+1800)
        self.assertEqual(self.q.desired(self.now+1800), {})
        self.assertIsNone(self.q.next_request(self.now+1800))

    def test_conflicting_plan_is_rejected_before_replacing_previous(self):
        self.q.set_plan({'inverter_on_off': False}, self.now)
        with self.assertRaises(ValueError):
            self.q.set_plan({'slot1_charge': True, 'slot1_discharge': True}, self.now)
        self.assertEqual(self.q.plan, {'inverter_on_off': False})

    def test_enabling_one_slot_first_stops_opposite_physical_slot(self):
        self.q.snapshot(snapshot(**{'5922':'1'}), self.now)
        self.q.submit('slot1_charge',True)
        first=self.q.next_request(self.now)
        self.assertEqual((first['cid'],first['value']),(5922,'0'))
        self.q.mark_sent(first,self.now)
        self.q.snapshot(snapshot(),self.now+360)
        second=self.q.next_request(self.now+360)
        self.assertEqual((second['cid'],second['value']),(5916,'1'))


class StorageRecoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_repeated_service_calls_cannot_renew_expired_source_plan(self):
        now = [10000]
        vol = types.SimpleNamespace(Schema=lambda x:x, Required=lambda k,**kw:k,
                                    Optional=lambda k,**kw:k, Coerce=lambda t:t)
        cls = load_methods('confirmed_hub.py', 'ConfirmedControlHub', {'_register_services'},
              dict(vol=vol,time=types.SimpleNamespace(time=lambda:now[0]),HomeAssistantError=ValueError))
        services=types.SimpleNamespace(has_service=lambda *args:False,async_register=Mock())
        hub=cls(); hub.entry=types.SimpleNamespace(entry_id='entry');hub.closed=False
        hub.hass=types.SimpleNamespace(data={},services=services);hub.changed=Mock()
        q=Queue(); device=types.SimpleNamespace(queue=q,lock=asyncio.Lock(),wake=asyncio.Event())
        hub.devices={'test':device};hub._register_services()
        handler=services.async_register.call_args.args[2]
        call=types.SimpleNamespace(data={'entry_id':'entry','inverter_sn':'test',
              'targets':{'slot1_discharge':True},'valid_until':10060})
        await handler(call)
        self.assertEqual(q.plan_expires,10060)
        now[0]=10050;await handler(call)
        self.assertEqual(q.plan_expires,10060)
        now[0]=10061;await handler(call)
        self.assertEqual(q.desired(now[0]),{})

    async def test_preflight_save_failure_does_not_send_and_can_recover(self):
        cls = load_methods('confirmed_hub.py', 'ConfirmedControlHub', {'_worker'},
              dict(asyncio=asyncio, time=time, CloudDeferred=CloudDeferred, _LOGGER=logging.getLogger('test')))
        hub = cls(); hub.closed = False
        q = Queue(); q.snapshot(snapshot(), time.time()); q.submit('inverter_on_off', False)
        device = types.SimpleNamespace(serial='test', queue=q, lock=asyncio.Lock(), wake=asyncio.Event(),
            storage_failed=False, not_before_monotonic=0, read_not_before_monotonic=0,
            store=types.SimpleNamespace(async_save=AsyncMock(side_effect=OSError('disk temporarily unavailable'))))
        api = types.SimpleNamespace(health=Health(), send_confirmed_control=AsyncMock())
        hub.service = types.SimpleNamespace(api=api)
        def stop():
            hub.closed = True; device.wake.set()
        hub.changed = stop
        await hub._worker(device)
        api.send_confirmed_control.assert_not_awaited()
        self.assertTrue(device.storage_failed)
        device.store.async_save.side_effect = None
        hub.closed = False
        await hub._worker(device)
        self.assertFalse(device.storage_failed)
        api.send_confirmed_control.assert_not_awaited()
        self.assertIsNotNone(q.active)  # must reconcile after the settling interval

    async def test_save_failure_after_retirement_blocks_worker(self):
        clock = types.SimpleNamespace(time=lambda: 11000)
        cls = load_methods('confirmed_hub.py', 'ConfirmedControlHub', {'refresh'},
             dict(asyncio=asyncio, time=clock, CloudDeferred=CloudDeferred, _LOGGER=logging.getLogger('test')))
        q = Queue(); raw = snapshot(**{'636':'66'}); q.snapshot(raw, 10000)
        q.set_plan({'storage_mode':'Self-Use'}, 10000); q.mark_sent(q.next_request(10000), 10000)
        q.snapshot(raw, 10360)
        device = types.SimpleNamespace(lock=asyncio.Lock(), queue=q, wake=asyncio.Event(),
            not_before_monotonic=0, read_not_before_monotonic=0, storage_failed=False,
            store=types.SimpleNamespace(async_save=AsyncMock(side_effect=OSError('disk'))))
        api = types.SimpleNamespace(health=Health(), read_confirmed_controls=AsyncMock(return_value=raw))
        hub = cls(); hub.closed=False; hub.devices={'test':device}; hub.changed=Mock()
        hub.service=types.SimpleNamespace(api=api,_login=AsyncMock(return_value=True))
        await hub.refresh('test')
        self.assertIsNone(q.active)
        self.assertTrue(device.storage_failed)




if __name__ == '__main__':
    unittest.main()
