import os
import time
import base64
import threading
from collections import deque
from datetime import datetime

import cv2
import numpy as np
import pandas as pd
import plotly.graph_objs as go
from dash import Dash, dcc, html
from dash.dependencies import Input, Output
from dotenv import load_dotenv

from arduino_iot_cloud import ArduinoCloudClient

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
load_dotenv()

DEVICE_ID = os.environ.get("ARDUINO_DEVICE_ID")
SECRET_KEY = os.environ.get("ARDUINO_SECRET_KEY")

if not DEVICE_ID or not SECRET_KEY:
    raise SystemExit(
        "Missing Arduino credentials. Copy '.env.example' to '.env' and fill "
        "in ARDUINO_DEVICE_ID and ARDUINO_SECRET_KEY."
    )

# Arduino IoT Cloud variable name -> internal axis name used for buffer/CSV columns
CLOUD_VARIABLE_MAP = {
    "accelerometer_x": "x",
    "accelerometer_y": "y",
    "accelerometer_z": "z",
}

DATA_DIR = "data"
WINDOW_SECONDS = 10
WEBCAM_INDEX = 0
DASHBOARD_PORT = 8050
GRAPH_REFRESH_MS = 2000

os.makedirs(DATA_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Shared state (written by the cloud callback + capture thread, read by Dash)
# ---------------------------------------------------------------------------
lock = threading.Lock()
buffer = {"x": deque(), "y": deque(), "z": deque()}
sequence_number = 1
latest_csv_path = None
latest_jpg_path = None
windows_saved = 0


def _on_axis_changed(internal_axis):
    def _callback(client, value):
        with lock:
            buffer[internal_axis].append(value)
    return _callback


def build_cloud_client() -> ArduinoCloudClient:
    client = ArduinoCloudClient(device_id=DEVICE_ID, username=DEVICE_ID, password=SECRET_KEY)
    for cloud_var_name, internal_axis in CLOUD_VARIABLE_MAP.items():
        client.register(cloud_var_name, value=None, on_write=_on_axis_changed(internal_axis))
    return client


def capture_webcam_frame(filepath: str) -> bool:
    cam = cv2.VideoCapture(WEBCAM_INDEX)
    ok, frame = cam.read()
    if ok:
        cv2.imwrite(filepath, frame)
    else:
        print(f"[WARN] Could not read a webcam frame for {filepath}")
    cam.release()
    return ok


def save_window(seq: int, x_vals, y_vals, z_vals):
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    base = f"{seq}_{ts}"
    csv_path = os.path.join(DATA_DIR, f"{base}.csv")
    jpg_path = os.path.join(DATA_DIR, f"{base}.jpg")

    n = min(len(x_vals), len(y_vals), len(z_vals))
    df = pd.DataFrame({
        "sample_index": range(n),
        "x": list(x_vals)[:n],
        "y": list(y_vals)[:n],
        "z": list(z_vals)[:n],
    })
    df.to_csv(csv_path, index=False)
    capture_webcam_frame(jpg_path)
    return base, csv_path, jpg_path, df


def capture_loop():
    global sequence_number, latest_csv_path, latest_jpg_path, windows_saved

    while True:
        time.sleep(WINDOW_SECONDS)

        with lock:
            x_vals, y_vals, z_vals = list(buffer["x"]), list(buffer["y"]), list(buffer["z"])
            buffer["x"].clear()
            buffer["y"].clear()
            buffer["z"].clear()

        if not x_vals:
            print("[INFO] No accelerometer samples arrived this window - skipping capture.")
            continue

        base, csv_path, jpg_path, df = save_window(sequence_number, x_vals, y_vals, z_vals)
        print(f"[SAVED] {csv_path}  ({len(df)} samples)  +  {jpg_path}")

        latest_csv_path = csv_path
        latest_jpg_path = jpg_path
        windows_saved += 1
        sequence_number += 1


# ---------------------------------------------------------------------------
# Dash dashboard
# ---------------------------------------------------------------------------
app = Dash(__name__)
app.title = "SIT225 6D - Live Activity Capture"

app.layout = html.Div(
    style={"fontFamily": "sans-serif", "maxWidth": "900px", "margin": "0 auto"},
    children=[
        html.H2("Live Accelerometer + Activity Image"),
        html.P(id="status-text"),
        html.Div(
            style={"display": "flex", "gap": "24px", "flexWrap": "wrap"},
            children=[
                dcc.Graph(id="accel-graph", style={"flex": "1 1 500px"}),
                html.Img(id="activity-image", style={"maxWidth": "360px", "borderRadius": "8px"}),
            ],
        ),
        dcc.Interval(id="refresh-interval", interval=GRAPH_REFRESH_MS, n_intervals=0),
    ],
)


@app.callback(
    Output("accel-graph", "figure"),
    Output("activity-image", "src"),
    Output("status-text", "children"),
    Input("refresh-interval", "n_intervals"),
)
def refresh_dashboard(_):
    if latest_csv_path is None:
        return go.Figure(), "", "Waiting for the first 10-second window..."

    df = pd.read_csv(latest_csv_path)
    fig = go.Figure()
    for axis in ("x", "y", "z"):
        fig.add_trace(go.Scatter(y=df[axis], mode="lines", name=axis))
    fig.update_layout(
        title=os.path.basename(latest_csv_path),
        xaxis_title="sample #",
        yaxis_title="acceleration",
        margin=dict(l=40, r=20, t=40, b=40),
    )

    image_src = ""
    if latest_jpg_path and os.path.exists(latest_jpg_path):
        with open(latest_jpg_path, "rb") as f:
            image_src = "data:image/jpg;base64," + base64.b64encode(f.read()).decode()

    status = f"Windows saved so far: {windows_saved}  |  latest: {os.path.basename(latest_csv_path)}"
    return fig, image_src, status


if __name__ == "__main__":
    print("Connecting to Arduino IoT Cloud...")
    cloud_client = build_cloud_client()
    threading.Thread(target=cloud_client.start, daemon=True).start()

    print(f"Starting capture loop ({WINDOW_SECONDS}s windows, saving to '{DATA_DIR}/')...")
    threading.Thread(target=capture_loop, daemon=True).start()

    print(f"Dashboard running at http://127.0.0.1:{DASHBOARD_PORT}")
    app.run(debug=False, port=DASHBOARD_PORT)
