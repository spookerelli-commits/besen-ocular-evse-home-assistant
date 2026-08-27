"""Repeated-schedule time controls for Ocular EVSE."""

from datetime import time

from homeassistant.components.time import TimeEntity

from .const import DEVICE_REPEATED, DOMAIN
from .entity import OcularEntity


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    client = hass.data[DOMAIN][entry.entry_id]
    async_add_entities((
        OcularScheduleTime(client, False), OcularScheduleTime(client, True),
        *(OcularDailyScheduleTime(client, day, is_stop) for day in range(7) for is_stop in (False, True)),
    ))


class OcularScheduleTime(OcularEntity, TimeEntity):
    _attr_icon = "mdi:clock-outline"

    def __init__(self, client, is_stop: bool) -> None:
        key = "schedule_stop" if is_stop else "schedule_start"
        super().__init__(client, key, DEVICE_REPEATED)
        self._is_stop = is_stop
        self._attr_translation_key = key

    @property
    def available(self) -> bool:
        return super().available and self.client.state.schedule_available

    @property
    def native_value(self) -> time:
        minute = self.client.state.schedule_draft_start_minutes[0]
        if self._is_stop:
            minute = (
                minute + self.client.state.schedule_draft_duration_minutes[0]
            ) % (24 * 60)
        return time(hour=minute // 60, minute=minute % 60)

    async def async_set_value(self, value: time) -> None:
        new_minute = value.hour * 60 + value.minute
        if self._is_stop:
            self.client.stage_schedule_all_days_time(stop_minute=new_minute)
        else:
            self.client.stage_schedule_all_days_time(start_minute=new_minute)


class OcularDailyScheduleTime(OcularEntity, TimeEntity):
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, client, day: int, is_stop: bool) -> None:
        key = f"schedule_day_{day}_{'stop' if is_stop else 'start'}"
        super().__init__(client, key, DEVICE_REPEATED)
        self._day = day
        self._is_stop = is_stop
        self._attr_translation_key = key

    @property
    def available(self) -> bool:
        return super().available and self.client.state.schedule_available

    @property
    def native_value(self) -> time:
        minute = self.client.state.schedule_draft_start_minutes[self._day]
        if self._is_stop:
            minute = (
                minute + self.client.state.schedule_draft_duration_minutes[self._day]
            ) % (24 * 60)
        return time(hour=minute // 60, minute=minute % 60)

    async def async_set_value(self, value: time) -> None:
        minute = value.hour * 60 + value.minute
        if self._is_stop:
            self.client.stage_schedule_day_time(self._day, stop_minute=minute)
        else:
            self.client.stage_schedule_day_time(self._day, start_minute=minute)
