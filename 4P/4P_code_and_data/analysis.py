"""
SIT225 4P - statistics, hypothesis tests and plots  (processed_data.csv -> results)

The 3P design compared individual showers, but no shower log was kept during collection and
showers do not leave a clear mark in Room B's humidity. So the data is analysed as one
continuous record of Room B, and each 3P hypothesis is tested as far as that record allows:

  H2  (tested)       Room B's damp exposure comes from a constantly high background, not from
                     shower peaks -> time above critical RH, regression on outdoor humidity (R^2, p)
  H1  (proxy test)   "Room B rises after a shower" -> humidity change in the hours when showers
                     usually happen vs all other hours (Mann-Whitney U). Room A was not measured.
  H3  (not testable) No record of which showers used the routine. Described instead: what
                     happens to Room B's humidity when its door/window is opened.

Outputs
  descriptive_stats.csv, correlation_matrix.csv, vent_events.csv, results_summary.txt
  figures/fig1_timeseries.png      time series (required plot 1)
  figures/fig2_distribution.png    histogram (required plot 2)
  figures/fig3_relationship.png    Room B vs outdoor humidity (required plot 3)
  figures/fig4_shower_hours.png    box plot: humidity change, usual shower hours vs other hours
  figures/fig5_vent_events.png     humidity after each door/window opening
  figures/fig6_correlation.png     correlation heatmap

Run:  python3 analysis.py
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy import stats
from config import *

os.makedirs(FIG_DIR, exist_ok=True)
out = []
def say(msg=""):
    print(msg)
    out.append(str(msg))

df = pd.read_csv(PROCESSED_CSV, parse_dates=["timestamp_local"])
df = df[df.room == "B"].copy()
ok = df.dropna(subset=["rh"])
SLOT_H = 0.5 / 60                                   # one 30 s slot, in hours

# plot style: one colour per series, grey for context
BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
INK, MUTED, GRID = "#0b0b0b", "#898781", "#e4e3df"
plt.rcParams.update({"font.size": 12, "figure.dpi": 150, "axes.edgecolor": MUTED,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
                     "axes.axisbelow": True, "axes.titleweight": "bold", "axes.titlesize": 13})

# ============================================================ 2.1 DESCRIPTIVE STATISTICS
series = {"Room B relative humidity (%)": ok["rh"], "Room B temperature (C)": ok["temp"],
          "Room B absolute humidity (g/m3)": ok["abs_hum"],
          "Outdoor relative humidity (%)": ok["outdoor_rh"], "Outdoor temperature (C)": ok["outdoor_temp"],
          "Outdoor absolute humidity (g/m3)": ok["outdoor_abs_hum"]}
desc = pd.DataFrame({k: {"mean": s.mean(), "median": s.median(), "std": s.std(), "min": s.min(),
                         "max": s.max(), "range": s.max() - s.min(), "p25": s.quantile(.25),
                         "p75": s.quantile(.75), "p95": s.quantile(.95), "n": s.count()}
                     for k, s in series.items()}).T.round(2)
desc.to_csv("descriptive_stats.csv")
say("=== 2.1 DESCRIPTIVE STATISTICS (30 s readings; outdoor = BOM value matched to each reading) ===")
say(desc.to_string())
say(f"Hours of data: {len(ok) * SLOT_H:.1f} (Room B), {ok['outdoor_rh'].notna().sum() * SLOT_H:.1f} with outdoor data")

# hourly means: used for correlation and regression so that 120 near-identical readings
# per hour are not counted as 120 independent observations
hourly = ok.set_index("timestamp_local")[["rh", "temp", "abs_hum", "outdoor_rh", "outdoor_temp",
                                          "outdoor_abs_hum", "hour"]].resample("1h").mean()
hourly = hourly[ok.set_index("timestamp_local")["rh"].resample("1h").count() >= 60]   # >= 30 min of data
both = hourly.dropna(subset=["outdoor_rh"])
corr = both.rename(columns={"rh": "Room B RH", "temp": "Room B temp", "abs_hum": "Room B abs. hum.",
                            "outdoor_rh": "Outdoor RH", "outdoor_temp": "Outdoor temp",
                            "outdoor_abs_hum": "Outdoor abs. hum."}).drop(columns="hour").corr().round(2)
corr.to_csv("correlation_matrix.csv")
say(f"\nCorrelation matrix (Pearson r, hourly means, n={len(both)} hours with outdoor data):")
say(corr.to_string())

# ============================================================ H2 (tested)
say("\n=== H2 (tested): Room B's damp exposure comes from a constantly high background humidity, "
    "not from shower peaks ===")
say("a) Time above each critical RH, and damp-hours (sum of RH minus critical RH while above it, %RH x h)")
for crit in CRITICAL_RH:
    above = ok["rh"] > crit
    dh = np.clip(ok["rh"] - crit, 0, None).sum() * SLOT_H
    say(f"   > {crit:.0f}% RH: {above.mean():6.1%} of recorded time ({above.sum() * SLOT_H:5.1f} h), damp-hours {dh:7.1f}")
say("b) Is the exposure concentrated in the hours when showers usually happen?")
for crit in (50.0, 70.0):
    for flag, name in [(True, "usual shower hours"), (False, "all other hours")]:
        g = ok[ok["usual_shower_hours"] == flag]
        say(f"   critical {crit:.0f}%: {name:19s} {len(g) * SLOT_H:5.1f} h recorded, "
            f"{np.clip(g['rh'] - crit, 0, None).sum() * SLOT_H / (len(g) * SLOT_H):5.2f} damp-hours per hour, "
            f"mean RH {g['rh'].mean():.1f}%")
say("c) Largest short-term RISE in the whole record (a shower peak would show up here)")
rise15 = ok.set_index("timestamp_local")["rh"]
rise15 = (rise15 - rise15.shift(30, freq="30s")).dropna()          # change over 15 minutes
rebound = ok.set_index("timestamp_local")["mins_since_vent"].reindex(rise15.index).between(0, 120)
calm15 = rise15[~rebound]                                          # ignore the rebound after a door/window opening
say(f"   biggest 15-min rise outside the 2 h after a door/window opening: +{calm15.max():.1f} % RH at "
    f"{calm15.idxmax():%a %d %b %H:%M}; 95th percentile of |15-min change|: {calm15.abs().quantile(.95):.1f} % RH")
say(f"   (inside those 2 h the biggest rise is +{rise15[rebound].max():.1f} % RH: the room returning to its damp level)")
say("d) Regression: hourly Room B humidity on hourly outdoor humidity")
lr = stats.linregress(both["outdoor_rh"], both["rh"])
say(f"   Room B RH = {lr.intercept:.1f} + {lr.slope:.3f} x outdoor RH;  R^2={lr.rvalue**2:.3f}, "
    f"p={lr.pvalue:.2g}, n={len(both)} hours")
resid = both["rh"] - (lr.intercept + lr.slope * both["outdoor_rh"])
say(f"   residual lag-1 autocorrelation = {resid.autocorr(1):.2f} (close to 1 = hours are not independent, "
    "so this p-value is too optimistic)")
chg = both[["rh", "outdoor_rh"]].diff()[both.index.to_series().diff() == pd.Timedelta("1h")].dropna()
lr_d = stats.linregress(chg["outdoor_rh"], chg["rh"])
say(f"   Hour-to-hour CHANGES (removes the shared slow trend): change in Room B = {lr_d.intercept:+.2f} + "
    f"{lr_d.slope:.3f} x change outdoors;  R^2={lr_d.rvalue**2:.3f}, p={lr_d.pvalue:.2g}, n={len(chg)}")
lr_ah = stats.linregress(both["outdoor_abs_hum"], both["abs_hum"])
say(f"   Same in absolute humidity (g/m3): Room B = {lr_ah.intercept:.2f} + {lr_ah.slope:.3f} x outdoor;  "
    f"R^2={lr_ah.rvalue**2:.3f}, p={lr_ah.pvalue:.2g}")
# daily averages remove most of the hour-to-hour dependence, but leave very few points
daily = ok.set_index("timestamp_local")[["rh", "outdoor_rh"]].resample("1D").mean().dropna()
say(f"   Daily means on days with outdoor data (n={len(daily)}): " +
    "; ".join(f"{d:%d %b} Room B {r.rh:.1f}% / outdoor {r.outdoor_rh:.1f}%" for d, r in daily.iterrows()))

# ============================================================ H1 (proxy test)
say("\n=== H1 (proxy test): does Room B's humidity rise in the hours when showers usually happen? ===")
say("Shower times were not logged, so 'usual shower hours' (11:00-15:00, 20:00-01:00, self-reported) "
    "stand in for them. Room A was not measured, so the A-vs-B half of H1 cannot be tested.")
blk = ok.set_index("timestamp_local")
agg = blk.resample("30min").agg(n=("rh", "count"), rh_first=("rh", "first"), rh_last=("rh", "last"),
                                ah_first=("abs_hum", "first"), ah_last=("abs_hum", "last"),
                                usual=("usual_shower_hours", "first"), vent=("mins_since_vent", "min"))
agg = agg[agg["n"] >= 54].copy()                                    # blocks with >= 90 % of readings
agg["d_rh"] = agg["rh_last"] - agg["rh_first"]
agg["d_ah"] = agg["ah_last"] - agg["ah_first"]
agg["vented"] = agg["vent"].notna() & (agg["vent"] < 120)           # within 2 h of a door/window opening
agg["usual"] = agg["usual"].astype(bool)

def mwu(label, x_shower, x_other, unit):
    u = stats.mannwhitneyu(x_shower, x_other, alternative="two-sided")
    rb = 2 * u.statistic / (len(x_shower) * len(x_other)) - 1       # +1 = shower hours always higher
    say(f"   {label}: usual shower hours median {x_shower.median():+.3f} {unit} (n={len(x_shower)} blocks), "
        f"other hours median {x_other.median():+.3f} {unit} (n={len(x_other)}), "
        f"Mann-Whitney U={u.statistic:.0f}, p={u.pvalue:.3f}, rank-biserial r={rb:+.2f}")

say("Change in humidity across each 30-minute block:")
mwu("Relative humidity, all blocks", agg.loc[agg.usual, "d_rh"], agg.loc[~agg.usual, "d_rh"], "% RH")
calm = agg[~agg.vented]
mwu("Relative humidity, excluding 2 h after door/window openings", calm.loc[calm.usual, "d_rh"],
    calm.loc[~calm.usual, "d_rh"], "% RH")
mwu("Absolute humidity, excluding 2 h after door/window openings", calm.loc[calm.usual, "d_ah"],
    calm.loc[~calm.usual, "d_ah"], "g/m3")

# ============================================================ H3 (not testable) + ventilation events
say("\n=== H3 (not testable): no record of which showers used the routine (door closed, window open) ===")
say("Described instead: Room B's humidity after each sudden drop. The occupant recalls these as times "
    "the Room B door or window was opened; they were detected from the data, not logged.")
rows = []
for vid, ev in df.dropna(subset=["vent_event_id"]).groupby("vent_event_id"):
    ev = ev.sort_values("mins_since_vent").dropna(subset=["rh"])
    pre = ev.loc[ev.mins_since_vent < 0, "rh"].mean()
    post = ev[ev.mins_since_vent >= 0]
    i_min = post["rh"].idxmin()
    after = post.loc[i_min:]
    back = after[after["rh"] >= pre - 1.0]                          # back within 1 % RH of the pre-level
    rows.append({"event": f"V{int(vid)}",
                 "start": ev.loc[ev.mins_since_vent >= 0, "timestamp_local"].iloc[0].strftime("%a %d %b %H:%M"),
                 "pre_rh": pre, "min_rh": post["rh"].min(), "drop_rh": pre - post["rh"].min(),
                 "mins_to_min": post.at[i_min, "mins_since_vent"],
                 "recovery_mins": back["mins_since_vent"].iloc[0] if len(back) else np.nan,
                 "followed_mins": post["mins_since_vent"].max(),
                 "drop_abs_hum": ev.loc[ev.mins_since_vent < 0, "abs_hum"].mean() - post["abs_hum"].min()})
vents = pd.DataFrame(rows)
vents.to_csv("vent_events.csv", index=False, float_format="%.2f")
say(vents.round(1).to_string(index=False))
say(f"Median drop {vents['drop_rh'].median():.1f} % RH, reached after a median of "
    f"{vents['mins_to_min'].median():.0f} min; back within 1 % RH of the starting level after a median of "
    f"{vents['recovery_mins'].median():.0f} min ({vents['recovery_mins'].notna().sum()} of {len(vents)} events "
    "recovered inside the time followed)")

# ============================================================ PLOTS
# Plot 1 - time series
fig, ax = plt.subplots(figsize=(13, 5.2))
t0, t1 = df["timestamp_local"].min(), df["timestamp_local"].max()
for day in pd.date_range(t0.normalize() - pd.Timedelta(days=1), t1.normalize(), freq="D"):
    for a, b in [(11, 15), (20, 25)]:                               # usual shower hours
        ax.axvspan(day + pd.Timedelta(hours=a), day + pd.Timedelta(hours=b), color="#f0efec", lw=0, zorder=0)
ax.plot(df["timestamp_local"], df["outdoor_rh"], color=ORANGE, lw=2, label="Outdoor (BOM, Olympic Park)")
ax.plot(df["timestamp_local"], df["rh"], color=BLUE, lw=2, label="Room B (DHT22)")
for _, v in vents.iterrows():
    tv = df.loc[(df.vent_event_id == int(v.event[1:])) & (df.mins_since_vent >= 0), "timestamp_local"].iloc[0]
    ax.annotate(v.event, (tv, v.min_rh), xytext=(0, -22), textcoords="offset points", ha="center",
                fontsize=10, color=INK, arrowprops={"arrowstyle": "-", "color": MUTED})
for a, b in [("2026-09-29 01:44", "2026-09-29 12:41"), ("2026-09-30 09:10", "2026-10-01 01:52")]:
    mid = pd.Timestamp(a) + (pd.Timestamp(b) - pd.Timestamp(a)) / 2
    ax.text(mid, 36, "board\noffline", ha="center", va="bottom", fontsize=10, color=MUTED)
ax.set_xlim(t0, t1); ax.set_ylim(30, 104)
ax.xaxis.set_major_locator(mdates.HourLocator(byhour=[0, 12]))
ax.xaxis.set_major_formatter(mdates.DateFormatter("%a %d\n%H:%M"))
h, _ = ax.get_legend_handles_labels()
h.append(plt.Rectangle((0, 0), 1, 1, color="#f0efec", label="Usual shower hours (11-15, 20-01)"))
ax.legend(handles=h[::-1], loc="upper left", fontsize=10, frameon=False, ncol=3)
ax.set(title="Plot 1. Room B and outdoor relative humidity, 28 Sep - 2 Oct 2026 (V = door/window opened)",
       xlabel="Local time (Melbourne)", ylabel="Relative humidity (%)")
fig.tight_layout(); fig.savefig(f"{FIG_DIR}/fig1_timeseries.png"); plt.close(fig)

# Plot 2 - distribution
fig, ax = plt.subplots(figsize=(9, 5))
s = ok["rh"]
ax.hist(s, bins=np.arange(48, 82, 0.5), density=True, color=BLUE, edgecolor="white", linewidth=0.4)
x = np.linspace(48, 82, 300)
ax.plot(x, stats.norm.pdf(x, s.mean(), s.std()), color=INK, lw=2,
        label=f"Normal curve (mean {s.mean():.1f}%, sd {s.std():.1f})")
for crit, lab in [(50, "50%: re-fitted\ncritical RH"), (60, "60%"), (70, "70%"), (80, "80%: original\nVTT critical RH")]:
    ax.axvline(crit, color=MUTED, lw=1, ls="--")
    ax.text(crit + (-0.3 if crit == 80 else 0.3), ax.get_ylim()[1] * 0.97, lab, fontsize=9, color="#52514e",
            va="top", ha="right" if crit == 80 else "left")
ax.set(title="Plot 2. Distribution of Room B relative humidity (30 s readings)",
       xlabel="Relative humidity (%)", ylabel="Density", xlim=(48, 82))
ax.legend(loc="center left", fontsize=10, frameon=False)
fig.tight_layout(); fig.savefig(f"{FIG_DIR}/fig2_distribution.png"); plt.close(fig)

# Plot 3 - relationship: Room B vs outdoor humidity (hourly means)
fig, ax = plt.subplots(figsize=(8, 6))
ax.scatter(both["outdoor_rh"], both["rh"], s=64, color=BLUE, edgecolor="white", linewidth=1.5, label="One hour of data")
xs = np.linspace(both["outdoor_rh"].min(), both["outdoor_rh"].max(), 50)
ax.plot(xs, lr.intercept + lr.slope * xs, color=INK, lw=2,
        label=f"Fit: Room B = {lr.intercept:.1f} + {lr.slope:.2f} x outdoor\nR$^2$ = {lr.rvalue**2:.2f}, n = {len(both)} hours")
ax.set(title="Plot 3. Room B humidity against outdoor humidity (hourly means)",
       xlabel="Outdoor relative humidity (%)", ylabel="Room B relative humidity (%)")
ax.legend(loc="lower right", fontsize=10, frameon=False)
fig.tight_layout(); fig.savefig(f"{FIG_DIR}/fig3_relationship.png"); plt.close(fig)

# Plot 4 - box plot: humidity change per 30-min block, usual shower hours vs other hours
fig, ax = plt.subplots(figsize=(7.5, 5))
data = [calm.loc[calm.usual, "d_rh"], calm.loc[~calm.usual, "d_rh"]]
bp = ax.boxplot(data, widths=0.5, patch_artist=True, showfliers=False,
                medianprops={"color": INK, "lw": 2}, boxprops={"facecolor": "#cde2fb", "edgecolor": BLUE},
                whiskerprops={"color": BLUE}, capprops={"color": BLUE})
rng = np.random.default_rng(0)
for i, d in enumerate(data, start=1):
    ax.scatter(np.full(len(d), i) + rng.uniform(-.18, .18, len(d)), d, s=14, color=BLUE, alpha=.55, zorder=3)
ax.axhline(0, color=MUTED, lw=1)
ax.set_xticks([1, 2], [f"Usual shower hours\n(n = {len(data[0])} blocks)", f"All other hours\n(n = {len(data[1])} blocks)"])
ax.set(title="Plot 4. Change in Room B humidity per 30 minutes (H1 proxy)",
       ylabel="Change in relative humidity over 30 min (% RH)")
fig.tight_layout(); fig.savefig(f"{FIG_DIR}/fig4_shower_hours.png"); plt.close(fig)

# Plot 5 - humidity after each door/window opening
fig, ax = plt.subplots(figsize=(10, 5))
ev_all = df.dropna(subset=["vent_event_id", "rh"])
for (vid, ev), colour in zip(ev_all.groupby("vent_event_id"), [BLUE, ORANGE, AQUA, YELLOW]):
    pre = ev.loc[ev.mins_since_vent < 0, "rh"].mean()
    v = vents[vents.event == f"V{int(vid)}"].iloc[0]
    ax.plot(ev["mins_since_vent"], ev["rh"] - pre, color=colour, lw=2, label=f"{v.event}: {v.start}")
ax.axhline(0, color=MUTED, lw=1); ax.axvline(0, color=MUTED, lw=1)
ax.set(title="Plot 5. Room B humidity after its door/window was opened",
       xlabel="Minutes since the humidity started to fall", ylabel="Change from the level before (% RH)",
       xlim=(-10, 180))
ax.legend(loc="lower right", fontsize=10, frameon=False)
fig.tight_layout(); fig.savefig(f"{FIG_DIR}/fig5_vent_events.png"); plt.close(fig)

# Plot 6 - correlation heatmap
fig, ax = plt.subplots(figsize=(7.5, 6.3))
im = ax.imshow(corr, cmap="RdBu_r", vmin=-1, vmax=1)
ax.set_xticks(range(len(corr)), corr.columns, rotation=40, ha="right")
ax.set_yticks(range(len(corr)), corr.index)
ax.grid(False)
for i in range(len(corr)):
    for j in range(len(corr)):
        val = corr.iloc[i, j]
        ax.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=10,
                color="white" if abs(val) > 0.6 else INK)
fig.colorbar(im, label="Pearson r")
ax.set_title(f"Plot 6. Correlation matrix (hourly means, {len(both)} h)", fontsize=12)
fig.tight_layout(); fig.savefig(f"{FIG_DIR}/fig6_correlation.png"); plt.close(fig)

with open("results_summary.txt", "w") as fh:
    fh.write("\n".join(out))
print(f"\nSaved results_summary.txt, descriptive_stats.csv, correlation_matrix.csv, vent_events.csv "
      f"and 6 plots in {FIG_DIR}/")
