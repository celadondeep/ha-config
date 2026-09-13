"""The Solis Inverter integration."""

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import ATTR_NAME, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CONTROL,
    CONF_KEY_ID,
    CONF_PASSWORD,
    CONF_PLANT_ID,
    CONF_PORTAL_DOMAIN,
    CONF_REFRESH_NOK,
    CONF_REFRESH_OK,
    CONF_SECRET,
    CONF_USERNAME,
    DOMAIN,
)
from .ginlong_base import PortalConfig
from .service import InverterService
from .soliscloud_api import SoliscloudConfig

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.SENSOR,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.TIME,
    Platform.BUTTON,
]

CONTROL_PLATFORMS = [
    Platform.SELECT,
    Platform.NUMBER,
    Platform.TIME,
    Platform.BUTTON,
]


async def async_setup(hass: HomeAssistant, config: ConfigType):
    """Set up the Solis component from configuration.yaml."""

    if "sensor" not in config:
        return True

    for entry in config["sensor"]:
        try:
            if DOMAIN.lower() == entry["platform"]:
                async_create_issue(
                    hass,
                    DOMAIN,
                    "deprecated_yaml",
                    breaks_in_ha_version="2023.2.0",
                    is_fixable=False,
                    severity=IssueSeverity.WARNING,
                    translation_key="deprecated_yaml",
                )
        except (TypeError, KeyError):
            continue
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up platform from a ConfigEntry."""

    hass.data.setdefault(DOMAIN, {})

    config = entry.data

    portal_domain = config[CONF_PORTAL_DOMAIN]
    portal_plantid = config[CONF_PLANT_ID]
    portal_username = config[CONF_USERNAME]
    portal_control = False
    portal_password = None
    try:
        portal_control = config[CONF_CONTROL]
        if portal_control:
            portal_password = config[CONF_PASSWORD]
    except KeyError:
        pass

    portal_config: PortalConfig | None = None
    portal_key_id = config[CONF_KEY_ID]
    portal_secret: bytes = bytes(config[CONF_SECRET], "utf-8")
    portal_config = SoliscloudConfig(
        portal_domain,
        portal_username,
        portal_key_id,
        portal_secret,
        portal_plantid,
        portal_password,
    )

    # Initialize the Ginlong data service.
    refresh_ok = 300
    refresh_error = 60
    try:
        # Fixme: https://github.com/hultenvp/solis-sensor/issues/496
        refresh_ok = config[CONF_REFRESH_OK]
        refresh_error = config[CONF_REFRESH_NOK]
    except KeyError:
        pass
    single_slot_control = bool(config.get("single_slot_control", False))
    if single_slot_control:
        logging.getLogger("custom_components.solis.cloud_diagnostics").setLevel(logging.INFO)
    service: InverterService = InverterService(
        portal_config, hass, refresh_ok, refresh_error,
        **({"max_discovery_delay": 300} if single_slot_control else {}),
    )
    if single_slot_control and portal_control:
        from .confirmed_hub import ConfirmedControlHub
        service.api._single_slot_control = True
        service.api.health.hold_startup()
        service.confirmed_hub = ConfirmedControlHub(hass, entry, service)
        service._schedule_ok = max(300, refresh_ok)
        service._schedule_nok = max(300, refresh_error)
    hass.data[DOMAIN][entry.entry_id] = service

    control_platforms = (
        [Platform.SELECT, Platform.NUMBER, Platform.SWITCH, Platform.TEXT, Platform.DATETIME, Platform.BUTTON]
        if service.confirmed_hub else CONTROL_PLATFORMS
    )
    service.loaded_platforms = [Platform.SENSOR, *control_platforms] if portal_control else [Platform.SENSOR]
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    # Forward the setup to the sensor platform.
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
    # while not service.discovery_complete:
    #     asyncio.sleep(1)
    _LOGGER.debug("Sensor setup complete")
    if portal_control:
        await hass.config_entries.async_forward_entry_setups(entry, control_platforms)
    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""

    service = hass.data[DOMAIN][entry.entry_id]
    # Options may already contain a new control flag; unload what was loaded.
    await service.shutdown()
    unload_ok = await hass.config_entries.async_unload_platforms(entry, service.loaded_platforms)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
