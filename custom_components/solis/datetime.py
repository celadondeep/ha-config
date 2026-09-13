"""Confirmed single-slot Solis datetime controls."""
from .const import DOMAIN


async def async_setup_entry(hass, config_entry, async_add_entities):
    service = hass.data[DOMAIN][config_entry.entry_id]
    if service.confirmed_hub:
        service.confirmed_hub.register_platform("datetime", async_add_entities)
