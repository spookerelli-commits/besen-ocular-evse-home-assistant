"""Session-health tests that run without Home Assistant or Bluetooth."""

import importlib.util
from pathlib import Path
import sys
import unittest

_PATH = Path(__file__).parents[1] / "custom_components" / "ocular_evse" / "session.py"
_SPEC = importlib.util.spec_from_file_location("ocular_evse_session", _PATH)
assert _SPEC and _SPEC.loader
_SESSION = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _SESSION
_SPEC.loader.exec_module(_SESSION)

SessionHealth = _SESSION.SessionHealth


class SessionHealthTests(unittest.TestCase):
    def setUp(self):
        self.health = SessionHealth(45, 45, 90, 20)
        self.health.connection_started(100)

    def test_isolated_login_beacon_is_ignored_during_healthy_session(self):
        self.health.operational_received(110)
        self.assertFalse(self.health.should_request_login(140, True))

    def test_stale_operational_traffic_requests_only_one_login(self):
        self.health.operational_received(110)
        self.assertTrue(self.health.should_request_login(156, True))
        self.health.mark_login_requested(156, recovering=True)
        self.assertFalse(self.health.should_request_login(161, True))

    def test_initial_unauthenticated_beacon_requests_login(self):
        self.assertTrue(self.health.should_request_login(101, False))

    def test_login_request_timeout_forces_reconnect(self):
        self.health.mark_login_requested(120, recovering=True)
        self.health.packet_received(139)
        self.assertEqual(
            self.health.failure_reason(141, True),
            "EVSE login response timeout",
        )

    def test_login_beacons_do_not_hide_operational_timeout(self):
        self.health.operational_received(110)
        for now in (130, 150, 170, 195):
            self.health.packet_received(now)
        self.assertEqual(
            self.health.failure_reason(201, True),
            "EVSE operational traffic timeout",
        )

    def test_complete_packet_silence_times_out(self):
        self.health.operational_received(110)
        self.assertEqual(
            self.health.failure_reason(156, True),
            "EVSE packet timeout",
        )

    def test_operational_recovery_clears_pending_login(self):
        self.health.mark_login_requested(160, recovering=True)
        self.health.operational_received(165)
        self.assertIsNone(self.health.login_requested)
        self.assertIsNone(self.health.failure_reason(180, True))

    def test_successful_relogin_does_not_create_beacon_login_loop(self):
        self.health.operational_received(100)
        self.health.mark_login_requested(146, recovering=True)
        self.health.login_succeeded(147)
        self.health.packet_received(152)
        self.assertFalse(self.health.should_request_login(152, True))
        self.assertEqual(
            self.health.failure_reason(168, True),
            "EVSE operational traffic did not resume after login",
        )

    def test_observed_duplicate_then_login_only_trace_requests_recovery(self):
        self.health.operational_received(100)
        self.health.packet_received(101)
        self.assertFalse(self.health.should_request_login(101, True))
        for now in (106, 111, 116, 121, 126, 131, 136, 141):
            self.health.packet_received(now)
            self.assertFalse(self.health.should_request_login(now, True))
        self.health.packet_received(146)
        self.assertTrue(self.health.should_request_login(146, True))


if __name__ == "__main__":
    unittest.main()
