"""
SIT225 4P - processing pipeline  (raw_data.csv  ->  processed_data.csv)

  1. LOAD       raw_data.csv, bom_outdoor.csv
  2. VALIDATE   missing values, duplicates, data types, sampling interval, long gaps
  3. CLEAN      remove duplicates, out-of-range values, single-reading spikes, and the
                first 15 minutes after each long outage (sensor re-settling)
  4. LOCATE     keep the Room B window from config.py (the sensor never left Room B)
  5. ALIGN      put readings on a regular 30 s grid; fill gaps <= 2 min only
  6. TRANSFORM  local time, time of day, 5-min moving average, absolute humidity,
                outdoor humidity (BOM), "usual shower hours" flag, ventilation events
  7. EXPORT     processed_data.csv + data_quality_report.txt

No shower log was kept, so readings cannot be tagged with a shower number or condition.
Instead each reading is flagged by whether it falls in the hours when showers usually
happen, and sudden humidity drops (door/window opened) are detected from the data itself.

Run:  python3 process.py
"""
import os
import numpy as np
import pandas as pd
from config import *

report = []
def say(msg=""):
    print(msg)
    report.append(str(msg))

def utc(s):
    """'2026-09-29 12:00' (Melbourne time) -> UTC timestamp."""
    return pd.Timestamp(s).tz_localize(LOCAL_TZ).tz_convert("UTC")

def abs_humidity(temp_c, rh):
    """Grams of water vapour per cubic metre of air (Magnus formula).
    Relative humidity changes when the room warms or cools; absolute humidity does not."""
    svp = 6.112 * np.exp(17.62 * temp_c / (243.12 + temp_c))      # saturation vapour pressure, hPa
    return 216.7 * (rh / 100 * svp) / (273.15 + temp_c)

# ---------------------------------------------------------------- 1. LOAD
raw = pd.read_csv(RAW_CSV)
raw["timestamp_utc"] = pd.to_datetime(raw["timestamp_utc"], utc=True, format="ISO8601")
say("=== SIT225 4P DATA QUALITY REPORT ===")
say(f"Raw file: {RAW_CSV}   shape: {raw.shape}")
say(f"First reading: {raw['timestamp_utc'].min().tz_convert(LOCAL_TZ):%a %d %b %H:%M}   "
    f"last reading: {raw['timestamp_utc'].max().tz_convert(LOCAL_TZ):%a %d %b %H:%M} ({LOCAL_TZ})")

# ---------------------------------------------------------------- 2. VALIDATE
say("\n-- Data types --")
say(raw.dtypes.to_string())
say("\n-- Missing values per column (raw) --")
say(raw.isnull().sum().to_string())
say("\n-- Read status --")
say(raw["status"].value_counts().to_string())
dups = raw.duplicated(subset=["timestamp_utc"]).sum()
say(f"\nDuplicate timestamps: {dups}")
ts = raw["timestamp_utc"].sort_values().reset_index(drop=True)
gaps = ts.diff().dt.total_seconds()
say(f"Median sampling interval {gaps.median():.0f} s; {(gaps > 300).sum()} gaps longer than 5 min")
for i in gaps[gaps > 300].index:
    say(f"   gap of {gaps[i] / 60:.0f} min: {ts[i - 1].tz_convert(LOCAL_TZ):%a %d %b %H:%M} "
        f"to {ts[i].tz_convert(LOCAL_TZ):%a %d %b %H:%M}")

# ---------------------------------------------------------------- 3. CLEAN
n0 = len(raw)
raw = raw.drop_duplicates(subset=["timestamp_utc"]).sort_values("timestamp_utc").reset_index(drop=True)
raw["temperature"] = pd.to_numeric(raw["temperature"], errors="coerce")
raw["humidity"] = pd.to_numeric(raw["humidity"], errors="coerce")
bad_rh = ~raw["humidity"].between(*RH_RANGE) & raw["humidity"].notna()
bad_t = ~raw["temperature"].between(*TEMP_RANGE) & raw["temperature"].notna()
raw.loc[bad_rh, "humidity"] = np.nan
raw.loc[bad_t, "temperature"] = np.nan
med = raw["humidity"].rolling(5, center=True, min_periods=3).median()
spike = (raw["humidity"] - med).abs() > SPIKE_RH
raw.loc[spike, "humidity"] = np.nan
# after an outage of more than 30 min the board restarts warm; drop its first 15 minutes
gap_s = raw["timestamp_utc"].diff().dt.total_seconds()
restart = raw["timestamp_utc"].where(gap_s > 1800).ffill()
settling = (raw["timestamp_utc"] - restart) < pd.Timedelta(minutes=15)
n_settle = int((settling & raw["humidity"].notna()).sum())
raw.loc[settling, ["humidity", "temperature"]] = np.nan
say("\n-- Cleaning --")
say(f"Duplicates removed: {n0 - len(raw)}")
say(f"Humidity outside {RH_RANGE} %: {int(bad_rh.sum())}   Temperature outside {TEMP_RANGE} C: {int(bad_t.sum())}")
say(f"Humidity spikes (> {SPIKE_RH} % from rolling median of 5) removed: {int(spike.sum())}")
say(f"Readings in the first 15 min after an outage > 30 min (re-settling) removed: {n_settle}")

# ---------------------------------------------------------------- 4 + 5. LOCATE and ALIGN
grid = raw.set_index("timestamp_utc")[["temperature", "humidity"]].resample("30s").mean()
grid = grid.rename(columns={"temperature": "temp", "humidity": "rh"})
windows = [("B", ROOM_B_START, ROOM_B_END)]
if ROOM_A_START and ROOM_A_END:
    windows.append(("A", ROOM_A_START, ROOM_A_END))

