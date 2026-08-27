"""Ocular EVSE integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .client import OcularEvseClient
from .const import CONF_PIN, CONF_USER_ID, DEFAULT_USER_ID, DOMAIN, PLATFORMS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    client = OcularEvseClient(
        hass, entry.data["address"], entry.data[CONF_PIN], entry.data.get(CONF_USER_ID, DEFAULT_USER_ID)
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = client
    await client.load_charging_records()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await client.start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    client = hass.data[DOMAIN].pop(entry.entry_id)
    await client.stop()
    return True
