"""Base Ocular EVSE entity."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .client import OcularEvseClient
from .const import (
    DEVICE_DIAGNOSTICS,
    DEVICE_MAIN,
    DEVICE_ONCE_OFF,
    DEVICE_REPEATED,
    DOMAIN,
)

_RELATED_DEVICE_NAMES = {
    DEVICE_REPEATED: "Repeated charging",
    DEVICE_ONCE_OFF: "Once-off charging",
    DEVICE_DIAGNOSTICS: "Diagnostics",
}


class OcularEntity(Entity):
    _attr_has_entity_name = True

    def __init__(
        self,
        client: OcularEvseClient,
        key: str,
        device_group: str = DEVICE_MAIN,
    ) -> None:
        self.client = client
        self._device_group = device_group
        self._attr_unique_id = f"{client.address}_{key}"

    @property
    def available(self) -> bool:
        return self.client.state.authenticated

    @property
    def device_info(self) -> DeviceInfo:
        if self._device_group != DEVICE_MAIN:
            return DeviceInfo(
                identifiers={
                    (DOMAIN, f"{self.client.address}:{self._device_group}")
                },
                manufacturer="BESEN / Ocular",
                model="BS20 function",
                name=_RELATED_DEVICE_NAMES[self._device_group],
                via_device=(DOMAIN, self.client.address),
            )
        return DeviceInfo(
            identifiers={(DOMAIN, self.client.address)},
            connections={('bluetooth', self.client.address)},
            manufacturer="BESEN / Ocular",
            model="BS20",
            name="BESEN / Ocular EVSE",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.client.add_listener(self.async_write_ha_state))
