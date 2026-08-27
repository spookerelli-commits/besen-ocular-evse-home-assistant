"""Asynchronous BLE client for an Ocular/EVSEMaster BS20."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import time

from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    BLE_WRITE_TIMEOUT_SECONDS, BLUETOOTH_PATH_RETRY_SECONDS,
    BLUETOOTH_PATH_STARTUP_GRACE_SECONDS, CONTROL_COOLDOWN_SECONDS,
    HEARTBEAT_TIMEOUT_SECONDS,
    MAX_CURRENT, MIN_CURRENT,
    LOGIN_RESPONSE_TIMEOUT_SECONDS, OPERATIONAL_STALE_SECONDS,
    OPERATIONAL_TIMEOUT_SECONDS, PACKET_QUEUE_MAXSIZE,
    RX_CHARACTERISTIC_UUID, TX_CHARACTERISTIC_UUID,
)
from .daily import roll_daily_counter
from .protocol import (
    CMD_AC_STATUS, CMD_AC_STATUS_ACK, CMD_AC_STATUS_ALTERNATE,
    CMD_CHARGE_START, CMD_CHARGE_START_RESPONSE,
    CMD_CHARGE_STATUS, CMD_CHARGE_STATUS_ALTERNATE, CMD_CHARGE_STOP,
    CMD_CHARGE_STATUS_ACK, CMD_CHARGE_STOP_RESPONSE, CMD_HEARTBEAT,
    CMD_HEARTBEAT_RESPONSE,
    CMD_MANUAL_CHARGING_RECORD, CMD_MANUAL_CHARGING_RECORD_ACK,
    CMD_SCHEDULED_CHARGING_RECORD, CMD_SCHEDULED_CHARGING_RECORD_ACK,
    CMD_LOGIN_BEACON, CMD_LOGIN_CONFIRM, CMD_LOGIN_REQUEST, CMD_LOGIN_RESPONSE,
    CMD_OUTPUT_CURRENT_RESPONSE, CMD_PASSWORD_ERROR, CMD_REQUEST_CHARGE_STATUS,
    CMD_REPEATED_SCHEDULE_RESPONSE, CMD_SET_GET_OUTPUT_CURRENT,
    CMD_SET_GET_REPEATED_SCHEDULE, PacketBuffer, build_packet, charge_start_payload,
    charge_stop_payload, charging_record_ack_payload, command_name,
    is_known_command, output_current_payload,
    packet_parts, parse_ac_status,
    parse_charge_status, parse_charging_record, parse_repeated_schedule,
    repeated_schedule_payload, repeated_schedule_records_payload,
    CMD_SET_TIME, CMD_SET_TIME_RESPONSE, set_time_payload,
)
from .session import SessionHealth

_LOGGER = logging.getLogger(__name__)

_SCHEDULE_DAY_NAMES = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _format_schedule_record(
    day: int, record: tuple[bool, int, int],
) -> str:
    """Format one charger schedule record."""
    enabled, start, duration = record
    stop = (start + duration) % (24 * 60)
    return (
        f"{_SCHEDULE_DAY_NAMES[day]}="
        f"{start // 60:02d}:{start % 60:02d}-"
        f"{stop // 60:02d}:{stop % 60:02d}"
        f"({'on' if enabled else 'off'})"
    )


def _format_schedule_records(
    records: tuple[tuple[bool, int, int], ...],
) -> str:
    """Format all seven charger schedule records for concise diagnostics."""
    return ", ".join(
        _format_schedule_record(day, record)
        for day, record in enumerate(records)
    )


@dataclass
class ChargerState:
    connected: bool = False
    authenticated: bool = False
    rssi: int | None = None
    status: str = "Unavailable"
    plug_state: str = "Unknown"
    output_state: str = "Unknown"
    protocol_state: str = "Unknown"
    raw_plug_state: int | None = None
    raw_output_state: int | None = None
    raw_protocol_state: int | None = None
    raw_plug_state_source: str = "None"
    raw_output_state_source: str = "None"
    raw_protocol_state_source: str = "None"
    power: int = 0
    total_energy: float = 0.0
    session_energy: float = 0.0
    session_duration: int = 0
    session_max_current: int = 0
    configured_current: int = 32
    schedule_available: bool = False
    schedule_enabled_days: tuple[bool, ...] = (False,) * 7
    schedule_start_minute: int = 0
    schedule_duration_minutes: int = 359
    schedule_start_minutes: tuple[int, ...] = (0,) * 7
    schedule_duration_minutes_by_day: tuple[int, ...] = (359,) * 7
    schedule_draft_enabled_days: tuple[bool, ...] = (False,) * 7
    schedule_draft_start_minutes: tuple[int, ...] = (0,) * 7
    schedule_draft_duration_minutes: tuple[int, ...] = (359,) * 7
    schedule_draft_dirty: bool = False
    once_delay_minutes: int = 0
    once_duration_minutes: int = 0
    once_energy_kwh: float = 0.0
    l1_voltage: float = 0.0
    l1_current: float = 0.0
    temperature: float | None = None
    emergency_state: int = 0
    error_bitfield: int = 0
    errors: str = "None"
    charge_id: str = ""
    last_command_result: str = "No command sent"
    connected_since: datetime | None = None
    last_packet_received: datetime | None = None
    last_operational_packet_received: datetime | None = None
    last_packet_type: str = "None"
    last_packet_command: int | None = None
    last_packet_payload_length: int = 0
    total_packet_count: int = 0
    operational_packet_count: int = 0
    login_beacon_count: int = 0
    consecutive_login_beacon_count: int = 0
    reauthentication_count: int = 0
    packet_command_counts: dict[str, int] = field(default_factory=dict)
    last_unknown_packet: str = "None"
    last_unknown_packet_command: int | None = None
    last_unknown_packet_payload_length: int = 0
    last_unknown_packet_received: datetime | None = None
    reconnect_count: int = 0
    reconnect_count_date: str = ""
    last_reconnect: datetime | None = None
    last_disconnect_reason: str = "None"
    last_connection_error: str = "None"
    last_connection_error_time: datetime | None = None
    schedule_last_verified: datetime | None = None
    last_charging_record: str = "None"
    last_charging_record_data: dict[str, object] = field(default_factory=dict)
    integration_health: str = "Starting"
    extra: dict[str, object] = field(default_factory=dict)


class OcularEvseClient:
    """Maintain one authenticated BLE session."""

    def __init__(self, hass: HomeAssistant, address: str, pin: str, user_id: str) -> None:
        self.hass = hass
        self.address = address
        self.pin = pin
        self.user_id = user_id
        self.state = ChargerState()
        self._client: BleakClientWithServiceCache | None = None
        self._serial: bytes | None = None
        self._buffer = PacketBuffer()
        self._listeners: set[Callable[[], None]] = set()
        self._charging_record_listeners: set[Callable[[dict[str, object]], None]] = set()
        self._seen_charging_records: set[str] = set()
        self._charging_records: list[dict[str, object]] = []
        storage_key = f"ocular_evse.{address.replace(':', '').lower()}_charging_records"
        self._record_store: Store[dict[str, object]] = Store(hass, 1, storage_key)
        diagnostics_key = f"ocular_evse.{address.replace(':', '').lower()}_diagnostics"
        self._diagnostics_store: Store[dict[str, object]] = Store(
            hass, 1, diagnostics_key
        )
        self._runner: asyncio.Task[None] | None = None
        self._packet_worker_task: asyncio.Task[None] | None = None
        self._packet_queue: asyncio.Queue[bytes] = asyncio.Queue(
            maxsize=PACKET_QUEUE_MAXSIZE
        )
        self._protocol_failed = asyncio.Event()
        self._protocol_error: Exception | None = None
        self._stop = asyncio.Event()
        self._write_lock = asyncio.Lock()
        self._schedule_lock = asyncio.Lock()
        self._schedule_response = asyncio.Event()
        self._schedule_refresh_response = asyncio.Event()
        self._schedule_expected: tuple[tuple[bool, int, int], ...] | None = None
        self._start_response = asyncio.Event()
        self._start_response_result: tuple[int, int, int] | None = None
        self._time_response = asyncio.Event()
        self._time_response_success: bool | None = None
        self._session_health = SessionHealth(
            packet_timeout=HEARTBEAT_TIMEOUT_SECONDS,
            operational_stale=OPERATIONAL_STALE_SECONDS,
            operational_timeout=OPERATIONAL_TIMEOUT_SECONDS,
            login_timeout=LOGIN_RESPONSE_TIMEOUT_SECONDS,
        )
        self._last_control = 0.0
        self._has_connected = False
        self._session_sync_done = False
        self._startup_grace_complete = False
        self._remove_midnight_listener: Callable[[], None] | None = None

    def add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.add(listener)
        return lambda: self._listeners.discard(listener)

    def add_charging_record_listener(
        self, listener: Callable[[dict[str, object]], None]
    ) -> Callable[[], None]:
        self._charging_record_listeners.add(listener)
        return lambda: self._charging_record_listeners.discard(listener)

    @property
    def charging_records(self) -> tuple[dict[str, object], ...]:
        return tuple(self._charging_records)

    async def load_charging_records(self) -> None:
        """Restore the last record and deduplication keys without replaying events."""
        stored = await self._record_store.async_load() or {}
        records = stored.get("records", [])
        if not isinstance(records, list):
            records = []
        self._charging_records = [r for r in records[-100:] if isinstance(r, dict)]
        for record in self._charging_records:
            record_id = str(record.get("charge_id") or "")
            if record_id:
                self._seen_charging_records.add(record_id)
        if self._charging_records:
            record = self._charging_records[-1]
            self.state.last_charging_record = str(
                record.get("charge_id") or "Unknown session"
            )
            self.state.last_charging_record_data = record
        diagnostics = await self._diagnostics_store.async_load() or {}
        today = dt_util.now().date().isoformat()
        if diagnostics.get("date") == today:
            self.state.reconnect_count = int(diagnostics.get("count", 0))
        self.state.reconnect_count_date = today
        last_reconnect = diagnostics.get("last_reconnect")
        if isinstance(last_reconnect, str):
            with suppress(ValueError):
                self.state.last_reconnect = datetime.fromisoformat(last_reconnect)

    def _save_diagnostics(self) -> None:
        self._diagnostics_store.async_delay_save(
            lambda: {
                "date": self.state.reconnect_count_date,
                "count": self.state.reconnect_count,
                "last_reconnect": (
                    self.state.last_reconnect.isoformat()
                    if self.state.last_reconnect else None
                ),
            },
            1,
        )

    def _roll_daily_reconnect_count(self) -> bool:
        """Roll the reconnect counter to the current local calendar day."""
        today = dt_util.now().date().isoformat()
        date, count, changed = roll_daily_counter(
            self.state.reconnect_count_date,
            self.state.reconnect_count,
            today,
        )
        if changed:
            self.state.reconnect_count_date = date
            self.state.reconnect_count = count
            self._save_diagnostics()
            return True
        return False

    def _handle_local_midnight(self, _now: datetime) -> None:
        """Publish the daily reconnect reset even on a continuously healthy link."""
        if self._roll_daily_reconnect_count():
            self._notify()

    def _publish_charging_record(self, record: dict[str, object]) -> None:
        record_id = str(record.get("charge_id") or "")
        dedupe_key = record_id or repr(sorted(record.items()))
        self.state.last_charging_record = record_id or "Unknown session"
        self.state.last_charging_record_data = record
        if dedupe_key in self._seen_charging_records:
            return
        self._seen_charging_records.add(dedupe_key)
        self._charging_records.append(record)
        self._charging_records = self._charging_records[-100:]
        self._record_store.async_delay_save(
            lambda: {"records": self._charging_records}, 1
        )
        for listener in tuple(self._charging_record_listeners):
            listener(record)

    def _notify(self) -> None:
        if self.state.raw_protocol_state == 14 and self.state.raw_output_state == 2:
            self.state.status = "Stopped by EV"
        elif self.state.output_state == "Charging":
            self.state.status = "Charging"
        else:
            self.state.status = self.state.protocol_state
        for listener in tuple(self._listeners):
            listener()

    async def start(self) -> None:
        if self._remove_midnight_listener is None:
            self._remove_midnight_listener = async_track_time_change(
                self.hass,
                self._handle_local_midnight,
                hour=0,
                minute=0,
                second=0,
            )
        if self._runner is None:
            self._runner = self.hass.async_create_background_task(self._run(), "ocular_evse_ble")

    async def stop(self) -> None:
        if self._remove_midnight_listener is not None:
            self._remove_midnight_listener()
            self._remove_midnight_listener = None
        self._stop.set()
        if self._runner:
            self._runner.cancel()
            with suppress(asyncio.CancelledError):
                await self._runner
            self._runner = None
        await self._disconnect()

    async def _run(self) -> None:
        while not self._stop.is_set():
            self._roll_daily_reconnect_count()
            disconnect_reason = "Bluetooth connection closed"
            connection_established = False
            try:
                await self._connect_and_watch()
                connection_established = self.state.connected
            except asyncio.CancelledError:
                raise
            except Exception as err:  # connection errors vary by proxy backend
                disconnect_reason = f"{type(err).__name__}: {err}"
                connection_established = self.state.connected
                _LOGGER.debug("Ocular EVSE connection ended: %s", disconnect_reason)
            self.state.connected = self.state.authenticated = False
            self.state.connected_since = None
            if connection_established:
                self.state.last_disconnect_reason = disconnect_reason
                self.state.integration_health = "Reconnecting"
            else:
                self.state.last_connection_error = disconnect_reason
                self.state.last_connection_error_time = datetime.now(timezone.utc)
                self.state.integration_health = "Waiting for Bluetooth path"
            self.state.status = "Unavailable"
            self._notify()
            await self._disconnect()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=15)
            except TimeoutError:
                pass

    async def _connect_and_watch(self) -> None:
        grace_deadline = time.monotonic() + (
            BLUETOOTH_PATH_STARTUP_GRACE_SECONDS
            if not self._startup_grace_complete else 0
        )
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        while ble_device is None and time.monotonic() < grace_deadline:
            self.state.integration_health = "Waiting for Bluetooth path"
            self._notify()
            try:
                await asyncio.wait_for(
                    self._stop.wait(), timeout=BLUETOOTH_PATH_RETRY_SECONDS
                )
                return
            except TimeoutError:
                pass
            ble_device = bluetooth.async_ble_device_from_address(
                self.hass, self.address, connectable=True
            )
        self._startup_grace_complete = True
        if ble_device is None:
            raise BleakError("No connectable Bluetooth path to charger")
        info = bluetooth.async_last_service_info(self.hass, self.address, connectable=True)
        self.state.rssi = info.rssi if info else None
        _LOGGER.debug("Connecting to Ocular EVSE via Bluetooth; RSSI=%s dBm", self.state.rssi)
        disconnected = asyncio.Event()
        self._protocol_failed.clear()
        self._protocol_error = None
        self._buffer = PacketBuffer()
        while not self._packet_queue.empty():
            self._packet_queue.get_nowait()
            self._packet_queue.task_done()
        self._session_sync_done = False
        self.state.authenticated = False
        self._client = await establish_connection(
            BleakClientWithServiceCache,
            ble_device,
            "BESEN / Ocular EVSE",
            disconnected_callback=lambda _c: self.hass.loop.call_soon_threadsafe(disconnected.set),
            max_attempts=3,
        )
        await self._client.start_notify(RX_CHARACTERISTIC_UUID, self._notification)
        self._packet_worker_task = self.hass.async_create_background_task(
            self._packet_worker(), "ocular_evse_packet_worker"
        )
        if self._has_connected:
            self._roll_daily_reconnect_count()
            self.state.reconnect_count += 1
            self.state.last_reconnect = datetime.now(timezone.utc)
            self._save_diagnostics()
        self._has_connected = True
        self.state.connected = True
        self.state.connected_since = datetime.now(timezone.utc)
        self.state.integration_health = "Connected; authenticating"
        self._session_health.connection_started(time.monotonic())
        _LOGGER.debug("Bluetooth connection established; notifications enabled")
        self._notify()
        while self._client.is_connected and not disconnected.is_set() and not self._stop.is_set():
            if self._protocol_failed.is_set():
                raise BleakError(
                    f"Protocol worker failed: {self._protocol_error or 'unknown error'}"
                )
            if reason := self._session_health.failure_reason(
                time.monotonic(), self.state.authenticated
            ):
                raise BleakError(reason)
            try:
                await asyncio.wait_for(disconnected.wait(), timeout=5)
            except TimeoutError:
                continue

    def _notification(self, _characteristic: object, data: bytearray) -> None:
        for packet in self._buffer.feed(bytes(data)):
            try:
                self._packet_queue.put_nowait(packet)
            except asyncio.QueueFull:
                self._protocol_error = BleakError("EVSE packet queue overflow")
                self._protocol_failed.set()

    async def _packet_worker(self) -> None:
        """Process complete packets strictly in their received order."""
        while True:
            packet = await self._packet_queue.get()
            try:
                await self._process_packet(packet)
            except asyncio.CancelledError:
                raise
            except Exception as err:
                self._protocol_error = err
                self._protocol_failed.set()
                _LOGGER.debug(
                    "Ocular EVSE protocol worker stopped: %s: %s",
                    type(err).__name__, err,
                )
                return
            finally:
                self._packet_queue.task_done()

    async def _process_packet(self, packet: bytes) -> None:
        serial, command, data = packet_parts(packet)
        self._serial = serial
        now_monotonic = time.monotonic()
        now_utc = datetime.now(timezone.utc)
        self._session_health.packet_received(now_monotonic)
        self.state.last_packet_received = now_utc
        self.state.last_packet_type = f"{command_name(command)} (0x{command:04X})"
        self.state.last_packet_command = command
        self.state.last_packet_payload_length = len(data)
        self.state.total_packet_count += 1
        command_key = f"0x{command:04X}"
        self.state.packet_command_counts[command_key] = (
            self.state.packet_command_counts.get(command_key, 0) + 1
        )
        if command == CMD_LOGIN_BEACON:
            self.state.login_beacon_count += 1
            self.state.consecutive_login_beacon_count += 1
        else:
            self.state.consecutive_login_beacon_count = 0
        if not is_known_command(command):
            self.state.last_unknown_packet = f"Unknown command (0x{command:04X})"
            self.state.last_unknown_packet_command = command
            self.state.last_unknown_packet_payload_length = len(data)
            self.state.last_unknown_packet_received = self.state.last_packet_received
        _LOGGER.debug("RX command=0x%04X payload_length=%d", command, len(data))
        live_operational = command in {
            CMD_HEARTBEAT, CMD_AC_STATUS, CMD_AC_STATUS_ALTERNATE,
            CMD_CHARGE_STATUS, CMD_CHARGE_STATUS_ALTERNATE,
        }
        authentication_evidence = live_operational or command in {
            CMD_CHARGE_START_RESPONSE, CMD_CHARGE_STOP_RESPONSE, CMD_OUTPUT_CURRENT_RESPONSE,
            CMD_REPEATED_SCHEDULE_RESPONSE, CMD_SET_TIME_RESPONSE,
        }
        recovering_login = live_operational and self._session_health.login_requested is not None
        if live_operational:
            self.state.operational_packet_count += 1
            self._session_health.operational_received(now_monotonic)
            self.state.last_operational_packet_received = now_utc
        if authentication_evidence and not self.state.authenticated:
            self.state.authenticated = True
            self.state.integration_health = "Healthy"
            _LOGGER.debug("Ocular EVSE session authenticated from operational traffic")
            await self._initial_sync()
        elif recovering_login:
            self._session_sync_done = False
            _LOGGER.debug("Ocular EVSE operational traffic resumed during reauthentication")
            await self._initial_sync()
        if command == CMD_LOGIN_BEACON:
            # Ignore isolated duplicate beacons while operational traffic is
            # healthy. If beacons continue after operational traffic stops,
            # request one guarded reauthentication instead of remaining stuck
            # or restarting the sync cycle on every beacon.
            if self._session_health.should_request_login(
                now_monotonic, self.state.authenticated
            ):
                recovering = self.state.authenticated
                self._session_health.mark_login_requested(
                    now_monotonic, recovering=recovering
                )
                if recovering:
                    self.state.reauthentication_count += 1
                    self._session_sync_done = False
                    self.state.last_command_result = (
                        "Operational traffic stale; requested EVSE reauthentication"
                    )
                    _LOGGER.debug(
                        "Login beacons continued after operational traffic stopped; "
                        "requesting guarded reauthentication"
                    )
                await self._send(CMD_LOGIN_REQUEST)
        elif command == CMD_LOGIN_RESPONSE:
            if (
                not self.state.authenticated
                or self._session_health.login_requested is not None
            ):
                await self._send(CMD_LOGIN_CONFIRM, b"\x01")
                self._session_health.login_succeeded(now_monotonic)
                self.state.authenticated = True
                self.state.integration_health = "Healthy"
                _LOGGER.debug("Ocular EVSE login accepted")
                await self._initial_sync()
        elif command == CMD_HEARTBEAT:
            await self._send(CMD_HEARTBEAT_RESPONSE, b"\x01")
        elif command in (CMD_AC_STATUS, CMD_AC_STATUS_ALTERNATE):
            for key, value in parse_ac_status(data).items():
                if hasattr(self.state, key):
                    setattr(self.state, key, value)
                else:
                    self.state.extra[key] = value
            source = f"{command_name(command)} (0x{command:04X})"
            self.state.raw_plug_state_source = source
            self.state.raw_output_state_source = source
            self.state.raw_protocol_state_source = source
            # Publish decoded measurements before a potentially slow BLE ACK.
            self._notify()
            if command == CMD_AC_STATUS:
                await self._send(CMD_AC_STATUS_ACK, b"\x00")
            return
        elif command in (CMD_CHARGE_STATUS, CMD_CHARGE_STATUS_ALTERNATE):
            for key, value in parse_charge_status(data).items():
                setattr(self.state, key, value)
            self.state.raw_protocol_state_source = (
                f"{command_name(command)} (0x{command:04X})"
            )
            # Publish session values before a potentially slow BLE ACK.
            self._notify()
            if command == CMD_CHARGE_STATUS:
                await self._send(CMD_CHARGE_STATUS_ACK, b"\x00")
            return
        elif command == CMD_OUTPUT_CURRENT_RESPONSE and len(data) >= 2:
            if MIN_CURRENT <= data[1] <= MAX_CURRENT:
                self.state.configured_current = data[1]
            self.state.last_command_result = f"Current response: action={data[0]}, current={data[1]} A"
        elif command == CMD_REPEATED_SCHEDULE_RESPONSE:
            schedule = parse_repeated_schedule(data)
            enabled_days = schedule["enabled_days"]
            self.state.schedule_enabled_days = enabled_days
            records = schedule["records"]
            starts = list(self.state.schedule_start_minutes)
            durations = list(self.state.schedule_duration_minutes_by_day)
            for day, record in enumerate(records):
                if record["enabled"] or not self.state.schedule_available:
                    starts[day] = int(record["start_minute"])
                    candidate_duration = int(record["duration_minutes"])
                    if 1 <= candidate_duration <= 24 * 60:
                        durations[day] = candidate_duration
            self.state.schedule_start_minutes = tuple(starts)
            self.state.schedule_duration_minutes_by_day = tuple(durations)
            # A disabled charger response clears its time fields. Preserve the
            # last desired times in memory so the schedule can be re-enabled.
            if any(enabled_days) or not self.state.schedule_available:
                self.state.schedule_start_minute = schedule["start_minute"]
                duration = schedule["duration_minutes"]
                if 1 <= duration <= 24 * 60:
                    self.state.schedule_duration_minutes = duration
            self.state.schedule_available = True
            if not self.state.schedule_draft_dirty:
                self._reset_schedule_draft()
            self.state.schedule_last_verified = datetime.now(timezone.utc)
            self.state.last_command_result = "Repeated schedule confirmed by charger"
            self._schedule_refresh_response.set()
            actual = tuple(
                (
                    bool(record["enabled"]),
                    int(record["start_minute"]),
                    int(record["duration_minutes"]),
                )
                for record in records
            )
            _LOGGER.debug(
                "Repeated schedule received: %s",
                _format_schedule_records(actual),
            )
            expected = self._schedule_expected
            if expected is not None:
                confirmed = all(
                    actual_day[0] == expected_day[0]
                    and (
                        not expected_day[0]
                        or actual_day[1:] == expected_day[1:]
                    )
                    for actual_day, expected_day in zip(actual, expected, strict=True)
                )
                if confirmed:
                    _LOGGER.debug("Repeated schedule confirmed: all 7 records matched")
                    self.state.schedule_draft_dirty = False
                    self._reset_schedule_draft()
                    self._schedule_response.set()
                else:
                    self.state.last_command_result = "Repeated schedule response did not match request"
                    mismatches = []
                    for day, (expected_day, actual_day) in enumerate(
                        zip(expected, actual, strict=True)
                    ):
                        if expected_day[0] != actual_day[0] or (
                            expected_day[0] and expected_day[1:] != actual_day[1:]
                        ):
                            mismatches.append(
                                f"requested {_format_schedule_record(day, expected_day)}; "
                                f"received {_format_schedule_record(day, actual_day)}"
                            )
                    _LOGGER.debug(
                        "Repeated schedule mismatch: %s", "; ".join(mismatches),
                    )
        elif command in (CMD_MANUAL_CHARGING_RECORD, CMD_SCHEDULED_CHARGING_RECORD):
            record = parse_charging_record(data, command)
            self._publish_charging_record(record)
            self.state.last_command_result = (
                f"Charging record received: {record['charge_id']}"
            )
            _LOGGER.debug("Charging record received: %s", record)
            self._notify()
            ack_command = (
                CMD_MANUAL_CHARGING_RECORD_ACK
                if command == CMD_MANUAL_CHARGING_RECORD
                else CMD_SCHEDULED_CHARGING_RECORD_ACK
            )
            await self._send(ack_command, charging_record_ack_payload(data))
            return
        elif command == CMD_CHARGE_START_RESPONSE and len(data) >= 5:
            self._start_response_result = (data[2], data[3], data[4])
            self.state.last_command_result = f"Start response: result={data[2]}, error={data[3]}, current={data[4]} A"
            self._start_response.set()
        elif command == CMD_CHARGE_STOP_RESPONSE and len(data) >= 3:
            self.state.last_command_result = f"Stop response: result={data[1]}, error={data[2]}"
        elif command == CMD_PASSWORD_ERROR:
            self.state.authenticated = False
            self.state.last_command_result = "Charger rejected the configured Bluetooth PIN"
        elif command == CMD_SET_TIME_RESPONSE:
            self._time_response_success = data[:1] == b"\x01"
            self.state.last_command_result = (
                "Charger clock synchronized"
                if self._time_response_success
                else "Charger rejected clock synchronization"
            )
            self._time_response.set()
        self._notify()

    async def _initial_sync(self) -> None:
        """Request initial state exactly once per BLE connection."""
        if self._session_sync_done:
            return
        self._session_sync_done = True
        try:
            await self._send(CMD_SET_GET_OUTPUT_CURRENT, output_current_payload())
            await self._send(CMD_REQUEST_CHARGE_STATUS)
            await self._send(CMD_SET_GET_REPEATED_SCHEDULE, repeated_schedule_payload())
        except Exception:
            self._session_sync_done = False
            raise

    async def _send(self, command: int, data: bytes = b"") -> None:
        if self._client is None or not self._client.is_connected or self._serial is None:
            raise BleakError("Charger is not connected")
        packet = build_packet(self._serial, self.pin, command, data)
        _LOGGER.debug("TX command=0x%04X payload_length=%d", command, len(data))
        async with self._write_lock:
            async with asyncio.timeout(BLE_WRITE_TIMEOUT_SECONDS):
                try:
                    await self._client.write_gatt_char(
                        TX_CHARACTERISTIC_UUID, packet, response=True
                    )
                except BleakError:
                    await self._client.write_gatt_char(
                        TX_CHARACTERISTIC_UUID, packet, response=False
                    )

    def _check_control(self) -> None:
        if not self.state.authenticated:
            raise BleakError("Charger is not authenticated")
        remaining = CONTROL_COOLDOWN_SECONDS - (time.monotonic() - self._last_control)
        if remaining > 0:
            raise BleakError(f"Control cooldown active for {remaining:.0f} seconds")
        self._last_control = time.monotonic()

    async def set_charging(self, enabled: bool) -> None:
        self._check_control()
        if enabled:
            await self._send(CMD_CHARGE_START, charge_start_payload(self.user_id, self.state.configured_current, datetime.now().astimezone()))
            self.state.last_command_result = f"Sent start request at {self.state.configured_current} A"
        else:
            await self._send(CMD_CHARGE_STOP, charge_stop_payload(self.user_id))
            self.state.last_command_result = "Sent stop request"
        self._notify()

    async def start_once_off_charging(self) -> None:
        """Start an immediate or delayed charger-stored once-off session."""
        self._check_control()
        self._start_response.clear()
        self._start_response_result = None
        await self._send(
            CMD_CHARGE_START,
            charge_start_payload(
                self.user_id,
                self.state.configured_current,
                datetime.now().astimezone(),
                delay_minutes=self.state.once_delay_minutes,
                duration_minutes=self.state.once_duration_minutes,
                energy_kwh=self.state.once_energy_kwh,
            ),
        )
        self.state.last_command_result = (
            "Sent once-off request: "
            f"delay={self.state.once_delay_minutes} min, "
            f"duration={self.state.once_duration_minutes or 'unlimited'} min, "
            f"energy={self.state.once_energy_kwh or 'unlimited'} kWh, "
            f"current={self.state.configured_current} A"
        )
        self._notify()
        try:
            await asyncio.wait_for(self._start_response.wait(), timeout=10)
        except TimeoutError as err:
            self.state.last_command_result = "Charger did not confirm the once-off request"
            self._notify()
            raise BleakError("Charger did not confirm the once-off request") from err
        result, error, _current = self._start_response_result or (0, -1, 0)
        if result != 1 or error != 0:
            message = (
                "Charger rejected the once-off request: "
                f"result={result}, error={error}"
            )
            self.state.last_command_result = message
            self._notify()
            raise BleakError(message)

    def set_once_off_value(self, key: str, value: float) -> None:
        if key == "once_delay_minutes":
            self.state.once_delay_minutes = round(value)
        elif key == "once_duration_minutes":
            self.state.once_duration_minutes = round(value)
        elif key == "once_energy_kwh":
            self.state.once_energy_kwh = round(value, 2)
        else:
            raise ValueError(f"Unsupported once-off setting: {key}")
        self._notify()

    async def set_current(self, amps: int) -> None:
        if not MIN_CURRENT <= amps <= MAX_CURRENT:
            raise ValueError("Current must be 6–32 A")
        await self._send(CMD_SET_GET_OUTPUT_CURRENT, output_current_payload(amps))
        self.state.configured_current = amps
        self.state.last_command_result = f"Requested current limit {amps} A"
        self._notify()

    async def set_repeated_schedule(
        self,
        *,
        start_minute: int | None = None,
        duration_minutes: int | None = None,
        enabled_days: tuple[bool, ...] | None = None,
    ) -> None:
        """Write the complete schedule and wait for the charger's echo."""
        if not self.state.authenticated:
            raise BleakError("Charger is not authenticated")
        start = self.state.schedule_start_minute if start_minute is None else start_minute
        duration = self.state.schedule_duration_minutes if duration_minutes is None else duration_minutes
        days = self.state.schedule_enabled_days if enabled_days is None else enabled_days
        records = tuple(
            (days[day], start, duration) for day in range(7)
        )
        await self._write_schedule_records(records)

    async def _write_schedule_records(
        self, records: tuple[tuple[bool, int, int], ...]
    ) -> None:
        """Write all daily records and require an exact enabled-record echo."""
        async with self._schedule_lock:
            _LOGGER.debug(
                "Repeated schedule requested: %s",
                _format_schedule_records(records),
            )
            self._schedule_response.clear()
            self._schedule_expected = records
            try:
                await self._send(
                    CMD_SET_GET_REPEATED_SCHEDULE,
                    repeated_schedule_records_payload(records),
                )
                await asyncio.wait_for(self._schedule_response.wait(), timeout=10)
            except TimeoutError as err:
                self.state.last_command_result = "Charger did not confirm the repeated schedule"
                _LOGGER.debug("Repeated schedule confirmation timed out")
                self._notify()
                raise BleakError("Charger did not confirm the repeated schedule") from err
            finally:
                self._schedule_expected = None

    def _reset_schedule_draft(self) -> None:
        self.state.schedule_draft_enabled_days = self.state.schedule_enabled_days
        self.state.schedule_draft_start_minutes = self.state.schedule_start_minutes
        self.state.schedule_draft_duration_minutes = (
            self.state.schedule_duration_minutes_by_day
        )
        self.state.schedule_draft_dirty = False

    def stage_schedule_day_enabled(self, day: int, enabled: bool) -> None:
        days = list(self.state.schedule_draft_enabled_days)
        days[day] = enabled
        self.state.schedule_draft_enabled_days = tuple(days)
        self.state.schedule_draft_dirty = True
        self._notify()

    def stage_schedule_day_time(
        self, day: int, *, start_minute: int | None = None,
        stop_minute: int | None = None,
    ) -> None:
        starts = list(self.state.schedule_draft_start_minutes)
        durations = list(self.state.schedule_draft_duration_minutes)
        if start_minute is not None:
            stop = (starts[day] + durations[day]) % (24 * 60)
            starts[day] = start_minute
            durations[day] = (stop - start_minute) % (24 * 60) or 24 * 60
        if stop_minute is not None:
            durations[day] = (stop_minute - starts[day]) % (24 * 60) or 24 * 60
        self.state.schedule_draft_start_minutes = tuple(starts)
        self.state.schedule_draft_duration_minutes = tuple(durations)
        self.state.schedule_draft_dirty = True
        self._notify()

    def stage_schedule_all_days_time(
        self, *, start_minute: int | None = None,
        stop_minute: int | None = None,
    ) -> None:
        """Stage one start or stop time across every weekday record."""
        starts = list(self.state.schedule_draft_start_minutes)
        durations = list(self.state.schedule_draft_duration_minutes)
        for day in range(7):
            if start_minute is not None:
                stop = (starts[day] + durations[day]) % (24 * 60)
                starts[day] = start_minute
                durations[day] = (stop - start_minute) % (24 * 60) or 24 * 60
            if stop_minute is not None:
                durations[day] = (
                    (stop_minute - starts[day]) % (24 * 60) or 24 * 60
                )
        self.state.schedule_draft_start_minutes = tuple(starts)
        self.state.schedule_draft_duration_minutes = tuple(durations)
        self.state.schedule_draft_dirty = True
        self._notify()

    async def apply_schedule_draft(self) -> None:
        records = tuple(
            (
                self.state.schedule_draft_enabled_days[day],
                self.state.schedule_draft_start_minutes[day],
                self.state.schedule_draft_duration_minutes[day],
            )
            for day in range(7)
        )
        await self._write_schedule_records(records)

    def discard_schedule_draft(self) -> None:
        self._reset_schedule_draft()
        self.state.last_command_result = "Discarded un-applied schedule changes"
        self._notify()

    async def refresh_schedule(self) -> None:
        if not self.state.authenticated:
            raise BleakError("Charger is not authenticated")
        self.state.schedule_draft_dirty = False
        self._schedule_refresh_response.clear()
        await self._send(
            CMD_SET_GET_REPEATED_SCHEDULE, repeated_schedule_payload()
        )
        try:
            await asyncio.wait_for(self._schedule_refresh_response.wait(), timeout=10)
        except TimeoutError as err:
            raise BleakError("Charger did not return its repeated schedule") from err

    async def set_schedule_enabled(self, enabled: bool) -> None:
        days = self.state.schedule_enabled_days
        if enabled:
            days = days if any(days) else (True,) * 7
        else:
            days = (False,) * 7
        records = tuple(
            (
                days[day],
                self.state.schedule_start_minutes[day],
                self.state.schedule_duration_minutes_by_day[day],
            )
            for day in range(7)
        )
        await self._write_schedule_records(records)

    async def set_schedule_day(self, day: int, enabled: bool) -> None:
        records = tuple(
            (
                enabled if index == day else self.state.schedule_enabled_days[index],
                self.state.schedule_start_minutes[index],
                self.state.schedule_duration_minutes_by_day[index],
            )
            for index in range(7)
        )
        await self._write_schedule_records(records)

    async def synchronize_time(self) -> None:
        """Set charger wall clock using the captured OCPP Set Tool command."""
        if not self.state.authenticated:
            raise BleakError("Charger is not authenticated")
        if self.state.raw_output_state == 1:
            raise BleakError("Charger clock can only be synchronized while idle")
        self._time_response.clear()
        self._time_response_success = None
        now = datetime.now().astimezone()
        await self._send(CMD_SET_TIME, set_time_payload(now))
        try:
            await asyncio.wait_for(self._time_response.wait(), timeout=10)
        except TimeoutError as err:
            self.state.last_command_result = "Charger did not confirm clock synchronization"
            self._notify()
            raise BleakError("Charger did not confirm clock synchronization") from err
        if not self._time_response_success:
            self._notify()
            raise BleakError("Charger rejected clock synchronization")

    async def _disconnect(self) -> None:
        self._session_sync_done = False
        worker, self._packet_worker_task = self._packet_worker_task, None
        if worker:
            worker.cancel()
            with suppress(asyncio.CancelledError):
                await worker
        client, self._client = self._client, None
        if client and client.is_connected:
            try:
                await client.disconnect()
            except Exception:
                pass
