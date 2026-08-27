"""Charging control for Ocular EVSE."""

from homeassistant.components.switch import SwitchEntity

from .const import DEVICE_REPEATED, DOMAIN
from .entity import OcularEntity


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    client = hass.data[DOMAIN][entry.entry_id]
    async_add_entities((
        OcularChargingSwitch(client),
        OcularScheduleEnabledSwitch(client),
        *(OcularScheduleDaySwitch(client, day) for day in range(7)),
    ))


class OcularChargingSwitch(OcularEntity, SwitchEntity):
    _attr_translation_key = "charging"
    _attr_icon = "mdi:ev-station"

    def __init__(self, client) -> None:
        super().__init__(client, "charging")

    @property
    def is_on(self) -> bool:
        # Protocol state 14 means that the charging session remains active.
        # Output state 2 within it is the EV-requested pause shown by
        # EVSEMaster as "Stop by EV", not a user-issued stop.
        return self.client.state.raw_protocol_state == 14

    async def async_turn_on(self, **kwargs) -> None:
        await self.client.set_charging(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.client.set_charging(False)


class OcularScheduleEnabledSwitch(OcularEntity, SwitchEntity):
    _attr_translation_key = "repeated_schedule"
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, client) -> None:
        super().__init__(client, "repeated_schedule", DEVICE_REPEATED)

    @property
    def available(self) -> bool:
        return super().available and self.client.state.schedule_available

    @property
    def is_on(self) -> bool:
        return any(self.client.state.schedule_enabled_days)

    async def async_turn_on(self, **kwargs) -> None:
        await self.client.set_schedule_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.client.set_schedule_enabled(False)


class OcularScheduleDaySwitch(OcularEntity, SwitchEntity):
    _attr_icon = "mdi:calendar-check"

    def __init__(self, client, day: int) -> None:
        super().__init__(client, f"schedule_day_{day}", DEVICE_REPEATED)
        self._day = day
        self._attr_translation_key = f"schedule_day_{day}"

    @property
    def available(self) -> bool:
        return super().available and self.client.state.schedule_available

    @property
    def is_on(self) -> bool:
        return self.client.state.schedule_draft_enabled_days[self._day]

    async def async_turn_on(self, **kwargs) -> None:
        self.client.stage_schedule_day_enabled(self._day, True)

    async def async_turn_off(self, **kwargs) -> None:
        self.client.stage_schedule_day_enabled(self._day, False)
