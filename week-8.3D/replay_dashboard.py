"""
SIT225 6D - Replay dashboard.

This is NOT the data collection script. live_capture.py is what collected the data.
This replays the already-saved 10-second windows (CSV + matching JPG) through the
same Plotly Dash layout, one window every few seconds, so the dashboard behaviour
can be demonstrated without a live Arduino IoT Cloud connection.

Run:  python replay_dashboard.py
Then: http://127.0.0.1:8060
"""

import os
import base64
import glob

import pandas as pd
import plotly.graph_objs as go
from dash import Dash, dcc, html
from dash.dependencies import Input, Output

DATA_DIR = "data_combined"
ANNOTATION_FILE = "annotation.csv"
PORT = 8060
SECONDS_PER_WINDOW = 4  # how fast the replay steps through saved windows

LABEL_NAMES = {0: "no-activity", 1: "waving (activity 1)", 2: "shaking (activity 2)"}


def load_windows():
    """Return [(stem, csv_path, jpg_path)] sorted by sequence number."""
    stems = []
    for csv_path in glob.glob(os.path.join(DATA_DIR, "*.csv")):
        stem = os.path.splitext(os.path.basename(csv_path))[0]
        jpg_path = os.path.join(DATA_DIR, stem + ".jpg")
        if os.path.exists(jpg_path):
            stems.append((stem, csv_path, jpg_path))

    def seq(item):
        try:
            return int(item[0].split("_")[0])
        except ValueError:
            return 10**9

    return sorted(stems, key=seq)


WINDOWS = load_windows()
if not WINDOWS:
    raise SystemExit(f"No matched CSV/JPG pairs found in '{DATA_DIR}/'.")

LABELS = {}
if os.path.exists(ANNOTATION_FILE):
    ann = pd.read_csv(ANNOTATION_FILE)
    LABELS = dict(zip(ann["filename"].astype(str), ann["label"]))

app = Dash(__name__)
app.title = "SIT225 6D - Replay of captured windows"

app.layout = html.Div(
    style={"fontFamily": "sans-serif", "maxWidth": "900px", "margin": "0 auto"},
    children=[
        html.H2("Accelerometer window + activity image (replay of saved capture)"),
        html.P(
            "Replay of windows already collected by live_capture.py - not a live "
            "Arduino IoT Cloud feed.",
            style={"color": "#a33", "fontWeight": "bold"},
        ),
        html.P(id="status-text"),
        html.Div(
            style={"display": "flex", "gap": "24px", "flexWrap": "wrap"},
            children=[
                dcc.Graph(id="accel-graph", style={"flex": "1 1 500px"}),
                html.Img(id="activity-image",
                         style={"maxWidth": "360px", "borderRadius": "8px"}),
            ],
        ),
        dcc.Interval(id="tick", interval=SECONDS_PER_WINDOW * 1000, n_intervals=0),
    ],
)


@app.callback(
    Output("accel-graph", "figure"),
    Output("activity-image", "src"),
    Output("status-text", "children"),
    Input("tick", "n_intervals"),
)
def step(n):
    stem, csv_path, jpg_path = WINDOWS[n % len(WINDOWS)]

    df = pd.read_csv(csv_path)
    fig = go.Figure()
    for axis in ("x", "y", "z"):
        if axis in df.columns:
            fig.add_trace(go.Scatter(y=df[axis], mode="lines", name=axis))
    fig.update_layout(
        title=os.path.basename(csv_path),
        xaxis_title="sample #",
        yaxis_title="acceleration",
        margin=dict(l=40, r=20, t=40, b=40),
    )

    with open(jpg_path, "rb") as f:
        image_src = "data:image/jpg;base64," + base64.b64encode(f.read()).decode()

    label = LABELS.get(stem)
    label_text = f"  |  label: {label} - {LABEL_NAMES.get(label, '?')}" if label is not None else ""
    status = (f"Window {n % len(WINDOWS) + 1} of {len(WINDOWS)}  |  {stem}  "
              f"|  {len(df)} samples{label_text}")
    return fig, image_src, status


if __name__ == "__main__":
    print(f"Replaying {len(WINDOWS)} saved windows at http://127.0.0.1:{PORT}")
    app.run(debug=False, port=PORT)
