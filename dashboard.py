"""Streamlit dashboard for viewing the live DC motor simulation state."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import time

import plotly.graph_objects as go
import streamlit as st

from faults import FaultManager
from motor import Motor
from physics import update_motor


REFRESH_INTERVAL_SECONDS = 0.1
MAX_ELAPSED_SECONDS = 1.0
HISTORY_WINDOW_SECONDS = 60
HEALTH_LEVELS = {"healthy": 0, "warm": 1, "degraded": 2, "critical": 3}


@dataclass(frozen=True)
class MotorSample:
    """One timestamped, display-only snapshot of the simulated motor state."""

    timestamp: datetime
    voltage: float
    current: float
    rpm: float
    temperature: float
    health: str


def _initialise_simulation() -> None:
    """Create one independent motor simulation for the current browser session."""
    if "motor" not in st.session_state:
        st.session_state.motor = Motor(voltage=12.0, load=0.005)
        st.session_state.fault_manager = FaultManager()
        st.session_state.last_update = time.monotonic()
        st.session_state.history = deque()


def _advance_simulation() -> Motor:
    """Advance the session motor by elapsed wall-clock time."""
    now = time.monotonic()
    elapsed = min(now - st.session_state.last_update, MAX_ELAPSED_SECONDS)
    elapsed = max(0.0, elapsed)

    if elapsed:
        st.session_state.fault_manager.update(st.session_state.motor, elapsed)
        update_motor(st.session_state.motor, elapsed)

    st.session_state.last_update = now
    motor = st.session_state.motor
    _record_sample(motor)
    return motor


def _record_sample(motor: Motor) -> None:
    """Store one sample and discard display history older than 60 seconds."""
    timestamp = datetime.now(timezone.utc)
    history: deque[MotorSample] = st.session_state.history
    history.append(
        MotorSample(
            timestamp=timestamp,
            voltage=motor.voltage,
            current=motor.current,
            rpm=motor.rpm,
            temperature=motor.temperature,
            health=motor.health,
        )
    )

    cutoff = timestamp - timedelta(seconds=HISTORY_WINDOW_SECONDS)
    while history and history[0].timestamp < cutoff:
        history.popleft()


def _apply_dark_theme() -> None:
    """Apply dashboard-local dark styling to metric cards."""
    st.markdown(
        """
        <style>
            .stApp { background: #0b1220; color: #e5edf8; }
            [data-testid="stHeader"] { background: rgba(11, 18, 32, 0.85); }
            [data-testid="stMetric"] {
                background: #131d2e;
                border: 1px solid #26364f;
                border-radius: 10px;
                padding: 1.1rem;
            }
            [data-testid="stMetricLabel"] { color: #9fb0c8; }
            [data-testid="stMetricValue"] { color: #f4f8ff; }
            .dashboard-caption { color: #9fb0c8; font-size: 0.9rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _numeric_figure(
    samples: list[MotorSample],
    title: str,
    field: str,
    unit: str,
    color: str,
) -> go.Figure:
    """Build one dark Plotly line chart for a numeric motor measurement."""
    timestamps = [sample.timestamp for sample in samples]
    values = [getattr(sample, field) for sample in samples]

    figure = go.Figure(
        go.Scatter(
            x=timestamps,
            y=values,
            mode="lines",
            line={"color": color, "width": 2},
            hovertemplate=f"%{{x}}<br>{title}: %{{y:.2f}} {unit}<extra></extra>",
        )
    )
    figure.update_layout(
        template="plotly_dark",
        title=title,
        height=260,
        margin={"l": 15, "r": 15, "t": 45, "b": 15},
        showlegend=False,
        uirevision="last-60-seconds",
    )
    figure.update_xaxes(title_text="Time", showgrid=True)
    figure.update_yaxes(title_text=unit, showgrid=True)
    return figure


def _health_figure(samples: list[MotorSample]) -> go.Figure:
    """Build a step chart for the categorical motor-health state."""
    timestamps = [sample.timestamp for sample in samples]
    levels = [HEALTH_LEVELS.get(sample.health, 0) for sample in samples]
    labels = [sample.health.title() for sample in samples]

    figure = go.Figure(
        go.Scatter(
            x=timestamps,
            y=levels,
            text=labels,
            mode="lines",
            line={"color": "#f3c969", "width": 2, "shape": "hv"},
            hovertemplate="%{x}<br>Health: %{text}<extra></extra>",
        )
    )
    figure.update_layout(
        template="plotly_dark",
        title="Health",
        height=260,
        margin={"l": 15, "r": 15, "t": 45, "b": 15},
        showlegend=False,
        uirevision="last-60-seconds",
    )
    figure.update_xaxes(title_text="Time", showgrid=True)
    figure.update_yaxes(
        title_text="Condition",
        tickmode="array",
        tickvals=list(HEALTH_LEVELS.values()),
        ticktext=["Healthy", "Warm", "Degraded", "Critical"],
        range=[-0.25, 3.25],
        showgrid=True,
    )
    return figure


def _render_history_charts() -> None:
    """Render the requested 60-second Plotly time-history charts."""
    samples = list(st.session_state.history)
    if not samples:
        return

    left_column, right_column = st.columns(2)
    left_column.plotly_chart(
        _numeric_figure(samples, "Voltage", "voltage", "V", "#59b8ff"),
        use_container_width=True,
        config={"displayModeBar": False},
    )
    right_column.plotly_chart(
        _numeric_figure(samples, "RPM", "rpm", "RPM", "#a78bfa"),
        use_container_width=True,
        config={"displayModeBar": False},
    )

    left_column, right_column = st.columns(2)
    left_column.plotly_chart(
        _numeric_figure(samples, "Current", "current", "A", "#4ade80"),
        use_container_width=True,
        config={"displayModeBar": False},
    )
    right_column.plotly_chart(
        _numeric_figure(samples, "Temperature", "temperature", "C", "#fb7185"),
        use_container_width=True,
        config={"displayModeBar": False},
    )

    st.plotly_chart(
        _health_figure(samples),
        use_container_width=True,
        config={"displayModeBar": False},
    )


@st.fragment(run_every=REFRESH_INTERVAL_SECONDS)
def render_dashboard() -> None:
    """Refresh and render the motor metric cards and Plotly history charts."""
    motor = _advance_simulation()

    first_row = st.columns(3)
    first_row[0].metric("Voltage", f"{motor.voltage:.2f} V")
    first_row[1].metric("Current", f"{motor.current:.2f} A")
    first_row[2].metric("Speed", f"{motor.rpm:,.0f} RPM")

    second_row = st.columns(3)
    second_row[0].metric("Temperature", f"{motor.temperature:.1f} C")
    second_row[1].metric("Health", motor.health.replace("_", " ").title())
    second_row[2].metric("Load", f"{float(motor.load):.4f} N m")

    st.markdown(
        '<p class="dashboard-caption">Live model update: 100 ms | History: 60 s</p>',
        unsafe_allow_html=True,
    )
    _render_history_charts()


def main() -> None:
    """Configure and start the professional motor-state dashboard."""
    st.set_page_config(
        page_title="DC Motor Digital Twin",
        page_icon="M",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    _apply_dark_theme()
    _initialise_simulation()

    st.title("DC Motor Digital Twin")
    st.caption("Live simplified physics model - no active faults")
    render_dashboard()


if __name__ == "__main__":
    main()
