"""Binary sensors for Ocular EVSE."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.helpers.entity import EntityCategory

from .const import DEVICE_DIAGNOSTICS, DOMAIN
from .entity import OcularEntity


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    client = hass.data[DOMAIN][entry.entry_id]
    async_add_entities((
        OcularProblem(client), OcularBluetoothConnected(client), OcularPlugConnected(client)
    ))


class OcularProblem(OcularEntity, BinarySensorEntity):
    _attr_translation_key = "problem"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, client) -> None:
        super().__init__(client, "problem", DEVICE_DIAGNOSTICS)

    @property
    def is_on(self) -> bool:
        return self.client.state.error_bitfield != 0


class OcularBluetoothConnected(OcularEntity, BinarySensorEntity):
    _attr_translation_key = "bluetooth_connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, client) -> None:
        super().__init__(client, "bluetooth_connected", DEVICE_DIAGNOSTICS)

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self.client.state.connected and self.client.state.authenticated


class OcularPlugConnected(OcularEntity, BinarySensorEntity):
    _attr_translation_key = "plug_connected"
    _attr_device_class = BinarySensorDeviceClass.PLUG
    _attr_icon = "mdi:ev-plug-type2"

    def __init__(self, client) -> None:
        super().__init__(client, "plug_connected")

    @property
    def is_on(self) -> bool:
        return self.client.state.raw_plug_state in (2, 3, 4)
