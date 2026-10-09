"""
SIT225 4P - data ingestion from the cloud (Firebase -> Pandas -> raw_data.csv)

The Nano 33 IoT sends a reading to Firebase every 30 s. This script:
  * downloads every reading already in Firebase into a Pandas DataFrame (the buffer)
  * then, every 60 s, downloads only the NEW readings, adds a proper timestamp column,
    appends them to the buffer and re-saves raw_data.csv
  * prints the latest reading so you can watch it live (use this for the video)
  * warns if the sensor has gone quiet for more than 5 minutes (heartbeat check from 3P)

Run during collection (leave it open, Ctrl+C to stop):   python3 live_monitor.py
Run once at the end just to download everything:          python3 live_monitor.py --once
"""
import sys
import time
from datetime import datetime

import pandas as pd
import firebase_admin
from firebase_admin import credentials, db

from config import (FIREBASE_DATABASE_URL, FIREBASE_CREDENTIALS_PATH, FIREBASE_PATH,
                    RAW_CSV, LOCAL_TZ)

POLL_S = 60             # check Firebase every minute
SILENT_S = 300          # warn if the newest reading is older than 5 minutes

cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
firebase_admin.initialize_app(cred, {"databaseURL": FIREBASE_DATABASE_URL})
ref = db.reference(FIREBASE_PATH)


def to_frame(data):
    """Firebase dict {push_key: {temperature, humidity, ok, ts}} -> tidy DataFrame."""
    rows = []
    for key, r in (data or {}).items():
        ok = r.get("ok", True)
        rows.append({
            "firebase_key": key,
            "timestamp_utc": pd.to_datetime(r["ts"], unit="ms", utc=True),
            "temperature": r["temperature"] if ok else None,   # failed reads kept as missing
            "humidity": r["humidity"] if ok else None,
            "status": "ok" if ok else "read_error",
        })
    return pd.DataFrame(rows, columns=["firebase_key", "timestamp_utc", "temperature",
                                       "humidity", "status"])


def save(buffer):
    out = buffer.sort_values("timestamp_utc").copy()
    out["timestamp_utc"] = out["timestamp_utc"].dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    out[["timestamp_utc", "temperature", "humidity", "status", "firebase_key"]].to_csv(RAW_CSV, index=False)


# ---- first full download -------------------------------------------------------
buffer = to_frame(ref.get())
save(buffer)
print(f"Downloaded {len(buffer)} readings -> {RAW_CSV}")
if "--once" in sys.argv or buffer.empty:
    if buffer.empty:
        print("No readings in Firebase yet - is the Nano 33 IoT on and showing HTTP 200?")
    sys.exit()

# ---- live loop ------------------------------------------------------------------
last_key = buffer["firebase_key"].max()      # push keys sort in time order
print("Live monitoring - Ctrl+C to stop")
try:
    while True:
        time.sleep(POLL_S)
        new = to_frame(ref.order_by_key().start_at(last_key).get())
        new = new[new["firebase_key"] != last_key]
        if not new.empty:
            buffer = pd.concat([buffer, new], ignore_index=True)
            last_key = new["firebase_key"].max()
            save(buffer)
        latest = buffer.sort_values("timestamp_utc").iloc[-1]
        age = (pd.Timestamp.now(tz="UTC") - latest["timestamp_utc"]).total_seconds()
        local = latest["timestamp_utc"].tz_convert(LOCAL_TZ).strftime("%a %H:%M:%S")
        print(f"{datetime.now():%H:%M:%S}  +{len(new)} new | total {len(buffer)} | latest {local}  "
              f"{latest['temperature']} C  {latest['humidity']} % RH")
        if age > SILENT_S:
            print(f"   WARNING: no reading for {int(age / 60)} min - check the charger and WiFi")
except KeyboardInterrupt:
    save(buffer)
    print(f"\nStopped. {len(buffer)} readings saved to {RAW_CSV}")
