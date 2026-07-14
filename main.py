"""Run the small DC motor simulation as a console application."""

from __future__ import annotations

import time

from faults import FaultManager
from motor import Motor
from physics import update_motor


UPDATE_INTERVAL_SECONDS = 0.1
DISPLAY_INTERVAL_SECONDS = 1.0


def render_motor(motor: Motor) -> None:
    """Render the current motor state without changing the simulation."""
    print(motor.display(), flush=True)


def run_simulation(
    motor: Motor, fault_manager: FaultManager | None = None
) -> None:
    """Advance the motor indefinitely and render it at fixed intervals."""
    next_update = time.monotonic()
    next_display = next_update + DISPLAY_INTERVAL_SECONDS

    while True:
        now = time.monotonic()

        if now >= next_update:
            if fault_manager is not None:
                fault_manager.update(motor, UPDATE_INTERVAL_SECONDS)
            update_motor(motor, UPDATE_INTERVAL_SECONDS)
            next_update += UPDATE_INTERVAL_SECONDS

            # Do not attempt a long burst of delayed simulation steps after a
            # debugger pause or system sleep; resume from the current time.
            if next_update <= now:
                next_update = now + UPDATE_INTERVAL_SECONDS

        if now >= next_display:
            render_motor(motor)
            next_display += DISPLAY_INTERVAL_SECONDS
            if next_display <= now:
                next_display = now + DISPLAY_INTERVAL_SECONDS

        next_event = min(next_update, next_display)
        time.sleep(max(0.0, next_event - time.monotonic()))


def main() -> None:
    """Create a nominal motor and run its simulation until interrupted."""
    motor = Motor(voltage=12.0, load=0.005)
    fault_manager = FaultManager()
    print("Motor simulation started. Press Ctrl+C to stop.")

    try:
        run_simulation(motor, fault_manager)
    except KeyboardInterrupt:
        print("\nMotor simulation stopped.")


if __name__ == "__main__":
    main()
