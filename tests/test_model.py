from motortwin import FaultState, run_simulation


def test_nominal_simulation_generates_positive_speed_and_current() -> None:
    states = run_simulation(duration_s=2.0, dt=0.01, voltage=12.0, load_torque=0.01)
    assert states[-1].current > 0
    assert states[-1].omega > 0


def test_open_circuit_fault_removes_drive_current() -> None:
    nominal = run_simulation(duration_s=2.0, dt=0.01, voltage=12.0, load_torque=0.01)
    open_fault = run_simulation(
        duration_s=2.0,
        dt=0.01,
        voltage=12.0,
        load_torque=0.01,
        faults=FaultState(open_circuit=True),
    )
    assert abs(open_fault[-1].current) < 1e-2
    assert open_fault[-1].omega < nominal[-1].omega


def test_short_circuit_fault_increases_current() -> None:
    nominal = run_simulation(duration_s=0.8, dt=0.005, voltage=12.0, load_torque=0.01)
    short_fault = run_simulation(
        duration_s=0.8,
        dt=0.005,
        voltage=12.0,
        load_torque=0.01,
        faults=FaultState(short_circuit=True),
    )
    assert short_fault[-1].current > nominal[-1].current


def test_cooling_failure_runs_hotter() -> None:
    nominal = run_simulation(duration_s=8.0, dt=0.01, voltage=12.0, load_torque=0.03)
    hot = run_simulation(
        duration_s=8.0,
        dt=0.01,
        voltage=12.0,
        load_torque=0.03,
        faults=FaultState(cooling_failure=True),
    )
    assert hot[-1].temperature > nominal[-1].temperature


def test_overload_reduces_speed() -> None:
    nominal = run_simulation(duration_s=2.0, dt=0.01, voltage=12.0, load_torque=0.015)
    overloaded = run_simulation(
        duration_s=2.0,
        dt=0.01,
        voltage=12.0,
        load_torque=0.015,
        faults=FaultState(overload=True),
    )
    assert overloaded[-1].omega < nominal[-1].omega
