"""Lightweight 2D Plotly renderer for the DC motor state."""

from __future__ import annotations

import math

import plotly.graph_objects as go


HEALTH_COLORS = {
    "healthy": "#35c46a",
    "warm": "#f2c94c",
    "degraded": "#f2c94c",
    "critical": "#ef5350",
}
AMBIENT_TEMPERATURE_C = 25.0
CRITICAL_TEMPERATURE_C = 120.0


def create_motor_figure(
    rpm: float,
    temperature_c: float,
    health: str,
    elapsed_seconds: float,
) -> go.Figure:
    """Return a simple 2D motor view with a speed-driven rotating shaft.

    ``elapsed_seconds`` is supplied by the caller's display clock. The renderer
    only visualizes state and does not change the motor simulation.
    """
    health_color = HEALTH_COLORS.get(health, HEALTH_COLORS["warm"])
    shaft_angle_degrees = (rpm * 360.0 * elapsed_seconds / 60.0) % 360.0
    shaft_angle_radians = math.radians(shaft_angle_degrees)
    shaft_end_x = 0.78 * math.cos(shaft_angle_radians)
    shaft_end_y = 0.78 * math.sin(shaft_angle_radians)

    temperature_fraction = _clamp(
        (temperature_c - AMBIENT_TEMPERATURE_C)
        / (CRITICAL_TEMPERATURE_C - AMBIENT_TEMPERATURE_C),
        0.0,
        1.0,
    )
    glow_opacity = 0.05 + 0.55 * temperature_fraction

    figure = go.Figure()
    figure.add_shape(
        type="circle",
        x0=-1.12,
        y0=-1.12,
        x1=1.12,
        y1=1.12,
        line={"width": 0},
        fillcolor=f"rgba(255, 83, 70, {glow_opacity:.3f})",
    )
    figure.add_shape(
        type="circle",
        x0=-0.86,
        y0=-0.86,
        x1=0.86,
        y1=0.86,
        line={"color": "#d7e2f0", "width": 2},
        fillcolor=health_color,
    )
    figure.add_shape(
        type="circle",
        x0=-0.22,
        y0=-0.22,
        x1=0.22,
        y1=0.22,
        line={"color": "#d7e2f0", "width": 2},
        fillcolor="#172235",
    )
    figure.add_trace(
        go.Scatter(
            x=[0.0, shaft_end_x],
            y=[0.0, shaft_end_y],
            mode="lines",
            line={"color": "#f4f8ff", "width": 8},
            hoverinfo="skip",
            showlegend=False,
        )
    )
    figure.add_trace(
        go.Scatter(
            x=[0.0],
            y=[0.0],
            mode="markers",
            marker={"color": "#f4f8ff", "size": 11},
            hoverinfo="skip",
            showlegend=False,
        )
    )

    figure.update_layout(
        template="plotly_dark",
        height=300,
        margin={"l": 10, "r": 10, "t": 10, "b": 10},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis={"range": [-1.3, 1.3], "visible": False, "fixedrange": True},
        yaxis={
            "range": [-1.3, 1.3],
            "visible": False,
            "fixedrange": True,
            "scaleanchor": "x",
            "scaleratio": 1,
        },
    )
    return figure


def _clamp(value: float, minimum: float, maximum: float) -> float:
    """Constrain a value to an inclusive range."""
    return max(minimum, min(value, maximum))
