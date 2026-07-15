"""Industrial Streamlit dashboard for the DC motor digital twin."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import time

import plotly.graph_objects as go
import streamlit as st

from faults import FaultManager
from logger import MotorLogger
from motor import Motor
from physics import update_motor
from visualization import create_motor_figure


REFRESH_INTERVAL_SECONDS = 0.1
MAX_ELAPSED_SECONDS = 1.0
HISTORY_WINDOW_SECONDS = 60
TEMPERATURE_WARNING_C = 75.0
HEALTH_LEVELS = {"healthy": 0, "warm": 1, "degraded": 2, "critical": 3}
FAULT_BUTTONS = (
    ("Voltage Drop", "voltage_drop"),
    ("Bearing Wear", "bearing_wear"),
    ("Cooling Failure", "cooling_failure"),
    ("Overload", "overload"),
)
HEALTH_GUIDANCE = {
    "healthy": "Normal operating condition. Continue monitoring live trends.",
    "warm": "Elevated temperature. Inspect loading and cooling margin.",
    "degraded": "Degraded thermal condition. Reduce demand and investigate.",
    "critical": "Critical condition. Stop and inspect the motor system.",
}


@dataclass(frozen=True)
class MotorSample:
    """One timestamped, display-only snapshot of the motor state."""

    timestamp: datetime
    voltage: float
    current: float
    rpm: float
    temperature: float
    health: str


def _initialise_simulation() -> None:
    """Create independent simulation, history, and event services per session."""
    if "motor" not in st.session_state:
        st.session_state.motor = Motor(voltage=12.0, load=0.005)
        st.session_state.fault_manager = FaultManager()
        st.session_state.event_logger = MotorLogger()
        st.session_state.event_logger.log_motor_started()
        st.session_state.last_update = time.monotonic()
        st.session_state.history = deque()
        st.session_state.last_health = "healthy"
        st.session_state.temperature_warning_active = False


def _advance_simulation() -> Motor:
    """Advance the session motor, then record display and engineering events."""
    now = time.monotonic()
    elapsed = min(now - st.session_state.last_update, MAX_ELAPSED_SECONDS)
    elapsed = max(0.0, elapsed)

    if elapsed:
        st.session_state.fault_manager.update(st.session_state.motor, elapsed)
        update_motor(st.session_state.motor, elapsed)

    st.session_state.last_update = now
    motor = st.session_state.motor
    _record_operating_events(motor)
    _record_sample(motor)
    return motor


def _record_operating_events(motor: Motor) -> None:
    """Log health and temperature threshold transitions without event flooding."""
    event_logger: MotorLogger = st.session_state.event_logger

    temperature_warning = motor.temperature >= TEMPERATURE_WARNING_C
    if temperature_warning and not st.session_state.temperature_warning_active:
        event_logger.log_temperature_warning(motor.temperature)
    st.session_state.temperature_warning_active = temperature_warning

    if motor.health != st.session_state.last_health:
        if motor.health != "healthy":
            event_logger.log_health_warning(motor.health)
        if motor.health == "critical":
            event_logger.log_motor_failure("Critical motor temperature reached.")
        st.session_state.last_health = motor.health


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


def _apply_industrial_theme() -> None:
    """Apply dashboard-local dark industrial styling."""
    st.markdown(
        """
        <style>
            .stApp {
                background-color: #0b1220;
                background-image: linear-gradient(rgba(80, 104, 136, 0.07) 1px,
                transparent 1px), linear-gradient(90deg, rgba(80, 104, 136, 0.07)
                1px, transparent 1px);
                background-size: 28px 28px;
                color: #e5edf8;
            }
            [data-testid="stHeader"] { background: rgba(11, 18, 32, 0.88); }
            [data-testid="stMetric"] {
                background: #131d2e;
                border: 1px solid #2d405d;
                border-radius: 8px;
                padding: 1rem;
            }
            [data-testid="stMetricLabel"] { color: #9fb0c8; }
            [data-testid="stMetricValue"] { color: #f4f8ff; }
            [data-testid="stTabs"] button { font-weight: 600; }
            .industrial-caption { color: #9fb0c8; font-size: 0.9rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _handle_fault_action(fault: str | None) -> None:
    """Toggle one fault or request gradual recovery through FaultManager."""
    fault_manager: FaultManager = st.session_state.fault_manager
    event_logger: MotorLogger = st.session_state.event_logger

    if fault is None:
        fault_manager.reset_motor(st.session_state.motor)
        event_logger.log_fault_removed("all active faults")
    elif fault_manager.is_enabled(fault):
        fault_manager.disable(fault)
        event_logger.log_fault_removed(fault)
    else:
        fault_manager.enable(fault)
        event_logger.log_fault_injected(fault)


def _render_fault_controls() -> None:
    """Render fault controls using one shared FaultManager action handler."""
    fault_manager: FaultManager = st.session_state.fault_manager
    columns = st.columns(len(FAULT_BUTTONS) + 1)

    for column, (label, fault) in zip(columns, FAULT_BUTTONS):
        is_active = fault_manager.is_enabled(fault)
        if column.button(
            label,
            key=f"fault-{fault}",
            type="primary" if is_active else "secondary",
            use_container_width=True,
        ):
            _handle_fault_action(fault)

    if columns[-1].button(
        "Reset",
        key="reset-motor",
        type="secondary",
        use_container_width=True,
    ):
        _handle_fault_action(None)


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
        height=280,
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
        height=280,
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


def _render_overview(motor: Motor) -> None:
    """Render current operating metrics in a responsive grid."""
    first_row = st.columns(3)
    first_row[0].metric("Voltage", f"{motor.voltage:.2f} V")
    first_row[1].metric("Current", f"{motor.current:.2f} A")
    first_row[2].metric("Speed", f"{motor.rpm:,.0f} RPM")

    second_row = st.columns(3)
    second_row[0].metric("Temperature", f"{motor.temperature:.1f} C")
    second_row[1].metric("Health", motor.health.replace("_", " ").title())
    second_row[2].metric("Load", f"{float(motor.load):.4f} N m")


def _render_charts() -> None:
    """Render the requested 60-second Plotly time-history charts."""
    samples = list(st.session_state.history)
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


def _render_logs() -> None:
    """Render the latest in-memory engineering events."""
    events = st.session_state.event_logger.latest_events(20)
    if not events:
        st.info("No events recorded.")
        return

    st.dataframe(
        [
            {
                "Time": event.timestamp.strftime("%H:%M:%S"),
                "Level": event.level.upper(),
                "Event": event.event,
                "Message": event.message,
            }
            for event in events
        ],
        hide_index=True,
        use_container_width=True,
    )


def _render_motor_visualization(motor: Motor) -> None:
    """Render the state-driven 2D motor view."""
    st.plotly_chart(
        create_motor_figure(
            motor.rpm,
            motor.temperature,
            motor.health,
            time.monotonic(),
        ),
        use_container_width=True,
        config={"displayModeBar": False},
    )


def _render_health(motor: Motor) -> None:
    """Render concise health assessment and thermal margin."""
    health_text = motor.health.replace("_", " ").title()
    guidance = HEALTH_GUIDANCE.get(motor.health, HEALTH_GUIDANCE["warm"])
    left_column, right_column = st.columns(2)
    left_column.metric("Current Condition", health_text)
    right_column.metric("Temperature Margin", f"{120.0 - motor.temperature:.1f} C")
    st.info(guidance)


@st.fragment(run_every=REFRESH_INTERVAL_SECONDS)
def render_dashboard() -> None:
    """Refresh and render the industrial dashboard sections."""
    motor = _advance_simulation()
    overview, charts, faults, logs, visualization, health = st.tabs(
        ["Overview", "Charts", "Faults", "Logs", "Motor Visualization", "Health"]
    )

    with overview:
        _render_overview(motor)
        st.markdown(
            '<p class="industrial-caption">Live model update: 100 ms | '
            'History: 60 s</p>',
            unsafe_allow_html=True,
        )
    with charts:
        _render_charts()
    with faults:
        _render_fault_controls()
    with logs:
        _render_logs()
    with visualization:
        _render_motor_visualization(motor)
    with health:
        _render_health(motor)


def main() -> None:
    """Configure and start the industrial DC motor dashboard."""
    st.set_page_config(
        page_title="DC Motor Digital Twin",
        page_icon="M",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    _apply_industrial_theme()
    _initialise_simulation()
    st.title("DC Motor Digital Twin")
    st.caption("Industrial monitoring and fault-injection console")
    render_dashboard()


if __name__ == "__main__":
    main()
