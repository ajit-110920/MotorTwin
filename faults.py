"""Gradual engineering fault models for the DC motor digital twin.

The manager models progressive degradation rather than instantaneous faults.
Each enabled fault has a target severity and an applied severity.  The applied
severity ramps toward its target during each update, preventing discontinuous
changes to voltage, load, or temperature.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from numbers import Real

from motor import Motor
from physics import (
    AMBIENT_TEMPERATURE_C,
    THERMAL_CAPACITANCE_J_PER_C,
    THERMAL_RESISTANCE_C_PER_W,
)


FAULT_NAMES = frozenset(
    {"voltage_drop", "bearing_wear", "cooling_failure", "overload"}
)
SEVERITY_RAMP_PER_SECOND = 0.25
MAX_VOLTAGE_DROP_FRACTION = 0.35
MAX_BEARING_STATIC_TORQUE_NM = 0.008
MAX_BEARING_VISCOUS_TORQUE_PER_RPM = 8.0e-7
MAX_OVERLOAD_TORQUE_NM = 0.025


@dataclass
class FaultManager:
    """Enable, disable, and progressively apply motor fault conditions.

    Fault severities range from 0.0 (inactive) to 1.0 (maximum modeled
    severity). ``update`` must be called once per simulation step before
    ``update_motor``. The manager records nominal voltage and load on its
    first update; use ``set_nominal_inputs`` if those commanded inputs change.

    Engineering models:
    - Voltage drop represents rising supply, cable, or connector resistance.
    - Bearing wear adds breakaway and speed-dependent friction torque.
    - Cooling failure removes part of the normal heat-rejection path.
    - Overload adds external resisting shaft torque.
    """

    _target: dict[str, float] = field(
        default_factory=lambda: {name: 0.0 for name in FAULT_NAMES}
    )
    _applied: dict[str, float] = field(
        default_factory=lambda: {name: 0.0 for name in FAULT_NAMES}
    )
    _nominal_voltage: float | None = None
    _nominal_load: float | None = None

    def enable(self, fault: str, severity: float = 1.0) -> None:
        """Enable ``fault`` and gradually ramp it to ``severity``."""
        self._target[self._validate_fault(fault)] = self._validate_severity(
            severity
        )

    def disable(self, fault: str) -> None:
        """Disable ``fault`` by gradually returning its severity to zero."""
        self._target[self._validate_fault(fault)] = 0.0

    def is_enabled(self, fault: str) -> bool:
        """Return whether ``fault`` has a non-zero requested severity."""
        return self._target[self._validate_fault(fault)] > 0.0

    def severity(self, fault: str) -> float:
        """Return the currently applied, ramped severity of ``fault``."""
        return self._applied[self._validate_fault(fault)]

    def set_nominal_inputs(self, voltage: float, load: float) -> None:
        """Set the fault-free voltage and load torque used as input baselines."""
        self._nominal_voltage = float(voltage)
        self._nominal_load = float(load)

    def update(self, motor: Motor, dt: float) -> None:
        """Progress fault severities and apply their gradual effects to ``motor``."""
        if dt <= 0.0:
            raise ValueError("dt must be greater than zero.")
        if not isinstance(motor.load, Real):
            raise TypeError("FaultManager requires motor.load in N m.")

        self._capture_nominal_inputs(motor)
        self._ramp_severities(dt)

        voltage_drop = self._applied["voltage_drop"]
        bearing_wear = self._applied["bearing_wear"]
        cooling_failure = self._applied["cooling_failure"]
        overload = self._applied["overload"]

        # V_effective = V_nominal * (1 - 0.35 * severity): a higher source or
        # connector resistance leaves less voltage available at the armature.
        motor.voltage = self._nominal_voltage * (
            1.0 - MAX_VOLTAGE_DROP_FRACTION * voltage_drop
        )

        # T_bearing = severity * (T_static + k_rpm * |RPM|): worn bearings add
        # both breakaway friction and speed-dependent drag to the shaft load.
        bearing_torque = bearing_wear * (
            MAX_BEARING_STATIC_TORQUE_NM
            + MAX_BEARING_VISCOUS_TORQUE_PER_RPM * abs(motor.rpm)
        )

        # T_load = T_nominal + T_bearing + T_overload: overload represents an
        # external machine demand that opposes motor rotation.
        overload_torque = overload * MAX_OVERLOAD_TORQUE_NM
        motor.load = self._nominal_load + bearing_torque + overload_torque

        # Delta_T = [severity * (T - T_ambient) / R_th] * dt / C_th: failed
        # cooling retains part of the heat that a healthy motor would reject.
        retained_heat_w = cooling_failure * max(
            0.0,
            (motor.temperature - AMBIENT_TEMPERATURE_C)
            / THERMAL_RESISTANCE_C_PER_W,
        )
        motor.temperature += retained_heat_w * dt / THERMAL_CAPACITANCE_J_PER_C

    def _capture_nominal_inputs(self, motor: Motor) -> None:
        """Store initial fault-free inputs once, before any effects are applied."""
        if self._nominal_voltage is None:
            self._nominal_voltage = float(motor.voltage)
        if self._nominal_load is None:
            self._nominal_load = float(motor.load)

    def _ramp_severities(self, dt: float) -> None:
        """Move each applied severity toward its requested severity."""
        maximum_change = SEVERITY_RAMP_PER_SECOND * dt
        for fault, target in self._target.items():
            current = self._applied[fault]
            # s_next = s_now + clamp(s_target - s_now, +/- ramp_rate * dt):
            # fault effects grow and clear smoothly instead of in one update.
            self._applied[fault] = current + max(
                -maximum_change,
                min(target - current, maximum_change),
            )

    @staticmethod
    def _validate_fault(fault: str) -> str:
        """Validate and return a supported fault name."""
        if fault not in FAULT_NAMES:
            supported = ", ".join(sorted(FAULT_NAMES))
            raise ValueError(f"Unsupported fault '{fault}'. Use: {supported}.")
        return fault

    @staticmethod
    def _validate_severity(severity: float) -> float:
        """Validate a normalized fault severity."""
        if not 0.0 <= severity <= 1.0:
            raise ValueError("Fault severity must be between 0.0 and 1.0.")
        return float(severity)
