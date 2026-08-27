"""EVSEMaster/BS20 protocol codec.

Ported from spudstuff/HA-ESP32-Ocular-EVSE under GPL-3.0.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import random

CMD_LOGIN_BEACON = 0x0001
CMD_LOGIN_RESPONSE = 0x0002
CMD_HEARTBEAT = 0x0003
CMD_AC_STATUS = 0x0004
CMD_CHARGE_STATUS = 0x0005
CMD_CHARGE_STATUS_ALTERNATE = 0x0006
CMD_CHARGE_START_RESPONSE = 0x0007
CMD_CHARGE_STOP_RESPONSE = 0x0008
CMD_MANUAL_CHARGING_RECORD = 0x0009
CMD_SCHEDULED_CHARGING_RECORD = 0x000A
CMD_AC_STATUS_ALTERNATE = 0x000D
CMD_OUTPUT_CURRENT_RESPONSE = 0x0107
CMD_REPEATED_SCHEDULE_RESPONSE = 0x010E
CMD_SET_TIME_RESPONSE = 0x0207
CMD_PASSWORD_ERROR = 0x0155

CMD_LOGIN_REQUEST = 0x8002
CMD_LOGIN_CONFIRM = 0x8001
CMD_HEARTBEAT_RESPONSE = 0x8003
CMD_AC_STATUS_ACK = 0x8004
CMD_CHARGE_STATUS_ACK = 0x8005
CMD_CHARGE_START = 0x8007
CMD_CHARGE_STOP = 0x8008
CMD_MANUAL_CHARGING_RECORD_ACK = 0x8009
CMD_SCHEDULED_CHARGING_RECORD_ACK = 0x800A
CMD_REQUEST_CHARGE_STATUS = 0x800D
CMD_SET_GET_OUTPUT_CURRENT = 0x8107
CMD_SET_GET_REPEATED_SCHEDULE = 0x810E
CMD_SET_TIME = 0x8207

COMMAND_NAMES = {
    CMD_LOGIN_BEACON: "Login beacon",
    CMD_LOGIN_RESPONSE: "Login response",
    CMD_HEARTBEAT: "Heartbeat",
    CMD_AC_STATUS: "AC status",
    CMD_CHARGE_STATUS: "Charging status",
    CMD_CHARGE_STATUS_ALTERNATE: "Charging status (alternate)",
    CMD_CHARGE_START_RESPONSE: "Charge start response",
    CMD_CHARGE_STOP_RESPONSE: "Charge stop response",
    CMD_MANUAL_CHARGING_RECORD: "Manual charging record",
    CMD_SCHEDULED_CHARGING_RECORD: "Scheduled charging record",
    CMD_AC_STATUS_ALTERNATE: "AC status (alternate)",
    CMD_OUTPUT_CURRENT_RESPONSE: "Current response",
    CMD_REPEATED_SCHEDULE_RESPONSE: "Repeated schedule response",
    CMD_SET_TIME_RESPONSE: "Set time response",
    CMD_PASSWORD_ERROR: "Password error",
}

SCHEDULE_DAY_COUNT = 7
SCHEDULE_RECORD_SIZE = 9
SCHEDULE_DISABLED = 1
SCHEDULE_ENABLED = 3


def u16(data: bytes, offset: int = 0) -> int:
    return int.from_bytes(data[offset : offset + 2], "big")


def command_name(command: int) -> str:
    return COMMAND_NAMES.get(command, "Unknown command")


def is_known_command(command: int) -> bool:
    return command in COMMAND_NAMES


def u32(data: bytes, offset: int = 0) -> int:
    return int.from_bytes(data[offset : offset + 4], "big")


def validate_packet(packet: bytes) -> bool:
    if len(packet) < 25 or packet[:2] != b"\x06\x01":
        return False
    if u16(packet, 2) != len(packet) or packet[-2:] != b"\x0f\x02":
        return False
    return u16(packet, len(packet) - 4) == sum(packet[:-4]) % 0xFFFF


def build_packet(serial: bytes, pin: str, command: int, data: bytes = b"") -> bytes:
    if len(serial) != 8:
        raise ValueError("serial must contain 8 bytes")
    pin_bytes = pin.encode("ascii")
    if len(pin_bytes) != 6:
        raise ValueError("PIN must contain exactly 6 ASCII characters")
    packet = bytearray(25 + len(data))
    packet[:2] = b"\x06\x01"
    packet[2:4] = len(packet).to_bytes(2, "big")
    packet[5:13] = serial
    packet[13:19] = pin_bytes
    packet[19:21] = command.to_bytes(2, "big")
    packet[21 : 21 + len(data)] = data
    packet[-4:-2] = (sum(packet[:-4]) % 0xFFFF).to_bytes(2, "big")
    packet[-2:] = b"\x0f\x02"
    return bytes(packet)


class PacketBuffer:
    """Reassemble packets split across BLE notifications."""

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, fragment: bytes) -> list[bytes]:
        self._buffer.extend(fragment)
        packets: list[bytes] = []
        while True:
            while len(self._buffer) >= 2 and self._buffer[:2] != b"\x06\x01":
                del self._buffer[0]
            if len(self._buffer) < 4:
                break
            length = u16(self._buffer, 2)
            if length < 25 or length > 2048:
                del self._buffer[0]
                continue
            if len(self._buffer) < length:
                break
            packet = bytes(self._buffer[:length])
            del self._buffer[:length]
            if validate_packet(packet):
                packets.append(packet)
        return packets


def packet_parts(packet: bytes) -> tuple[bytes, int, bytes]:
    if not validate_packet(packet):
        raise ValueError("invalid EVSEMaster packet")
    return packet[5:13], u16(packet, 19), packet[21:-4]


PLUG_STATES = {
    1: "Disconnected",
    2: "Connected unlocked",
    3: "Negotiating",
    4: "Connected locked",
}
OUTPUT_STATES = {1: "Charging", 2: "Idle"}
PROTOCOL_STATES = {
    0: "Fault", 1: "Charging fault 1", 2: "Charging fault", 3: "Charging fault",
    9: "Waiting for swipe", 10: "Waiting for swipe", 11: "Waiting for button",
    12: "Not connected", 13: "Ready to charge", 14: "Charging", 15: "Completed",
    17: "Completed full charge", 20: "Charging reservation",
}
ERROR_NAMES = {
    0: "Relay stuck error", 1: "Relay stuck error", 2: "Relay stuck error", 3: "Offline",
    4: "CC error", 5: "CP error", 6: "Emergency stop", 7: "Over temperature",
    8: "Over temperature", 10: "Leakage protection", 11: "Short circuit",
    12: "Over current", 13: "Ungrounded", 14: "Over voltage", 15: "Low voltage",
    25: "Input power error", 26: "DLB mains overload", 27: "Diode short circuit",
    28: "RTC failure", 29: "Flash memory failure", 30: "EEPROM failure",
    31: "Metering module failure",
}


def error_text(bits: int) -> str:
    if not bits:
        return "None"
    return ", ".join(ERROR_NAMES.get(bit, f"Unknown error bit {bit}") for bit in range(32) if bits & (1 << bit))


def parse_ac_status(data: bytes) -> dict[str, object]:
    if len(data) < 25:
        raise ValueError("short AC status payload")
    raw_temp = u16(data, 13)
    result: dict[str, object] = {
        "l1_voltage": u16(data, 1) * 0.1,
        "l1_current": u16(data, 3) * 0.01,
        "power": u32(data, 5),
        "total_energy": u32(data, 9) * 0.01,
        "temperature": None if raw_temp == 0xFFFF else (raw_temp - 20000) * 0.01,
        "emergency_state": data[17],
        "plug_state": PLUG_STATES.get(data[18], f"Unknown ({data[18]})"),
        "output_state": OUTPUT_STATES.get(data[19], f"Unknown ({data[19]})"),
        "protocol_state": PROTOCOL_STATES.get(data[20], f"Unknown ({data[20]})"),
        "raw_plug_state": data[18],
        "raw_output_state": data[19],
        "raw_protocol_state": data[20],
        "error_bitfield": u32(data, 21),
    }
    result["errors"] = error_text(int(result["error_bitfield"]))
    if len(data) >= 33:
        result.update({
            "l2_voltage": u16(data, 25) * 0.1, "l2_current": u16(data, 27) * 0.01,
            "l3_voltage": u16(data, 29) * 0.1, "l3_current": u16(data, 31) * 0.01,
        })
    return result


def parse_charge_status(data: bytes) -> dict[str, object]:
    if len(data) < 74:
        raise ValueError("short charge status payload")
    state = data[1]
    return {
        "protocol_state": PROTOCOL_STATES.get(state, f"Unknown ({state})"),
        "raw_protocol_state": state,
        "charge_id": data[2:18].rstrip(b"\0").decode("ascii", errors="replace"),
        "session_max_current": data[46],
        "session_duration": u32(data, 51),
        "session_energy": u32(data, 63) * 0.01,
    }


def _record_text(data: bytes) -> str:
    """Decode a fixed-width, space/NUL-padded charging-record string."""
    return data.rstrip(b"\0 ").decode("ascii", errors="replace")


def parse_charging_record(data: bytes, command: int = CMD_SCHEDULED_CHARGING_RECORD) -> dict[str, object]:
    """Decode an EVSEMaster manual or scheduled charging record.

    Offsets and scaling are verified against the Android HCI capture.  The
    charger represents energy as hundredths of a kWh and times as Unix-like
    32-bit values.  Raw timestamps are retained alongside ISO UTC renderings
    because charger firmware may encode its configured wall-clock timezone.
    """
    if len(data) < 88:
        raise ValueError("short charging record payload")
    start_timestamp = u32(data, 64)
    end_timestamp = u32(data, 68)

    def charger_wall_time(value: int) -> str | None:
        if not value:
            return None
        # Firmware stores its wall clock as an epoch based on a fixed UTC+8
        # convention.  Render the intended wall time without asking HA to
        # reinterpret the instant in its own timezone.
        return (
            datetime.fromtimestamp(value, timezone.utc) + timedelta(hours=8)
        ).strftime("%Y-%m-%d %H:%M:%S")

    manual = command == CMD_MANUAL_CHARGING_RECORD
    if command not in (CMD_MANUAL_CHARGING_RECORD, CMD_SCHEDULED_CHARGING_RECORD):
        raise ValueError(f"unsupported charging record command 0x{command:04X}")

    return {
        "record_type": "manual" if manual else "scheduled",
        "source_command": f"0x{command:04X}",
        "record_header_value": data[0],
        "user_id": _record_text(data[1:17]),
        "stop_user_id": _record_text(data[17:33]) if manual else None,
        "termination_reason": None if manual else _record_text(data[17:33]),
        "charge_id": _record_text(data[33:49]),
        "raw_record_flags": data[49:52].hex(),
        "raw_mode_value": data[58],
        "raw_phase_or_source_value": data[59],
        "start_timestamp": start_timestamp,
        "end_timestamp": end_timestamp,
        "start_time": charger_wall_time(start_timestamp),
        "end_time": charger_wall_time(end_timestamp),
        "duration_seconds": u32(data, 72),
        "meter_start_kwh": round(u32(data, 76) * 0.01, 2),
        "meter_end_kwh": round(u32(data, 80) * 0.01, 2),
        "session_energy_kwh": round(u32(data, 84) * 0.01, 2),
        "payload_length": len(data),
        "raw_payload": data.hex(),
    }


def charging_record_ack_payload(data: bytes) -> bytes:
    """Build the 0x8009/0x800A acknowledgement observed from EVSEMaster."""
    if len(data) < 49:
        raise ValueError("short charging record payload")
    return bytes((data[0],)) + data[33:49] + b"\x01"


def output_current_payload(amps: int | None = None) -> bytes:
    # EVSEMaster sends three bytes for both reads and writes.  The final 0x0B
    # is constant across captured 10 A and 32 A writes.
    return bytes((2, 0, 0)) if amps is None else bytes((1, amps, 0x0B))


def repeated_schedule_payload(
    start_minute: int | None = None,
    duration_minutes: int | None = None,
    enabled_days: tuple[bool, ...] | None = None,
) -> bytes:
    """Build a get or set payload for the charger's seven-day schedule.

    The weekday order observed in EVSEMaster is Monday through Sunday. Each
    nine-byte record is status, start minute, duration, and four reserved bytes.
    """
    if start_minute is None and duration_minutes is None and enabled_days is None:
        return bytes((2,)) + bytes(SCHEDULE_DAY_COUNT * SCHEDULE_RECORD_SIZE)
    if start_minute is None or not 0 <= start_minute < 24 * 60:
        raise ValueError("Schedule start must be between 00:00 and 23:59")
    if duration_minutes is None or not 1 <= duration_minutes <= 24 * 60:
        raise ValueError("Schedule duration must be between 1 minute and 24 hours")
    if enabled_days is None or len(enabled_days) != SCHEDULE_DAY_COUNT:
        raise ValueError("Schedule must contain seven weekday selections")
    payload = bytearray((1,))
    for enabled in enabled_days:
        payload.append(SCHEDULE_ENABLED if enabled else SCHEDULE_DISABLED)
        # EVSEMaster clears the time fields for unselected weekdays.
        payload.extend((start_minute if enabled else 0).to_bytes(2, "big"))
        payload.extend((duration_minutes if enabled else 0).to_bytes(2, "big"))
        payload.extend(b"\xff" * 4)
    return bytes(payload)


def repeated_schedule_records_payload(
    records: tuple[tuple[bool, int, int], ...],
) -> bytes:
    """Build a complete seven-record schedule preserving independent times."""
    if len(records) != SCHEDULE_DAY_COUNT:
        raise ValueError("Schedule must contain seven daily records")
    payload = bytearray((1,))
    for enabled, start_minute, duration_minutes in records:
        if not 0 <= start_minute < 24 * 60:
            raise ValueError("Schedule start must be between 00:00 and 23:59")
        if not 1 <= duration_minutes <= 24 * 60:
            raise ValueError("Schedule duration must be between 1 minute and 24 hours")
        payload.append(SCHEDULE_ENABLED if enabled else SCHEDULE_DISABLED)
        payload.extend((start_minute if enabled else 0).to_bytes(2, "big"))
        payload.extend((duration_minutes if enabled else 0).to_bytes(2, "big"))
        payload.extend(b"\xff" * 4)
    return bytes(payload)


def parse_repeated_schedule(data: bytes) -> dict[str, object]:
    """Decode the echoed set/get response for a repeated schedule."""
    expected = 1 + SCHEDULE_DAY_COUNT * SCHEDULE_RECORD_SIZE
    if len(data) < expected or data[0] not in (1, 2):
        raise ValueError("invalid repeated schedule payload")
    records: list[dict[str, int | bool]] = []
    for day in range(SCHEDULE_DAY_COUNT):
        offset = 1 + day * SCHEDULE_RECORD_SIZE
        records.append({
            "enabled": data[offset] == SCHEDULE_ENABLED,
            "status": data[offset],
            "start_minute": u16(data, offset + 1),
            "duration_minutes": u16(data, offset + 3),
        })
    enabled_days = tuple(bool(record["enabled"]) for record in records)
    representative = next((record for record in records if record["enabled"]), records[0])
    return {
        "action": data[0],
        "enabled_days": enabled_days,
        "start_minute": int(representative["start_minute"]),
        "duration_minutes": int(representative["duration_minutes"]),
        "records": records,
    }


def _evse_timestamp(now: datetime) -> int:
    offset = now.utcoffset()
    local_offset = int(offset.total_seconds()) if offset else 0
    return int(now.timestamp()) + local_offset - 8 * 3600


def charge_start_payload(
    user_id: str,
    amps: int,
    now: datetime | None = None,
    *,
    delay_minutes: int = 0,
    duration_minutes: int = 0,
    energy_kwh: float = 0,
) -> bytes:
    """Build the captured 47-byte manual/once-off charging request.

    EVSEMaster represents delayed start as an absolute charger-wall-clock
    timestamp. A zero duration or energy uses 0xFFFF (unlimited).
    """
    now = now or datetime.now().astimezone()
    if not 0 <= delay_minutes <= 24 * 60:
        raise ValueError("Delay must be between 0 and 24 hours")
    if not 0 <= duration_minutes <= 24 * 60:
        raise ValueError("Duration must be between 0 and 24 hours")
    energy_hundredths = round(energy_kwh * 100)
    if not 0 <= energy_hundredths <= 10000:
        raise ValueError("Energy must be between 0 and 100 kWh")
    user = user_id.encode("ascii")[:16]
    charge_id = (now.strftime("%Y%m%d%H%M") + f"{random.randrange(10000):04d}").encode()
    data = bytearray(47)
    data[0] = 1
    data[1 : 1 + len(user)] = user
    data[17:33] = charge_id
    data[33] = 1 if delay_minutes else 0
    start_at = now + timedelta(minutes=delay_minutes)
    data[34:38] = (
        _evse_timestamp(start_at).to_bytes(4, "big") if delay_minutes else b"\x00" * 4
    )
    data[38] = 1
    # Captures show mode 1 for auto-full/unlimited and mode 2 when an energy
    # target is active. Duration remains an independent limit field.
    data[39] = 2 if energy_hundredths else 1
    data[40:42] = (
        duration_minutes.to_bytes(2, "big") if duration_minutes else b"\xff\xff"
    )
    data[42:44] = (
        energy_hundredths.to_bytes(2, "big") if energy_hundredths else b"\xff\xff"
    )
    data[44:46] = b"\xff\xff"
    data[46] = amps
    return bytes(data)


def set_time_payload(now: datetime) -> bytes:
    """Build the OCPP Set Tool's 9C YY MM DD HH MM SS clock payload."""
    local = now
    if not 2000 <= local.year <= 2255:
        raise ValueError("Charger year must be between 2000 and 2255")
    return bytes((
        0x9C, local.year - 2000, local.month, local.day,
        local.hour, local.minute, local.second,
    ))


def charge_stop_payload(user_id: str) -> bytes:
    user = user_id.encode("ascii")[:16]
    data = bytearray(17)
    data[0] = 1
    data[1 : 1 + len(user)] = user
    return bytes(data)
