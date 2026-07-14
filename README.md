# MotorTwin

Physics-based digital twin of a small DC motor, featuring real-time electrical, mechanical, thermal, and fault simulation with a Streamlit and Plotly engineering dashboard.

## Features

- Electrical model: armature R-L dynamics with back EMF
- Mechanical model: torque generation, inertia, viscous friction, and load torque
- Thermal model: copper losses and ambient cooling dynamics
- Fault simulation: open-circuit, short-circuit, overload, and cooling-failure modes
- Engineering dashboard: Streamlit controls + Plotly time-series plots

## Run the dashboard

```bash
pip install -e .
streamlit run app.py
```

## Run tests

```bash
pip install pytest
pytest tests/test_model.py -q
```
