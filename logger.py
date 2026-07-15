"""In-memory event logging for the DC motor digital twin."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class MotorLogEvent:
    """One timestamped motor event suitable for display in the dashboard."""

    timestamp: datetime
    level: str
    event: str
    message: str


class MotorLogger:
    """Store recent motor events in a bounded in-memory log buffer."""

    def __init__(self, max_events: int = 200) -> None:
        """Create a logger that retains at most ``max_events`` recent events."""
        if max_events <= 0:
            raise ValueError("max_events must be greater than zero.")
        self._events: deque[MotorLogEvent] = deque(maxlen=max_events)

    def log_motor_started(self) -> None:
        """Record that the motor simulation has started."""
        self._record("info", "Motor Started", "Motor simulation started.")

    def log_fault_injected(self, fault: str) -> None:
        """Record that a named fault was enabled."""
        self._record("warning", "Fault Injected", f"Fault enabled: {fault}.")

    def log_fault_removed(self, fault: str) -> None:
        """Record that a named fault was disabled."""
        self._record("info", "Fault Removed", f"Fault removed: {fault}.")

    def log_temperature_warning(self, temperature_c: float) -> None:
        """Record a warning when motor temperature reaches a concern level."""
        self._record(
            "warning",
            "Temperature Warning",
            f"Motor temperature is {temperature_c:.1f} C.",
        )

    def log_motor_failure(self, reason: str) -> None:
        """Record a motor failure with its engineering reason."""
        self._record("critical", "Motor Failure", reason)

    def log_health_warning(self, health: str) -> None:
        """Record that motor health has degraded from its normal condition."""
        self._record("warning", "Health Warning", f"Motor health is {health}.")

    def latest_events(self, limit: int = 10) -> list[MotorLogEvent]:
        """Return up to ``limit`` newest events, newest first."""
        if limit <= 0:
            raise ValueError("limit must be greater than zero.")
        return list(reversed(self._events))[:limit]

    def display_latest_events(self, limit: int = 10) -> list[str]:
        """Return readable text lines for the newest in-memory events."""
        return [
            (
                f"{event.timestamp.strftime('%H:%M:%S')} "
                f"[{event.level.upper()}] {event.event}: {event.message}"
            )
            for event in self.latest_events(limit)
        ]

    def _record(self, level: str, event: str, message: str) -> None:
        """Append one timestamped event to the bounded in-memory buffer."""
        self._events.append(
            MotorLogEvent(
                timestamp=datetime.now(timezone.utc),
                level=level,
                event=event,
                message=message,
            )
        )
