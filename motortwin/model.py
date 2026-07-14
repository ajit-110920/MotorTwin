from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MotorParameters:
    resistance: float = 1.2
    inductance: float = 0.02
    back_emf_constant: float = 0.02
    torque_constant: float = 0.02
    inertia: float = 0.0007
    viscous_friction: float = 0.0002
    thermal_capacitance: float = 35.0
    thermal_conductance: float = 0.55
    ambient_temperature: float = 25.0
    copper_temp_coeff: float = 0.0039


@dataclass(frozen=True)
class FaultState:
    open_circuit: bool = False
    short_circuit: bool = False
    overload: bool = False
    cooling_failure: bool = False
    short_resistance_factor: float = 0.35
    overload_factor: float = 2.0
    cooling_factor: float = 0.2


@dataclass(frozen=True)
class MotorState:
    current: float = 0.0
    omega: float = 0.0
    temperature: float = 25.0


def _clamp(value: float, minimum: float) -> float:
    return value if value > minimum else minimum


def step_motor(
    state: MotorState,
    params: MotorParameters,
    voltage: float,
    load_torque: float,
    dt: float,
    faults: FaultState | None = None,
) -> MotorState:
    faults = faults or FaultState()

    resistance = params.resistance * (
        1.0 + params.copper_temp_coeff * (state.temperature - params.ambient_temperature)
    )
    resistance = _clamp(resistance, 1e-4)

    effective_voltage = 0.0 if faults.open_circuit else voltage
    if faults.short_circuit:
        resistance = _clamp(resistance * faults.short_resistance_factor, 1e-4)

    effective_load = load_torque * (faults.overload_factor if faults.overload else 1.0)
    thermal_conductance = params.thermal_conductance * (
        faults.cooling_factor if faults.cooling_failure else 1.0
    )

    di_dt = (
        effective_voltage - resistance * state.current - params.back_emf_constant * state.omega
    ) / params.inductance
    current = state.current + dt * di_dt

    electromagnetic_torque = params.torque_constant * current
    domega_dt = (
        electromagnetic_torque - params.viscous_friction * state.omega - effective_load
    ) / params.inertia
    omega = max(0.0, state.omega + dt * domega_dt)

    copper_loss = current * current * resistance
    dtemp_dt = (
        copper_loss - thermal_conductance * (state.temperature - params.ambient_temperature)
    ) / params.thermal_capacitance
    temperature = state.temperature + dt * dtemp_dt

    return MotorState(current=current, omega=omega, temperature=temperature)


def run_simulation(
    duration_s: float,
    dt: float,
    voltage: float,
    load_torque: float,
    params: MotorParameters | None = None,
    faults: FaultState | None = None,
) -> list[MotorState]:
    params = params or MotorParameters()
    faults = faults or FaultState()

    steps = max(int(duration_s / dt), 1)
    state = MotorState(temperature=params.ambient_temperature)
    history = [state]

    for _ in range(steps):
        state = step_motor(
            state=state,
            params=params,
            voltage=voltage,
            load_torque=load_torque,
            dt=dt,
            faults=faults,
        )
        history.append(state)

    return history
