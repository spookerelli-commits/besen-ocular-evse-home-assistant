"""Safe explicit actions for Ocular EVSE."""

from homeassistant.components.button import ButtonEntity

from .const import DEVICE_ONCE_OFF, DEVICE_REPEATED, DOMAIN
from .entity import OcularEntity


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    client = hass.data[DOMAIN][entry.entry_id]
    async_add_entities((
        OcularActionButton(client, "apply_schedule", client.apply_schedule_draft, DEVICE_REPEATED),
        OcularActionButton(client, "discard_schedule", client.discard_schedule_draft, DEVICE_REPEATED),
        OcularActionButton(client, "refresh_schedule", client.refresh_schedule, DEVICE_REPEATED),
        OcularActionButton(client, "start_once_off", client.start_once_off_charging, DEVICE_ONCE_OFF),
        OcularActionButton(client, "synchronize_time", client.synchronize_time),
    ))


class OcularActionButton(OcularEntity, ButtonEntity):
    def __init__(self, client, key, action, device_group="main") -> None:
        super().__init__(client, key, device_group)
        self._attr_translation_key = key
        self._action = action

    async def async_press(self) -> None:
        result = self._action()
        if hasattr(result, "__await__"):
            await result
