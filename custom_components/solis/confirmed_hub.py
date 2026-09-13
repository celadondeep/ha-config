"""Home Assistant adapter for the confirmed Solis command queue."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import time

import voluptuous as vol
from homeassistant.core import ServiceCall
from homeassistant.helpers.storage import Store
from homeassistant.exceptions import HomeAssistantError

from .confirmed_queue import ConfirmedCommandQueue
from .cloud_health import CloudDeferred

_LOGGER = logging.getLogger("custom_components.solis.cloud_diagnostics")

@dataclass
class Device:
    serial: str
    queue: ConfirmedCommandQueue
    store: Store
    lock: asyncio.Lock
    wake: asyncio.Event
    worker: asyncio.Task | None = None
    not_before_monotonic: float = 0.0
    storage_failed: bool = False
    read_not_before_monotonic: float = 0.0
    worker_restarts: int = 0

class ConfirmedControlHub:
    def __init__(self, hass, entry, service):
        self.hass = hass
        self.entry = entry
        self.service = service
        self.devices = {}
        self.platforms = {}
        self.listeners = set()
        self.closed = False
        self._register_services()

    def _register_services(self):
        hubs = self.hass.data.setdefault("solis_confirmed_hubs", {})
        hubs[self.entry.entry_id] = self
        if self.hass.services.has_service("solis", "set_plan"):
            return

        async def set_plan(call: ServiceCall):
            hub = self.hass.data.get("solis_confirmed_hubs", {}).get(call.data["entry_id"])
            if hub is None or hub.closed:
                raise HomeAssistantError("Confirmed Solis controls are unavailable")
            serial = str(call.data["inverter_sn"])
            device = hub.devices.get(serial)
            if device is None:
                raise HomeAssistantError("Solis inverter discovery has not finished")
            try:
                async with device.lock:
                    if call.data.get("cancel", False):
                        device.queue.cancel_plan()
                    else:
                        device.queue.set_plan(call.data.get("targets", {}), time.time(), ttl=180)
            except (ValueError, KeyError, TypeError) as error:
                raise HomeAssistantError(str(error)) from error
            hub.changed()
            device.wake.set()

        self.hass.services.async_register(
            "solis", "set_plan", set_plan,
            schema=vol.Schema({
                vol.Required("entry_id"): str,
                vol.Required("inverter_sn"): str,
                vol.Optional("targets", default={}): dict,
                vol.Optional("cancel", default=False): bool,
            }),
        )

    def register_platform(self, platform, add_entities):
        self.platforms[platform] = add_entities
        for serial in self.devices:
            self._add_platform_entities(platform, serial)

    def _add_platform_entities(self, platform, serial):
        from .confirmed_entities import entities_for
        self.platforms[platform](entities_for(self, serial, platform))

    def listen(self, callback):
        self.listeners.add(callback)
        return lambda: self.listeners.discard(callback)

    def changed(self):
        for callback in tuple(self.listeners):
            callback()

    async def discover(self, serials):
        for serial in serials:
            if serial in self.devices or self.closed:
                continue
            store = Store(self.hass, 1, f"solis_confirmed_commands.{self.entry.entry_id}.{serial}")
            queue = ConfirmedCommandQueue()
            queue.export_power_unit_w = self.service.api.export_power_unit_w(serial)
            saved = await store.async_load()
            if isinstance(saved, dict):
                queue.restore(saved)
            device = Device(serial, queue, store, asyncio.Lock(), asyncio.Event())
            remaining = max(0.0, queue.last_sent + queue.interval - time.time())
            if queue.active:
                # Preserve the actual attempt timestamp for diagnostics, while
                # separately preventing another write for a full restart interval.
                remaining = max(remaining, queue.interval)
            device.not_before_monotonic = asyncio.get_running_loop().time() + remaining
            self.devices[serial] = device
            for platform in self.platforms:
                self._add_platform_entities(platform, serial)
            device.worker = self.hass.async_create_background_task(
                self._worker(device), f"solis confirmed commands {serial}"
            )
            await self.refresh(serial, force=True)

    async def refresh_all(self):
        for serial, device in self.devices.items():
            if not self.closed and device.worker is not None and device.worker.done():
                device.worker_restarts += 1
                _LOGGER.warning("Restarting a stopped Solis command worker; persisted command will be reconciled")
                device.worker = self.hass.async_create_background_task(
                    self._worker(device), f"solis confirmed commands {serial}"
                )
            await self.refresh(serial)

    async def refresh(self, serial, force=False):
        device = self.devices.get(serial)
        if device is None or self.closed:
            return
        async with device.lock:
            now = time.time()
            queue = device.queue
            loop = asyncio.get_running_loop()
            # While settling, telemetry continues but register readback waits.
            if queue.active and (now < queue.last_sent + queue.interval
                                 or loop.time() < device.not_before_monotonic):
                return
            retry = self.service.api.health.delay()
            if retry:
                device.read_not_before_monotonic = max(device.read_not_before_monotonic, loop.time() + retry)
                return
            # All callers share the same attempt budget, including failed reads
            # and forced confirmation reads. A plan refresh must not retry HTTP.
            if loop.time() < device.read_not_before_monotonic:
                return
            queue.read_attempt_at = now
            device.read_not_before_monotonic = loop.time() + 300
            try:
                if not await self.service._login():
                    raise ValueError("Solis telemetry login is unavailable")
                raw = await self.service.api.read_confirmed_controls(serial)
                active_before = queue.active
                queue.snapshot(raw, time.time())
                if active_before and queue.active is None:
                    self.service.api.health.write_confirmed(serial)
                await device.store.async_save(queue.persistent())
            except asyncio.CancelledError:
                raise
            except CloudDeferred as error:
                device.read_not_before_monotonic = loop.time() + error.seconds
                queue.state = "cloud_backoff"
            except Exception as error:
                queue.read_failed(error)
                _LOGGER.warning("Solis control snapshot failed: %s", error)
            finally:
                device.read_not_before_monotonic = max(device.read_not_before_monotonic,
                    loop.time() + max(300, self.service.api.health.delay()))
        self.changed()
        device.wake.set()

    async def submit(self, serial, key, value):
        device = self.devices[serial]
        try:
            async with device.lock:
                device.queue.submit(key, value)
        except (ValueError, KeyError, TypeError) as error:
            raise HomeAssistantError(str(error)) from error
        self.changed()
        device.wake.set()

    async def clear(self, serial):
        device = self.devices[serial]
        async with device.lock:
            queue = device.queue
            if queue.active and (time.time() < queue.last_sent + queue.interval
                                 or asyncio.get_running_loop().time() < device.not_before_monotonic
                                 or not queue.read_ok or queue.read_at < queue.last_sent + queue.interval):
                raise HomeAssistantError("Wait at least 6 minutes and a fresh device read before clearing an unconfirmed command")
            device.queue.clear()
            await device.store.async_save(device.queue.persistent())
        self.changed()
        device.wake.set()

    async def _worker(self, device):
        while not self.closed:
            queue = device.queue
            now = time.time()
            due = queue.last_sent + queue.interval
            needs_confirmation = queue.active and now >= due and (
                queue.read_at < due or now - queue.read_at >= 300
            ) and asyncio.get_running_loop().time() >= device.read_not_before_monotonic
            if needs_confirmation:
                await self.refresh(device.serial, force=True)
            device.wake.clear()
            async with device.lock:
                if device.storage_failed:
                    request = None
                elif asyncio.get_running_loop().time() < device.not_before_monotonic:
                    request = None
                    if not queue.active:
                        queue.state = "cooldown"
                elif self.service.api.health.delay():
                    request = None
                    if not queue.active:
                        queue.state = "cloud_backoff"
                else:
                    request = queue.next_request(time.time())
                if request:
                    previous_sent = queue.last_sent
                    previous_deadline = device.not_before_monotonic
                    queue.mark_sent(request, time.time())
                    device.not_before_monotonic = asyncio.get_running_loop().time() + queue.interval
                    try:
                        # Persist the uncertain write BEFORE touching the inverter.
                        await device.store.async_save(queue.persistent())
                    except Exception as error:
                        device.storage_failed = True
                        queue.state = "storage_error"
                        queue.error = str(error)
                        _LOGGER.error("Solis command withheld: persistent queue save failed")
                    else:
                        _LOGGER.info("Solis command submitting key=%s cid=%s; readback in at least 360s",
                                     request["key"], request["cid"])
                        sent = True
                        try:
                            accepted = await self.service.api.send_confirmed_control(device.serial, request)
                            queue.write_result(accepted)
                        except asyncio.CancelledError:
                            queue.last_sent = time.time()
                            await asyncio.shield(device.store.async_save(queue.persistent()))
                            raise
                        except CloudDeferred as error:
                            # The API limiter guarantees that no HTTP request was
                            # sent. Restore the preflight state, retaining desires.
                            sent = False
                            queue.active = None
                            queue.last_sent = previous_sent
                            queue.state = "cloud_backoff"
                            queue.error = str(error)
                            device.not_before_monotonic = max(previous_deadline,
                                asyncio.get_running_loop().time() + error.seconds)
                        except Exception as error:
                            queue.write_result(False, str(error))
                            _LOGGER.warning("Solis command outcome requires readback key=%s: %s", request["key"], error)
                        # Count the interval from the completed network attempt,
                        # including time spent waiting for the shared API lock.
                        if sent:
                            queue.last_sent = time.time()
                            device.not_before_monotonic = asyncio.get_running_loop().time() + queue.interval
                        try:
                            await device.store.async_save(queue.persistent())
                        except Exception as error:
                            device.storage_failed = True
                            queue.state = "storage_error"
                            queue.error = str(error)
            self.changed()
            if queue.active and time.time() < queue.last_sent + queue.interval:
                timeout = max(1.0, queue.last_sent + queue.interval - time.time())
            else:
                timeout = 300.0
            try:
                await asyncio.wait_for(device.wake.wait(), timeout=timeout)
            except TimeoutError:
                pass

    async def shutdown(self):
        self.closed = True
        tasks = [device.worker for device in self.devices.values() if device.worker]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self.listeners.clear()
        hubs = self.hass.data.get("solis_confirmed_hubs", {})
        hubs.pop(self.entry.entry_id, None)
        if not hubs:
            self.hass.services.async_remove("solis", "set_plan")
