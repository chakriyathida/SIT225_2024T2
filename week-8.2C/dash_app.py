"""dash_app.py — smooth live accelerometer graph (SIT225 5C).

    export ARDUINO_DEVICE_ID=your-device-id
    export ARDUINO_SECRET_KEY=your-secret-key
    python dash_app.py
"""

import os
import threading

from dash import Dash
from arduino_iot_cloud import ArduinoCloudClient

from smooth_dash import smooth_graph

app = Dash(__name__)
layout, add_point = smooth_graph(app, ["x", "y", "z"],
                                 y_range=(-2, 2), title="Phone accelerometer")
app.layout = layout

latest = {}


def got_value(axis, value):
    """x, y and z arrive separately. Collect all three, then send one point."""
    latest[axis] = value
    if len(latest) == 3:
        add_point(dict(latest))
        latest.clear()


if __name__ == "__main__":
    client = ArduinoCloudClient(
        device_id=os.environ["ARDUINO_DEVICE_ID"],
        username=os.environ["ARDUINO_DEVICE_ID"],
        password=os.environ["ARDUINO_SECRET_KEY"],
        sync_mode=False,
    )
    client.register("accelerometer_x", value=None, on_write=lambda c, v: got_value("x", v))
    client.register("accelerometer_y", value=None, on_write=lambda c, v: got_value("y", v))
    client.register("accelerometer_z", value=None, on_write=lambda c, v: got_value("z", v))
    threading.Thread(target=client.start, daemon=True).start()

    print("open http://127.0.0.1:8050")
    app.run()
