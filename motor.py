"""State container for a small DC motor digital twin.

This module intentionally contains no physics, simulation, dashboard, or
fault-detection behavior.  It only represents the current motor state.
"""

from dataclasses import asdict, dataclass


@dataclass
class Motor:
    """Store the observable state of a DC motor.

    Values are kept in common engineering units: volts, amperes, revolutions
    per minute, and degrees Celsius. ``load`` is the currently assigned load
    description or value; it is not interpreted by this class.
    """

    voltage: float = 0.0
    current: float = 0.0
    rpm: float = 0.0
    temperature: float = 25.0
    load: float | str = 0.0
    health: str = "healthy"
    status: str = "stopped"

    def display(self) -> str:
        """Return a readable summary of the current motor state."""
        return (
            f"Voltage: {self.voltage} V | Current: {self.current} A | "
            f"RPM: {self.rpm} | Temperature: {self.temperature} degrees C | "
            f"Load: {self.load} | Health: {self.health} | "
            f"Status: {self.status}"
        )

    def reset(self) -> None:
        """Restore the motor to its default idle state."""
        self.voltage = 0.0
        self.current = 0.0
        self.rpm = 0.0
        self.temperature = 25.0
        self.load = 0.0
        self.health = "healthy"
        self.status = "stopped"

    def to_dict(self) -> dict[str, float | str]:
        """Return the current state as a dictionary."""
        return asdict(self)
