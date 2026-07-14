"""Simplified, physics-based state update for a small brushed DC motor."""

from __future__ import annotations

import math
from numbers import Real
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from motor import Motor


# Nominal parameters for a small 12 V permanent-magnet brushed DC motor.
ARMATURE_RESISTANCE_OHM = 2.0
ARMATURE_INDUCTANCE_H = 0.010
TORQUE_CONSTANT_NM_PER_A = 0.020
BACK_EMF_CONSTANT_V_PER_RAD_S = 0.020
ROTOR_INERTIA_KG_M2 = 1.0e-5
VISCOUS_FRICTION_NM_PER_RAD_S = 2.0e-5
COULOMB_FRICTION_NM = 0.002
COPPER_TEMP_COEFFICIENT_PER_C = 0.00393
AMBIENT_TEMPERATURE_C = 25.0
THERMAL_CAPACITANCE_J_PER_C = 50.0
THERMAL_RESISTANCE_C_PER_W = 8.0
MAX_INTERNAL_TIME_STEP_SECONDS = 0.005


def update_motor(motor: Motor, dt: float) -> None:
    """Advance ``motor`` by ``dt`` seconds using coupled DC-motor equations.

    ``motor.load`` must be a non-negative numeric load torque in N m.  The
    function updates only the motor state in place.  A small time step (for
    example 1 to 10 ms) gives the most realistic transient response.
    """
    if dt <= 0:
        raise ValueError("dt must be greater than zero.")
    if not isinstance(motor.load, Real):
        raise TypeError("motor.load must be a numeric torque in N m.")

    load_magnitude = abs(float(motor.load))
    remaining_time = dt

    while remaining_time > 0.0:
        step = min(remaining_time, MAX_INTERNAL_TIME_STEP_SECONDS)
        angular_speed = motor.rpm * (2.0 * math.pi / 60.0)

        # R(T) = R_25 * [1 + alpha * (T - 25 C)]: copper resistance rises as
        # winding temperature rises, reducing current for the same voltage.
        armature_resistance = ARMATURE_RESISTANCE_OHM * (
            1.0
            + COPPER_TEMP_COEFFICIENT_PER_C
            * (motor.temperature - AMBIENT_TEMPERATURE_C)
        )
        armature_resistance = max(armature_resistance, 0.01)

        # E_b = K_e * omega: rotor speed creates a back electromotive force that
        # opposes the applied voltage and naturally reduces current at high speed.
        back_emf = BACK_EMF_CONSTANT_V_PER_RAD_S * angular_speed

        # di/dt = (V - E_b - I*R) / L: armature inductance prevents current from
        # changing instantly after a voltage or load change.
        current_rate = (
            motor.voltage - back_emf - motor.current * armature_resistance
        ) / ARMATURE_INDUCTANCE_H

        # T_e = K_t * I: armature current is converted into electromagnetic torque.
        electromagnetic_torque = TORQUE_CONSTANT_NM_PER_A * motor.current

        # T_v = b * omega: viscous friction grows in proportion to shaft speed.
        viscous_friction = VISCOUS_FRICTION_NM_PER_RAD_S * angular_speed

        if abs(angular_speed) < 1.0e-8:
            # |T_e| <= T_coulomb + T_load: static friction and load hold a stopped
            # shaft in place until electromagnetic torque is large enough to move it.
            breakaway_torque = COULOMB_FRICTION_NM + load_magnitude
            if abs(electromagnetic_torque) <= breakaway_torque:
                angular_acceleration = 0.0
            else:
                direction = math.copysign(1.0, electromagnetic_torque)
                # T_c = T_coulomb * sign(T_e): after breakaway, dry friction opposes
                # the direction in which electromagnetic torque starts the rotor.
                coulomb_friction = COULOMB_FRICTION_NM * direction
                # T_load = |load| * sign(T_e): load torque resists initial motion.
                opposing_load_torque = load_magnitude * direction
                # d_omega/dt = (T_e - T_v - T_c - T_load) / J: net shaft torque
                # changes speed gradually according to rotor inertia.
                angular_acceleration = (
                    electromagnetic_torque
                    - viscous_friction
                    - coulomb_friction
                    - opposing_load_torque
                ) / ROTOR_INERTIA_KG_M2
        else:
            direction = math.copysign(1.0, angular_speed)
            # T_c = T_coulomb * sign(omega): dry bearing/brush friction opposes
            # existing shaft motion.
            coulomb_friction = COULOMB_FRICTION_NM * direction
            # T_load = |load| * sign(omega): a positive load value always resists
            # rotation, including when the motor changes direction.
            opposing_load_torque = load_magnitude * direction
            # d_omega/dt = (T_e - T_v - T_c - T_load) / J: net shaft torque changes
            # speed gradually according to rotor inertia.
            angular_acceleration = (
                electromagnetic_torque
                - viscous_friction
                - coulomb_friction
                - opposing_load_torque
            ) / ROTOR_INERTIA_KG_M2

        # P_copper = I^2 * R: resistive armature losses are converted into heat.
        copper_loss_w = motor.current**2 * armature_resistance

        # P_cooling = (T - T_ambient) / R_th: heat flows from the motor to ambient
        # air in proportion to the temperature difference.
        cooling_loss_w = (
            motor.temperature - AMBIENT_TEMPERATURE_C
        ) / THERMAL_RESISTANCE_C_PER_W

        # dT/dt = (P_copper - P_cooling) / C_th: thermal mass prevents temperature
        # from changing instantly, even during a high-current event.
        temperature_rate = (
            copper_loss_w - cooling_loss_w
        ) / THERMAL_CAPACITANCE_J_PER_C

        # Explicit Euler integration: x_next = x_now + (dx/dt) * dt advances each
        # continuous state by one short physical time step.
        next_current = motor.current + current_rate * step
        next_angular_speed = angular_speed + angular_acceleration * step
        next_temperature = motor.temperature + temperature_rate * step

        motor.current = next_current
        motor.rpm = next_angular_speed * (60.0 / (2.0 * math.pi))
        motor.temperature = next_temperature

        remaining_time -= step

    # Health labels only change after the gradually evolving temperature crosses
    # a limit; hotter windings represent progressively reduced motor health.
    if motor.temperature >= 120.0:
        motor.health = "critical"
    elif motor.temperature >= 95.0:
        motor.health = "degraded"
    elif motor.temperature >= 75.0:
        motor.health = "warm"
    else:
        motor.health = "healthy"
