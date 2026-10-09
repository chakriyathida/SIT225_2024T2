import csv
import sys
import threading
from datetime import datetime

from arduino_iot_cloud import ArduinoCloudClient

# ---------------------------------------------------------------------------
# Credentials - from Arduino Cloud > Devices > your Python device
# ---------------------------------------------------------------------------
DEVICE_ID = "edfd284c-9b50-434e-8552-528b0c46fc73"
SECRET_KEY = "<hidden for submission>"

VAR_X = "accelerometer_x"
VAR_Y = "accelerometer_y"
VAR_Z = "accelerometer_z"

OUTPUT_FILE = "accelerometer_xyz.csv"

# ---------------------------------------------------------------------------
# Buffer holding the most recent value of each axis.
# A row is written only when all three slots are filled.
# ---------------------------------------------------------------------------
buffer = {"x": None, "y": None, "z": None}
lock = threading.Lock()
rows_written = 0


def timestamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def store(axis, value):
    """Save one axis value; write a full row once x, y and z are all present."""
    global rows_written

    with lock:
        buffer[axis] = value

        # Not a complete set yet - wait for the remaining axes
        if None in buffer.values():
            return

        row = [timestamp(), buffer["x"], buffer["y"], buffer["z"]]

        with open(OUTPUT_FILE, "a", newline="") as f:
            csv.writer(f).writerow(row)

        rows_written += 1
        print(f"[{rows_written:4d}] {row[0]}  "
              f"x={row[1]:+.4f}  y={row[2]:+.4f}  z={row[3]:+.4f}")

        # Clear the buffer so the next reading starts a fresh set
        for k in buffer:
            buffer[k] = None


# ---------------------------------------------------------------------------
# One call-back function per variable
# ---------------------------------------------------------------------------
def on_x_changed(client, value):
    store("x", value)


def on_y_changed(client, value):
    store("y", value)


def on_z_changed(client, value):
    store("z", value)


def main():
    with open(OUTPUT_FILE, "w", newline="") as f:
        csv.writer(f).writerow(["timestamp", "x", "y", "z"])
    print(f"Created {OUTPUT_FILE}")

    client = ArduinoCloudClient(
        device_id=DEVICE_ID,
        username=DEVICE_ID,
        password=SECRET_KEY,
        sync_mode=False,
    )

    client.register(VAR_X, value=None, on_write=on_x_changed)
    client.register(VAR_Y, value=None, on_write=on_y_changed)
    client.register(VAR_Z, value=None, on_write=on_z_changed)

    print("\nListening for accelerometer data... press Ctrl+C to stop.\n")
    client.start()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\nStopped. {rows_written} rows saved to {OUTPUT_FILE}.")
        sys.exit(0)
