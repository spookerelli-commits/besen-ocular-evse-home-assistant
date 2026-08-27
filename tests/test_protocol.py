"""Protocol tests that run without Home Assistant."""

import importlib.util
from pathlib import Path
import unittest

_PATH = Path(__file__).parents[1] / "custom_components" / "ocular_evse" / "protocol.py"
_SPEC = importlib.util.spec_from_file_location("ocular_evse_protocol", _PATH)
assert _SPEC and _SPEC.loader
_PROTOCOL = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_PROTOCOL)

PacketBuffer = _PROTOCOL.PacketBuffer
build_packet = _PROTOCOL.build_packet
packet_parts = _PROTOCOL.packet_parts
validate_packet = _PROTOCOL.validate_packet
parse_ac_status = _PROTOCOL.parse_ac_status
parse_repeated_schedule = _PROTOCOL.parse_repeated_schedule
parse_charging_record = _PROTOCOL.parse_charging_record
charging_record_ack_payload = _PROTOCOL.charging_record_ack_payload
output_current_payload = _PROTOCOL.output_current_payload
charge_start_payload = _PROTOCOL.charge_start_payload
charge_stop_payload = _PROTOCOL.charge_stop_payload
repeated_schedule_payload = _PROTOCOL.repeated_schedule_payload
command_name = _PROTOCOL.command_name
is_known_command = _PROTOCOL.is_known_command
CMD_AC_STATUS_ACK = _PROTOCOL.CMD_AC_STATUS_ACK
CMD_CHARGE_STATUS_ACK = _PROTOCOL.CMD_CHARGE_STATUS_ACK


