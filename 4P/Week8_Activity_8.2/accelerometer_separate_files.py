import csv
import sys
from datetime import datetime

from arduino_iot_cloud import ArduinoCloudClient

# ---------------------------------------------------------------------------
# Credentials - from Arduino Cloud > Devices > your Python device
# ---------------------------------------------------------------------------
DEVICE_ID = "edfd284c-9b50-434e-8552-528b0c46fc73"
SECRET_KEY = "<hidden for submission>"

# Variable names must match the variable names in your Python Thing exactly
VAR_X = "accelerometer_x"
VAR_Y = "accelerometer_y"
VAR_Z = "accelerometer_z"

FILES = {
    VAR_X: "accelerometer_x.csv",
    VAR_Y: "accelerometer_y.csv",
    VAR_Z: "accelerometer_z.csv",
}


def timestamp():
    """Current local time, to millisecond precision."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def append_row(filename, value):
    """Append one '<timestamp>,<value>' line to the given CSV file."""
    with open(filename, "a", newline="") as f:
        csv.writer(f).writerow([timestamp(), value])


# ---------------------------------------------------------------------------
# One call-back function per variable
# ---------------------------------------------------------------------------
def on_x_changed(client, value):
    append_row(FILES[VAR_X], value)
    print(f"x = {value:+.4f}")


def on_y_changed(client, value):
    append_row(FILES[VAR_Y], value)
    print(f"y = {value:+.4f}")


def on_z_changed(client, value):
    append_row(FILES[VAR_Z], value)
    print(f"z = {value:+.4f}")


def main():
    # Write a header row into each file before we start
    for name, filename in FILES.items():
        with open(filename, "w", newline="") as f:
            csv.writer(f).writerow(["timestamp", "value"])
        print(f"Created {filename}")

    client = ArduinoCloudClient(
        device_id=DEVICE_ID,
        username=DEVICE_ID,
        password=SECRET_KEY,
        sync_mode=False,
    )

    # Register each cloud variable with its own call-back
    client.register(VAR_X, value=None, on_write=on_x_changed)
    client.register(VAR_Y, value=None, on_write=on_y_changed)
    client.register(VAR_Z, value=None, on_write=on_z_changed)

    print("\nListening for accelerometer data... press Ctrl+C to stop.\n")
    client.start()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped. CSV files saved.")
        sys.exit(0)
