from __future__ import annotations

import time

import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from motortwin import FaultState, run_simulation


st.set_page_config(page_title="MotorTwin", layout="wide")
st.title("MotorTwin: DC Motor Physics Digital Twin")

with st.sidebar:
    st.header("Inputs")
    voltage = st.slider("Supply Voltage (V)", min_value=0.0, max_value=24.0, value=12.0, step=0.1)
    load_torque = st.slider("Load Torque (N·m)", min_value=0.0, max_value=0.2, value=0.02, step=0.001)
    duration = st.slider("Simulation Duration (s)", min_value=1.0, max_value=20.0, value=8.0, step=0.5)
    dt = st.select_slider("Time Step (s)", options=[0.001, 0.002, 0.005, 0.01, 0.02], value=0.01)
    realtime = st.checkbox("Realtime playback", value=False)

    st.header("Fault Injection")
    open_circuit = st.checkbox("Open-circuit fault")
    short_circuit = st.checkbox("Short-circuit fault")
    overload = st.checkbox("Overload fault")
    cooling_failure = st.checkbox("Cooling failure")

faults = FaultState(
    open_circuit=open_circuit,
    short_circuit=short_circuit,
    overload=overload,
    cooling_failure=cooling_failure,
)

history = run_simulation(
    duration_s=duration,
    dt=dt,
    voltage=voltage,
    load_torque=load_torque,
    faults=faults,
)

samples = len(history)
time_axis = [i * dt for i in range(samples)]
currents = [s.current for s in history]
omega = [s.omega for s in history]
temps = [s.temperature for s in history]

fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05)
fig.add_trace(go.Scatter(x=time_axis, y=currents, name="Current (A)"), row=1, col=1)
fig.add_trace(go.Scatter(x=time_axis, y=omega, name="Speed (rad/s)"), row=2, col=1)
fig.add_trace(go.Scatter(x=time_axis, y=temps, name="Winding Temp (°C)"), row=3, col=1)
fig.update_xaxes(title_text="Time (s)", row=3, col=1)
fig.update_yaxes(title_text="Current", row=1, col=1)
fig.update_yaxes(title_text="Speed", row=2, col=1)
fig.update_yaxes(title_text="Temp", row=3, col=1)
fig.update_layout(height=760, margin=dict(l=20, r=20, t=50, b=20))

if realtime:
    placeholder = st.empty()
    replay_fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05)
    replay_fig.update_xaxes(title_text="Time (s)", row=3, col=1)
    replay_fig.update_yaxes(title_text="Current", row=1, col=1)
    replay_fig.update_yaxes(title_text="Speed", row=2, col=1)
    replay_fig.update_yaxes(title_text="Temp", row=3, col=1)
    replay_fig.update_layout(height=760, margin=dict(l=20, r=20, t=50, b=20))

    for idx in range(2, samples + 1):
        replay_fig.data = ()
        replay_fig.add_trace(go.Scatter(x=time_axis[:idx], y=currents[:idx], name="Current (A)"), row=1, col=1)
        replay_fig.add_trace(go.Scatter(x=time_axis[:idx], y=omega[:idx], name="Speed (rad/s)"), row=2, col=1)
        replay_fig.add_trace(go.Scatter(x=time_axis[:idx], y=temps[:idx], name="Winding Temp (°C)"), row=3, col=1)
        placeholder.plotly_chart(replay_fig, use_container_width=True)
        time.sleep(min(dt, 0.03))
else:
    st.plotly_chart(fig, use_container_width=True)

fault_flags = [name for name, active in {
    "Open-circuit": open_circuit,
    "Short-circuit": short_circuit,
    "Overload": overload,
    "Cooling failure": cooling_failure,
}.items() if active]

st.metric("Final Current (A)", f"{currents[-1]:.2f}")
st.metric("Final Speed (rad/s)", f"{omega[-1]:.2f}")
st.metric("Final Temp (°C)", f"{temps[-1]:.2f}")
st.caption("Active faults: " + (", ".join(fault_flags) if fault_flags else "None"))
