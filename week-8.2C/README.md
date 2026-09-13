# SIT225 5C — Smooth live Plotly Dash update

Phone accelerometer data streamed through Arduino IoT Cloud into a Plotly Dash
graph that updates smoothly instead of jumping every 20 samples.

## Files

| File | What it is |
|---|---|
| `smooth_dash.py` | The `smooth_graph()` function |
| `dash_app.py` | The accelerometer dashboard |
| `SIT225-5C.ipynb` | Notebook that builds it step by step |
| `accelerometer_5c.csv` | Recorded data |
| `screenshots/` | Graph screenshots |

## How it works

1. Data arriving from the phone goes into a list.
2. Ten times a second, whatever is in the list is **added** to the graph lines
   using Plotly's `extendData`, so the graph is never rebuilt.
3. The x-axis window slides a little each time, so the graph scrolls.

## Running

```bash
pip install "dash>=2.11" plotly arduino-iot-cloud

export ARDUINO_DEVICE_ID=your-device-id
export ARDUINO_SECRET_KEY=your-secret-key

python dash_app.py     # http://127.0.0.1:8050
```

Credentials are read from the environment, never committed.
