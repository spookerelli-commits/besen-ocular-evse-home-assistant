"""Pure session-health state machine for the Ocular BLE connection."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SessionHealth:
    """Distinguish a live BLE transport from a live EVSE protocol session."""

    packet_timeout: float
    operational_stale: float
    operational_timeout: float
    login_timeout: float
    last_packet: float = 0.0
    last_operational: float = 0.0
    login_requested: float | None = None
    login_was_recovery: bool = False
    operational_resume_deadline: float | None = None

    def connection_started(self, now: float) -> None:
        """Start timeout grace periods for a newly connected transport."""
        self.last_packet = now
        self.last_operational = now
        self.login_requested = None
        self.login_was_recovery = False
        self.operational_resume_deadline = None

    def packet_received(self, now: float) -> None:
        """Record any valid protocol packet, including a login beacon."""
        self.last_packet = now

    def operational_received(self, now: float) -> None:
        """Record traffic that proves the authenticated session is live."""
        self.last_packet = now
        self.last_operational = now
        self.login_requested = None
        self.login_was_recovery = False
        self.operational_resume_deadline = None

    def should_request_login(self, now: float, authenticated: bool) -> bool:
        """Return whether one guarded login request should be sent."""
        if (
            self.login_requested is not None
            or self.operational_resume_deadline is not None
        ):
            return False
        return not authenticated or now - self.last_operational > self.operational_stale

    def mark_login_requested(self, now: float, *, recovering: bool) -> None:
        self.login_requested = now
        self.login_was_recovery = recovering

    def login_succeeded(self, now: float) -> None:
        if self.login_was_recovery:
            self.operational_resume_deadline = now + self.login_timeout
        self.login_requested = None
        self.login_was_recovery = False

    def failure_reason(self, now: float, authenticated: bool) -> str | None:
        """Return a reason when the transport or protocol session is stale."""
        if now - self.last_packet > self.packet_timeout:
            return "EVSE packet timeout"
        if (
            self.login_requested is not None
            and now - self.login_requested > self.login_timeout
        ):
            return "EVSE login response timeout"
        if (
            self.operational_resume_deadline is not None
            and now > self.operational_resume_deadline
        ):
            return "EVSE operational traffic did not resume after login"
        if authenticated and now - self.last_operational > self.operational_timeout:
            return "EVSE operational traffic timeout"
        return None