class ProtocolTests(unittest.TestCase):
    def test_packet_round_trip_and_fragmentation(self):
        packet = build_packet(b"TESTSER1", "123456", 0x8003, b"\x01")
        self.assertTrue(validate_packet(packet))
        serial, command, data = packet_parts(packet)
        self.assertEqual(serial, b"TESTSER1")
        self.assertEqual(command, 0x8003)
        self.assertEqual(data, b"\x01")
        buf = PacketBuffer()
        self.assertEqual(buf.feed(b"junk" + packet[:9]), [])
        self.assertEqual(buf.feed(packet[9:]), [packet])

    def test_checksum_rejects_corruption(self):
        packet = bytearray(build_packet(b"12345678", "123456", 0x8001, b"\x01"))
        packet[20] ^= 1
        self.assertFalse(validate_packet(bytes(packet)))

    def test_single_phase_ac_status(self):
        data = bytearray(25)
        data[1:3] = (2305).to_bytes(2, "big")
        data[3:5] = (1612).to_bytes(2, "big")
        data[5:9] = (3715).to_bytes(4, "big")
        data[9:13] = (123456).to_bytes(4, "big")
        data[13:15] = (22500).to_bytes(2, "big")
        data[18:21] = bytes((4, 1, 14))
        parsed = parse_ac_status(bytes(data))
        self.assertEqual(parsed["l1_voltage"], 230.5)
        self.assertEqual(parsed["l1_current"], 16.12)
        self.assertEqual(parsed["power"], 3715)
        self.assertEqual(parsed["output_state"], "Charging")
        self.assertEqual(parsed["raw_plug_state"], 4)
        self.assertEqual(parsed["raw_output_state"], 1)
        self.assertEqual(parsed["raw_protocol_state"], 14)

    def test_negotiating_plug_state(self):
        data = bytearray(25)
        data[13:15] = (20000).to_bytes(2, "big")
        data[18] = 3
        parsed = parse_ac_status(bytes(data))
        self.assertEqual(parsed["plug_state"], "Negotiating")

    def test_repeated_schedule_get_matches_capture(self):
        self.assertEqual(repeated_schedule_payload(), bytes((2,)) + bytes(63))

    def test_repeated_schedule_set_and_parse(self):
        enabled = (False, False, True, True, True, True, True)
        payload = repeated_schedule_payload(3, 355, enabled)
        self.assertEqual(len(payload), 64)
        self.assertEqual(payload.hex(),
            "010100000000ffffffff0100000000ffffffff"
            "0300030163ffffffff0300030163ffffffff0300030163ffffffff"
            "0300030163ffffffff0300030163ffffffff")
        parsed = parse_repeated_schedule(payload)
        self.assertEqual(parsed["action"], 1)
        self.assertEqual(parsed["enabled_days"], enabled)
        self.assertEqual(parsed["start_minute"], 3)
        self.assertEqual(parsed["duration_minutes"], 355)

    def test_final_desired_schedule_matches_capture(self):
        payload = repeated_schedule_payload(1, 358, (True,) * 7)
        self.assertEqual(payload[1:10].hex(), "0300010166ffffffff")
        self.assertEqual(payload[1:10] * 7, payload[1:])

    def test_status_acknowledgements_match_android_capture(self):
        serial = b"TESTSER1"
        ac_ack = build_packet(serial, "123456", CMD_AC_STATUS_ACK, b"\x00")
        charge_ack = build_packet(serial, "123456", CMD_CHARGE_STATUS_ACK, b"\x00")
        self.assertEqual(
            ac_ack.hex(),
            "0601001a00544553545345523131323334353680040004350f02",
        )
        self.assertEqual(
            charge_ack.hex(),
            "0601001a00544553545345523131323334353680050004360f02",
        )

    def test_received_command_names(self):
        self.assertEqual(command_name(0x0003), "Heartbeat")
        self.assertEqual(command_name(0x0004), "AC status")
        self.assertEqual(command_name(0x0005), "Charging status")
        self.assertEqual(command_name(0x010E), "Repeated schedule response")
        self.assertEqual(command_name(0x7777), "Unknown command")
        self.assertTrue(is_known_command(0x0004))
        self.assertFalse(is_known_command(0x7777))

    def test_charging_record_from_android_capture(self):
        data = bytes.fromhex(
            "01"
            "436c6f636b2020202020202020202020"
            "50756c6c20506c756720202020202020"
            "436c6f636b2031373834363439363031"
            "000402ffffffffffff110100000000"
            "6a5f97816a5fdfd800004857"
            "0000237a00002ffb00000c81"
            "0000000001000000"
        )
        record = parse_charging_record(data)
        self.assertEqual(record["record_header_value"], 1)
        self.assertEqual(record["record_type"], "scheduled")
        self.assertEqual(record["user_id"], "Clock")
        self.assertEqual(record["termination_reason"], "Pull Plug")
        self.assertEqual(record["charge_id"], "Clock 1784649601")
        self.assertEqual(record["raw_mode_value"], 17)
        self.assertEqual(record["duration_seconds"], 18519)
        self.assertEqual(record["meter_start_kwh"], 90.82)
        self.assertEqual(record["meter_end_kwh"], 122.83)
        self.assertEqual(record["session_energy_kwh"], 32.01)
        self.assertEqual(
            charging_record_ack_payload(data).hex(),
            "01436c6f636b203137383436343936303101",
        )

    def test_charging_record_commands_are_known(self):
        self.assertEqual(command_name(0x0009), "Manual charging record")
        self.assertEqual(command_name(0x000A), "Scheduled charging record")
        self.assertTrue(is_known_command(0x000A))

    def test_manual_charging_record_from_controlled_capture(self):
        data = bytes.fromhex(
            "0154657374557365723030303030303031"
            "54657374557365723030303030303031"
            "32303236303832333139303030303639"
            "000101ffffffffffff0b0100000000"
            "6a8ad2c46a8ad389000000c5"
            "000160850001608f0000000a"
            "000000000100000000"
            + "ff" * 58
        )
        self.assertEqual(len(data), 155)
        record = parse_charging_record(data, 0x0009)
        self.assertEqual(record["record_type"], "manual")
        self.assertEqual(record["source_command"], "0x0009")
        self.assertEqual(record["user_id"], "TestUser00000001")
        self.assertEqual(record["stop_user_id"], "TestUser00000001")
        self.assertIsNone(record["termination_reason"])
        self.assertEqual(record["charge_id"], "2026082319000069")
        self.assertEqual(record["raw_mode_value"], 11)
        self.assertEqual(record["start_time"], "2026-08-23 19:00:20")
        self.assertEqual(record["end_time"], "2026-08-23 19:03:37")
        self.assertEqual(record["duration_seconds"], 197)
        self.assertEqual(record["meter_start_kwh"], 902.45)
        self.assertEqual(record["meter_end_kwh"], 902.55)
        self.assertEqual(record["session_energy_kwh"], 0.10)
        self.assertEqual(
            charging_record_ack_payload(data).hex(),
            "013230323630383233313930303030363901",
        )

    def test_current_payloads_match_evsemaster_capture(self):
        self.assertEqual(output_current_payload(), bytes.fromhex("020000"))
        self.assertEqual(output_current_payload(10), bytes.fromhex("010a0b"))
        self.assertEqual(output_current_payload(32), bytes.fromhex("01200b"))

    def test_manual_start_and_stop_shapes_match_capture(self):
        from datetime import datetime, timezone
        start = charge_start_payload(
            "TestUser00000001", 10,
            datetime(2026, 8, 23, 19, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(len(start), 47)
        self.assertEqual(start[0:17], bytes.fromhex("01") + b"TestUser00000001")
        self.assertEqual(start[33:47], bytes.fromhex("00000000000101ffffffffffff0a"))
        self.assertEqual(
            charge_stop_payload("TestUser00000001"),
            bytes.fromhex("01") + b"TestUser00000001",
        )

    def test_once_off_delay_duration_energy_matches_controlled_capture(self):
        from datetime import datetime, timedelta, timezone
        from unittest.mock import patch

        local = timezone(timedelta(hours=9, minutes=30))
        with patch("random.randrange", return_value=29):
            payload = charge_start_payload(
                "TestUser00000001",
                32,
                datetime(2026, 8, 24, 20, 24, tzinfo=local),
                delay_minutes=120,
                duration_minutes=180,
                energy_kwh=4,
            )
        self.assertEqual(
            payload.hex(),
            "0154657374557365723030303030303031"
            "32303236303832343230323430303239"
            "016a8c5400010200b40190ffff20",
        )

    def test_independent_daily_schedule_round_trip(self):
        records = tuple(
            (day != 2, (day * 60) % 1440, 120 + day) for day in range(7)
        )
        decoded = parse_repeated_schedule(
            _PROTOCOL.repeated_schedule_records_payload(records)
        )
        for day, expected in enumerate(records):
            actual = decoded["records"][day]
            self.assertEqual(actual["enabled"], expected[0])
            if expected[0]:
                self.assertEqual(actual["start_minute"], expected[1])
                self.assertEqual(actual["duration_minutes"], expected[2])
            else:
                self.assertEqual(actual["start_minute"], 0)
                self.assertEqual(actual["duration_minutes"], 0)

    def test_set_time_matches_ocpp_set_tool_capture(self):
        from datetime import datetime, timedelta, timezone
        local = timezone(timedelta(hours=9, minutes=30))
        self.assertEqual(
            _PROTOCOL.set_time_payload(datetime(2026, 8, 24, 20, 45, 23, tzinfo=local)),
            bytes.fromhex("9c1a0818142d17"),
        )
        self.assertEqual(_PROTOCOL.CMD_SET_TIME, 0x8207)
        self.assertEqual(_PROTOCOL.CMD_SET_TIME_RESPONSE, 0x0207)


if __name__ == "__main__":
    unittest.main()