parts = []
say("\n-- Location window and 30 s alignment --")
for room, start, end in windows:
    part = grid.loc[utc(start):utc(end)].copy()
    n_slots, miss0 = len(part), part["rh"].isna().sum()
    for c in ["temp", "rh"]:
        part[c] = part[c].interpolate(limit=MAX_GAP_FILL_MIN * 2, limit_area="inside")
    miss1 = part["rh"].isna().sum()
    part["room"] = room
    parts.append(part)
    say(f"Room {room}: {start} to {end}  ->  {n_slots} slots = {n_slots / 120:.1f} h | missing "
        f"{miss0} ({miss0 / max(n_slots, 1):.1%}) -> interpolated {miss0 - miss1} -> still missing "
        f"{miss1} ({miss1 / max(n_slots, 1):.1%})")
wide = pd.concat(parts)
outside = grid["rh"].notna().sum() - sum(grid.loc[utc(s):utc(e), "rh"].notna().sum() for _, s, e in windows)
say(f"Readings before the window start (sensor settling), not analysed: {outside} slots")

# ---------------------------------------------------------------- 6. TRANSFORM
wide.index.name = "timestamp_utc"
wide = wide.reset_index()
wide["timestamp_local"] = wide["timestamp_utc"].dt.tz_convert(LOCAL_TZ)
wide["hour"] = wide["timestamp_local"].dt.hour
wide["time_of_day"] = pd.cut(wide["hour"], bins=[-1, 5, 11, 17, 23],
                             labels=["night", "morning", "afternoon", "evening"])
wide["rh_5min"] = wide["rh"].rolling(10, min_periods=5).mean()
wide["abs_hum"] = abs_humidity(wide["temp"], wide["rh"])
wide["usual_shower_hours"] = wide["hour"].isin(USUAL_SHOWER_HOURS)

if os.path.exists(BOM_CSV):
    bom = pd.read_csv(BOM_CSV)
    bom["timestamp_utc"] = pd.to_datetime(bom["timestamp_utc"], utc=True, format="ISO8601")
    bom["outdoor_abs_hum"] = abs_humidity(bom["outdoor_temp"], bom["outdoor_rh"])
    wide = pd.merge_asof(wide.sort_values("timestamp_utc"),
                         bom[["timestamp_utc", "outdoor_rh", "outdoor_temp", "outdoor_abs_hum"]]
                         .sort_values("timestamp_utc"),
                         on="timestamp_utc", direction="nearest", tolerance=pd.Timedelta("35min"))
    has_out = wide["outdoor_rh"].notna() & wide["rh"].notna()
    say(f"\nOutdoor (BOM) data matched to {has_out.sum()} of {wide['rh'].notna().sum()} indoor readings "
        f"({has_out.sum() / 120:.1f} h); BOM only keeps 72 h, so earlier readings have no outdoor value")
else:
    wide["outdoor_rh"] = wide["outdoor_temp"] = wide["outdoor_abs_hum"] = np.nan
    say("WARNING: bom_outdoor.csv not found - outdoor humidity left empty")

# Ventilation events: humidity falls >= VENT_DROP_RH within VENT_DROP_WINDOW_MIN minutes
lag = VENT_DROP_WINDOW_MIN * 2                      # 30 s slots
drop = wide["rh"] - wide["rh"].shift(lag)
hit = wide.index[drop <= -VENT_DROP_RH]
wide["vent_event_id"] = pd.NA
wide["mins_since_vent"] = np.nan
starts, last = [], None
for i in hit:                                       # hits less than 30 min apart = same event
    if last is None or (wide.at[i, "timestamp_utc"] - last) > pd.Timedelta(minutes=30):
        starts.append(wide.loc[i - lag:i, "rh"].idxmax())   # the event starts where the fall began
    last = wide.at[i, "timestamp_utc"]
for n, i0 in enumerate(starts, start=1):
    t0 = wide.at[i0, "timestamp_utc"]
    mins = (wide["timestamp_utc"] - t0).dt.total_seconds() / 60
    nxt = wide.at[starts[n], "timestamp_utc"] if n < len(starts) else None
    in_win = (mins >= -BASELINE_MIN) & (mins < VENT_RECOVERY_MAX_MIN)
    if nxt is not None:
        in_win &= wide["timestamp_utc"] < nxt - pd.Timedelta(minutes=BASELINE_MIN)
    wide.loc[in_win, "vent_event_id"] = n
    wide.loc[in_win, "mins_since_vent"] = mins[in_win]
say(f"Ventilation events detected (fall >= {VENT_DROP_RH} % RH within {VENT_DROP_WINDOW_MIN} min): {len(starts)}")
for n, i0 in enumerate(starts, start=1):
    say(f"   V{n}: {wide.at[i0, 'timestamp_local']:%a %d %b %H:%M}")

# ---------------------------------------------------------------- 7. EXPORT
wide["timestamp_local"] = wide["timestamp_local"].dt.strftime("%Y-%m-%d %H:%M:%S")
wide["timestamp_utc"] = wide["timestamp_utc"].dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
cols = ["timestamp_utc", "timestamp_local", "room", "hour", "time_of_day", "usual_shower_hours",
        "temp", "rh", "rh_5min", "abs_hum", "outdoor_rh", "outdoor_temp", "outdoor_abs_hum",
        "vent_event_id", "mins_since_vent"]
wide[cols].to_csv(PROCESSED_CSV, index=False, float_format="%.3f")
say(f"\nFINAL: {len(wide)} rows in {PROCESSED_CSV}; {wide['rh'].notna().sum()} with a humidity value "
    f"= {wide['rh'].notna().sum() / 120:.1f} h of data")

with open(QUALITY_TXT, "w") as fh:
    fh.write("\n".join(report))
print(f"\nSaved {PROCESSED_CSV} and {QUALITY_TXT}")
