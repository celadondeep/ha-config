"""Entities backed exclusively by confirmed device register snapshots."""
from __future__ import annotations

from datetime import datetime, timezone
import time

from homeassistant.components.button import ButtonEntity
from homeassistant.components.datetime import DateTimeEntity
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.components.select import SelectEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.components.text import TextEntity
from homeassistant.helpers.entity import Entity, EntityCategory
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .confirmed_controls import CONTROLS, MODE_OPTIONS, TIME_PATTERN, UNUSED_SLOT_CIDS, value_for


def iso(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).isoformat() if timestamp else None


class ConfirmedEntity(Entity):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, hub, serial, control=None, *, platform=None, key=None, name=None):
        self.hub = hub
        self.serial = serial
        self.control = control
        self.key = control.key if control else key
        platform = control.platform if control else platform
        self.entity_id = f"{platform}.solis_inverter_{serial}_{self.key}"
        self._attr_unique_id = f"{hub.entry.entry_id}_{serial}_confirmed_{self.key}"
        self._attr_name = control.name if control else name
        self._attr_icon = control.icon if control else "mdi:cloud-clock"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"{serial}_{hub.service.api_name}")},
            "manufacturer": "Solis",
            "name": f"Solis_Inverter_{serial}",
        }

    @property
    def queue(self):
        return self.hub.devices[self.serial].queue

    @property
    def available(self):
        return (not self.hub.closed and self.queue.read_ok
                and time.time() - self.queue.read_at <= 660
                and self.queue.raw.get(6798) == "43605"
                and (self.control is None or value_for(self.key, self.queue.raw) is not None)
                and (self.key != "allow_export" or value_for("storage_mode", self.queue.raw) == "Self-Use"))

    @property
    def actual(self):
        return value_for(self.key, self.queue.raw)

    @property
    def extra_state_attributes(self):
        desired = self.queue.desired(time.time())
        return {
            "last_read": iso(self.queue.read_at),
            "pending_target": desired.get(self.key),
            "command_status": self.queue.state,
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(self.hub.listen(self.async_write_ha_state))

    async def request(self, value):
        await self.hub.submit(self.serial, self.key, value)


class ConfirmedSwitch(ConfirmedEntity, SwitchEntity):
    @property
    def is_on(self):
        return self.actual

    async def async_turn_on(self, **kwargs):
        await self.request(True)

    async def async_turn_off(self, **kwargs):
        await self.request(False)


class ConfirmedSelect(ConfirmedEntity, SelectEntity):
    _attr_options = list(MODE_OPTIONS)

    @property
    def current_option(self):
        return self.actual

    async def async_select_option(self, option):
        await self.request(option)


class ConfirmedNumber(ConfirmedEntity, NumberEntity):
    _attr_mode = NumberMode.BOX

    def __init__(self, hub, serial, control):
        super().__init__(hub, serial, control)
        self._attr_native_min_value = control.minimum
        self._attr_native_max_value = control.maximum
        self._attr_native_step = control.step
        if control.key == "max_export_power":
            self._attr_native_step = self.queue.export_power_unit_w
        self._attr_native_unit_of_measurement = control.unit
        # SOC setpoints are configuration values, not a device battery indicator.

    @property
    def native_value(self):
        return self.actual

    async def async_set_native_value(self, value):
        await self.request(value)


class ConfirmedText(ConfirmedEntity, TextEntity):
    _attr_native_min = 11
    _attr_native_max = 11
    _attr_pattern = TIME_PATTERN.pattern

    @property
    def native_value(self):
        return self.actual

    async def async_set_value(self, value):
        await self.request(value)


class ConfirmedDateTime(ConfirmedEntity, DateTimeEntity):
    @property
    def native_value(self):
        try:
            return datetime.strptime(self.actual, "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt_util.DEFAULT_TIME_ZONE)
        except (ValueError, TypeError):
            return None

    async def async_set_value(self, value):
        await self.request(dt_util.as_local(value).strftime("%Y-%m-%d %H:%M:%S"))


class CommandStatus(ConfirmedEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hub, serial):
        super().__init__(hub, serial, platform="sensor", key="cloud_command_status", name="Cloud Command Status")

    @property
    def available(self):
        return not self.hub.closed

    @property
    def native_value(self):
        return self.queue.state

    @property
    def extra_state_attributes(self):
        queue = self.queue
        return {
            "last_read": iso(queue.read_at),
            "last_read_attempt": iso(queue.read_attempt_at),
            "last_sent": iso(queue.last_sent),
            "confirm_after": iso(queue.last_sent + queue.interval) if queue.active else None,
            "active_command": queue.active["key"] if queue.active else None,
            "active_target": queue.active["expected"] if queue.active else None,
            "pending_targets": queue.desired(time.time()),
            "last_confirmed": queue.last_confirmed,
            "error": queue.error,
            "minimum_write_interval": queue.interval,
            "unused_slots_off": all(queue.raw.get(cid) == "0" for cid in UNUSED_SLOT_CIDS),
        }


class ClearCommands(ConfirmedEntity, ButtonEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hub, serial):
        super().__init__(hub, serial, platform="button", key="clear_pending_commands", name="Clear Pending Commands")
        self._attr_icon = "mdi:playlist-remove"

    @property
    def available(self):
        return not self.hub.closed

    async def async_press(self):
        await self.hub.clear(self.serial)


class CloudApiHealth(ConfirmedEntity, SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hub, serial):
        super().__init__(hub, serial, platform="sensor", key="cloud_api_health", name="Cloud API Health")

    @property
    def available(self):
        return not self.hub.closed

    @property
    def native_value(self):
        worker = self.hub.devices[self.serial].worker
        if worker is not None and worker.done():
            return "worker_stopped"
        return self.hub.service.api.health.diagnostics(self.serial)["state"]

    @property
    def extra_state_attributes(self):
        attrs = {k: v for k, v in self.hub.service.api.health.diagnostics(self.serial).items() if k != "state"}
        attrs["worker_restarts"] = self.hub.devices[self.serial].worker_restarts
        return attrs


_ENTITY_CLASSES = {"switch": ConfirmedSwitch, "number": ConfirmedNumber, "select": ConfirmedSelect,
                   "text": ConfirmedText, "datetime": ConfirmedDateTime}


def entities_for(hub, serial, platform):
    if platform == "sensor":
        return [CommandStatus(hub, serial), CloudApiHealth(hub, serial)]
    if platform == "button":
        return [ClearCommands(hub, serial)]
    return [_ENTITY_CLASSES[platform](hub, serial, c) for c in CONTROLS if c.platform == platform]
