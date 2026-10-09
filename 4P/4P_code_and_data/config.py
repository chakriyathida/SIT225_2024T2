"""
SIT225 4P - shared settings. Edit THIS file, not the other scripts.
Every script does `from config import *`.

One DHT22 on a Nano 33 IoT. It stayed in ROOM B (the bedroom next to the bathroom) for the
whole capture, 28 Sep - 2 Oct 2026. No Room A session was run and no shower log was kept, so
the analysis treats the data as one continuous record (see the deviations table in the report).
"""
import os

# ---- Firebase (same project you used in the Week 5 activity) ------------------
FIREBASE_DATABASE_URL = os.environ.get(
    "FIREBASE_DATABASE_URL", "https://data-capture-unit-default-rtdb.firebaseio.com/")
FIREBASE_CREDENTIALS_PATH = os.environ.get(
    "FIREBASE_CREDENTIALS_PATH", "service-account.json")   # never put this file in the PDF
FIREBASE_PATH = "/readings/dht22"                          # where the Nano 33 IoT writes

# ---- Time zone ----------------------------------------------------------------
LOCAL_TZ = "Australia/Melbourne"   # everything is stored in UTC and shown in Melbourne time

# ---- Where the sensor was, and when (local time). Fill these in as you go. ------
# Start each window ~30 min AFTER you put the sensor down, so it has settled to the room.
ROOM_B_START = "2026-09-28 14:00"   # sensor placed ~13:03-13:31, 30 min allowed to settle
ROOM_B_END = "2026-10-02 17:49"     # last reading before the board was unplugged
ROOM_A_START = None                 # no Room A session was run
ROOM_A_END = None

# ---- Files --------------------------------------------------------------------
RAW_CSV = "raw_data.csv"             # everything the sensor sent, untouched -> submit (raw)
BOM_CSV = "bom_outdoor.csv"          # outdoor humidity from BOM, appended daily
SHOWER_LOG = "shower_log.csv"        # you fill this in by hand after every shower
SCHEDULE_CSV = "shower_schedule.csv" # random condition list made BEFORE collection starts
PROCESSED_CSV = "processed_data.csv" # cleaned 30 s grid -> submit (processed)
EVENTS_CSV = "shower_events.csv"     # one row per shower (H1-H3 measures)
QUALITY_TXT = "data_quality_report.txt"
FIG_DIR = "figures"

# ---- Cleaning rules ------------------------------------------------------------
RH_RANGE = (0, 100)          # physically possible humidity, %
TEMP_RANGE = (-10, 50)       # indoor temperature, deg C (DHT22 is rated -40..80)
SPIKE_RH = 8.0               # a reading this far (% RH) from its 5-reading median is a sensor glitch
MAX_GAP_FILL_MIN = 2         # interpolate gaps up to 2 minutes; longer gaps stay missing

# ---- Shower event definitions (from the 3P revised design, Appendix B.3) ------
BASELINE_MIN = 10            # baseline = mean of the 10 minutes before the shower starts
EVENT_WINDOW_MIN = 180       # look 3 hours after the shower starts
THRESHOLD_RH = 70.0          # 3P threshold: minutes above 70 % RH
SECONDARY_THRESHOLD_RH = 60.0  # 1P showed rooms may never reach 70 %; 60 % is the fallback
DWELL_ABOVE_BASELINE = 3.0   # "still damp" = more than 3 % RH above the room's own baseline
PEAK_PHASE_EXTRA_MIN = 10    # H2: "peak phase" = shower start until 10 min after the peak

# ---- Continuous-record analysis (used because no shower log was kept) ----------
# Hours of the day when showers USUALLY happen (self-reported afterwards, not logged):
# 11:00-15:00 and 20:00-01:00. Used only as a proxy; exact shower times are unknown.
USUAL_SHOWER_HOURS = [11, 12, 13, 14, 20, 21, 22, 23, 0]
CRITICAL_RH = (50.0, 60.0, 70.0, 80.0)   # 80 = original VTT, 50 = re-fitted (Menneer et al. 2022)
VENT_DROP_RH = 3.0           # a fall of >= 3 % RH within 5 minutes = door/window opened in Room B
VENT_DROP_WINDOW_MIN = 5
VENT_RECOVERY_MAX_MIN = 180  # follow each ventilation event for up to 3 hours
