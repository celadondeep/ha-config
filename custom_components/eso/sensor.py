"""Sensor exposing the official ESO storage-bank ("pasaugojimas") balance.

The value comes straight from the portal's "Rodyti sukauptos energijos
kiekį" monthly series (see ESOClient.fetch_stored): the balance at the end
of the last closed month of the current bank year (Apr 1 – Mar 31). The
still-open month is always reported as 0 by ESO, so it is ignored; months
from a previous bank year are ignored too because that credit burned on
March 31.
"""

import logging

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import CONF_ID, CONF_NAME, UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import dt as dt_util

from .const import (
    CONF_RETURNED,
    SUBENTRY_TYPE_OBJECT,
    signal_outages_updated,
    signal_stored_updated,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> None:
    """Add a bank sensor per exporting object and the outages sensor."""
    async_add_entities([ESOOutagesSensor(entry)])
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_OBJECT:
            continue
        if not subentry.data.get(CONF_RETURNED):
            continue
        async_add_entities(
            [ESOStoredBankSensor(entry, subentry)],
            config_subentry_id=subentry.subentry_id,
        )


class ESOOutagesSensor(RestoreSensor):
    """Planned outages from the self-service dashboard block."""

    _attr_should_poll = False
    _attr_icon = "mdi:transmission-tower-off"

    def __init__(self, entry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_outages"
        self._attr_name = "ESO atjungimai"
        self._attr_extra_state_attributes = {}

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_sensor_data()) is not None:
            self._attr_native_value = last.native_value
        if (state := await self.async_get_last_state()) is not None:
            self._attr_extra_state_attributes = {
                key: state.attributes[key]
                for key in ("langai", "tekstas")
                if key in state.attributes
            }
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                signal_outages_updated(self._entry.entry_id),
                self._handle_update,
            )
        )
        self._handle_update()

    @callback
    def _handle_update(self) -> None:
        outages = self._entry.runtime_data.outages
        if not outages:
            return
        windows = outages.get("windows") or []
        if windows:
            w = windows[0]
            self._attr_native_value = f"{w['nuo']} – {w['iki'][-5:]}"
        else:
            self._attr_native_value = "nenumatoma"
        self._attr_extra_state_attributes = {
            "langai": windows,
            "tekstas": outages.get("raw", ""),
        }
        self.async_write_ha_state()


class ESOStoredBankSensor(RestoreSensor):
    """Official storage-bank balance for one metering object."""

    _attr_should_poll = False
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_device_class = SensorDeviceClass.ENERGY_STORAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:bank"

    def __init__(self, entry, subentry: ConfigSubentry) -> None:
        self._entry = entry
        self._obj_id: str = subentry.data[CONF_ID]
        self._obj_name: str = subentry.data.get(CONF_NAME, self._obj_id)
        self._attr_unique_id = f"{self._obj_id}_stored_bank"
        self._attr_name = f"ESO bankas {self._obj_id}"
        self._attr_extra_state_attributes = {}

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Data arrives once a day after the scheduled import; survive
        # restarts on the previously reported balance.
        if (last := await self.async_get_last_sensor_data()) is not None:
            self._attr_native_value = last.native_value
        if (state := await self.async_get_last_state()) is not None:
            self._attr_extra_state_attributes = {
                key: state.attributes[key]
                for key in ("menuo", "serija")
                if key in state.attributes
            }
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                signal_stored_updated(self._entry.entry_id),
                self._handle_update,
            )
        )
        self._handle_update()

    @callback
    def _handle_update(self) -> None:
        series = self._entry.runtime_data.stored.get(self._obj_id)
        if not series:
            return
        now = dt_util.now()
        bank_year_start = f"{now.year if now.month >= 4 else now.year - 1}-04"
        current_month = now.strftime("%Y-%m")
        closed = {
            month: value
            for month, value in series.items()
            if bank_year_start <= month < current_month
        }
        last_month = max(closed) if closed else None
        self._attr_native_value = closed[last_month] if last_month else 0.0
        self._attr_extra_state_attributes = {
            "menuo": last_month,
            "serija": series,
        }
        self.async_write_ha_state()
