"""Loading, cleaning and time alignment of MWV wind data."""

import sqlite3
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

DATA_DIR = Path("~/Data/Western_Flyer/nmea-logger").expanduser()
DB_NAMES = [f"nmea_database-2026-{i}.sdb" for i in range(1, 5)]
TALKERS = {"FT": "ft", "WI": "wi"}


def default_paths(data_dir=DATA_DIR):
    return [Path(data_dir) / n for n in DB_NAMES]


def clean(df):
    """Drop NaN, out-of-range values and duplicate (timestamp, talker) rows.

    Expects raw columns timestamp, talker, aws_knots (speed, knots), awa (direction, deg).
    """
    df = df.dropna(subset=["timestamp", "talker", "aws_knots", "awa"])
    df = df[(df["aws_knots"] >= 0) & (df["awa"] >= 0) & (df["awa"] <= 360)]
    df = df[df["talker"].isin(TALKERS)]
    return df.drop_duplicates(subset=["timestamp", "talker"])


def bin_sums(df, bin_s=1):
    """Per (time bin, talker) partial sums so that chunks can be merged exactly.

    Direction is accumulated as unit vectors (never averaged as angles).
    """
    rad = np.deg2rad(df["awa"].to_numpy())
    work = pd.DataFrame({
        "bin": (df["timestamp"].to_numpy() // (1000 * bin_s)).astype("int64"),
        "talker": df["talker"].to_numpy(),
        "spd": df["aws_knots"].to_numpy(),
        "sx": np.sin(rad),
        "sy": np.cos(rad),
    })
    work["n"] = 1
    return work.groupby(["bin", "talker"], as_index=False).sum()


def _finalize(sums, bin_s):
    g = sums.groupby(["bin", "talker"], as_index=False).sum()
    out = pd.DataFrame({
        "ts": pd.to_datetime(g["bin"] * bin_s, unit="s", utc=True),
        "talker": g["talker"],
        "spd": g["spd"] / g["n"],
        "dir": np.rad2deg(np.arctan2(g["sx"], g["sy"])) % 360.0,
        "n": g["n"],
    })
    return out.sort_values(["talker", "ts"]).reset_index(drop=True)


def load_mwv(paths=None, bin_s=1, chunksize=1_000_000):
    """Load MWV rows from the SQLite files (in the order given) averaged into bin_s bins.

    Returns a DataFrame with columns ts (UTC), talker, spd (knots), dir (deg), n (samples per bin).
    A corrupt database is reported with a warning and whatever could be read is kept.
    """
    paths = default_paths() if paths is None else [Path(p).expanduser() for p in paths]
    parts = []
    for path in paths:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        rows = 0
        try:
            cur = con.execute(
                "SELECT timestamp, talker, aws_knots, awa FROM MWV ORDER BY timestamp")
            while True:
                batch = cur.fetchmany(chunksize)
                if not batch:
                    break
                raw = pd.DataFrame(batch, columns=["timestamp", "talker", "aws_knots", "awa"])
                rows += len(raw)
                parts.append(bin_sums(clean(raw), bin_s))
        except sqlite3.DatabaseError as exc:
            warnings.warn(f"{path.name}: read stopped after {rows} rows ({exc})")
        finally:
            con.close()
    if not parts:
        return pd.DataFrame(columns=["ts", "talker", "spd", "dir", "n"])
    return _finalize(pd.concat(parts, ignore_index=True), bin_s)


def align(df, tol="1s"):
    """Pair FT and WI records in time.

    Returns columns ts, ft_spd, ft_dir, wi_spd, wi_dir; FT records without a WI record
    within tol are dropped.
    """
    ft = df[df["talker"] == "FT"].sort_values("ts")[["ts", "spd", "dir"]]
    wi = df[df["talker"] == "WI"].sort_values("ts")[["ts", "spd", "dir"]]
    ft = ft.rename(columns={"spd": "ft_spd", "dir": "ft_dir"})
    wi = wi.rename(columns={"spd": "wi_spd", "dir": "wi_dir"})
    wi = wi.assign(wi_ts=wi["ts"])
    merged = pd.merge_asof(ft, wi, on="ts", direction="nearest", tolerance=pd.Timedelta(tol))
    merged = merged.dropna(subset=["wi_ts"]).drop(columns="wi_ts")
    return merged.reset_index(drop=True)


def estimate_clock_offset(df, max_lag=10, block=200_000):
    """Estimate the WI-vs-FT clock offset (seconds) by cross-correlating speed fluctuations.

    Uses the best-covered contiguous block of the 1 s data. A positive result means the WI
    record is delayed relative to FT (WI timestamps must be shifted back by that much).
    """
    ft = df[df["talker"] == "FT"].set_index("ts")["spd"]
    wi = df[df["talker"] == "WI"].set_index("ts")["spd"]
    common = ft.index.intersection(wi.index)
    if len(common) < 1000:
        return {"lag_s": np.nan, "corr": np.nan}
    start = max(0, (len(common) - block) // 2)
    span = common[start:start + block]
    grid = pd.date_range(span[0], span[-1], freq="1s")
    f = ft.reindex(grid).interpolate(limit=5)
    w = wi.reindex(grid).interpolate(limit=5)
    f, w = f.diff(), w.diff()
    best = (np.nan, -np.inf)
    for lag in range(-max_lag, max_lag + 1):
        c = f.corr(w.shift(-lag))
        if np.isfinite(c) and c > best[1]:
            best = (float(lag), float(c))
    return {"lag_s": best[0], "corr": best[1]}


def coverage(df):
    """Per-talker time span and sample count summary."""
    return df.groupby("talker").agg(start=("ts", "min"), end=("ts", "max"),
                                    bins=("ts", "size"), samples=("n", "sum"))
