"""Configured start current control for Ocular EVSE."""

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import UnitOfElectricCurrent, UnitOfEnergy, UnitOfTime

from .const import DEVICE_ONCE_OFF, DOMAIN, MAX_CURRENT, MIN_CURRENT
from .entity import OcularEntity


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    client = hass.data[DOMAIN][entry.entry_id]
    async_add_entities((
        OcularCurrentNumber(client),
        OcularOnceOffNumber(client, "once_delay_minutes", 0, 1440, 1),
        OcularOnceOffNumber(client, "once_duration_minutes", 0, 1440, 1),
        OcularOnceOffNumber(client, "once_energy_kwh", 0, 100, 0.1),
    ))


class OcularCurrentNumber(OcularEntity, NumberEntity):
    _attr_translation_key = "start_current"
    _attr_native_min_value = MIN_CURRENT
    _attr_native_max_value = MAX_CURRENT
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_device_class = NumberDeviceClass.CURRENT
    _attr_mode = NumberMode.BOX

    def __init__(self, client) -> None:
        super().__init__(client, "start_current")

    @property
    def native_value(self) -> float:
        return self.client.state.configured_current

    async def async_set_native_value(self, value: float) -> None:
        await self.client.set_current(round(value))


class OcularOnceOffNumber(OcularEntity, NumberEntity):
    _attr_mode = NumberMode.BOX
    _attr_entity_category = None

    def __init__(self, client, key: str, minimum: float, maximum: float, step: float) -> None:
        super().__init__(client, key, DEVICE_ONCE_OFF)
        self._key = key
        self._attr_translation_key = key
        self._attr_native_min_value = minimum
        self._attr_native_max_value = maximum
        self._attr_native_step = step
        if key.endswith("minutes"):
            self._attr_native_unit_of_measurement = UnitOfTime.MINUTES
            self._attr_icon = "mdi:timer-outline"
        else:
            self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
            self._attr_icon = "mdi:lightning-bolt"

    @property
    def native_value(self) -> float:
        return getattr(self.client.state, self._key)

    async def async_set_native_value(self, value: float) -> None:
        self.client.set_once_off_value(self._key, value)
