"""Wind direction and u/v component comparison."""

import numpy as np
import pandas as pd

from .speed import speed_stats

SPEED_THRESHOLD_KN = 2.0


def wrap_diff(a, b):
    """Signed angular difference a - b wrapped to [-180, 180)."""
    return (np.asarray(a, float) - np.asarray(b, float) + 180.0) % 360.0 - 180.0


def circ_mean(deg):
    """Circular mean in degrees, in [0, 360)."""
    rad = np.deg2rad(np.asarray(deg, float))
    return float(np.rad2deg(np.arctan2(np.sin(rad).mean(), np.cos(rad).mean())) % 360.0)


def circ_std(deg):
    """Circular standard deviation in degrees: sqrt(-2 ln R)."""
    rad = np.deg2rad(np.asarray(deg, float))
    r = np.hypot(np.sin(rad).mean(), np.cos(rad).mean())
    return float(np.rad2deg(np.sqrt(-2.0 * np.log(min(r, 1.0)))))


def to_uv(spd, direction):
    """Convert speed and direction (deg, 0 = north/bow, clockwise) to (u, v) = (east, north) components."""
    rad = np.deg2rad(np.asarray(direction, float))
    spd = np.asarray(spd, float)
    return spd * np.sin(rad), spd * np.cos(rad)


def filter_speed(df, threshold=SPEED_THRESHOLD_KN):
    """Keep samples where both instruments are above the speed threshold."""
    return df[(df["ft_spd"] >= threshold) & (df["wi_spd"] >= threshold)]


def direction_stats(df, threshold=SPEED_THRESHOLD_KN):
    """Circular stats of FT - WI direction differences above the speed threshold."""
    sub = filter_speed(df, threshold)
    if sub.empty:
        return {"n": 0, "mean_offset": np.nan, "circ_sd": np.nan}
    d = wrap_diff(sub["ft_dir"], sub["wi_dir"])
    return {"n": len(sub), "mean_offset": _signed_mean(d), "circ_sd": circ_std(d)}


def _signed_mean(d):
    m = circ_mean(d)
    return m - 360.0 if m >= 180.0 else m


def offset_by_direction(df, threshold=SPEED_THRESHOLD_KN, bin_deg=15):
    """Mean/SD of the direction offset binned by the WI direction (alignment vs flow distortion)."""
    sub = filter_speed(df, threshold)
    d = wrap_diff(sub["ft_dir"], sub["wi_dir"])
    bins = (np.floor(sub["wi_dir"].to_numpy() / bin_deg) * bin_deg + bin_deg / 2) % 360
    rows = []
    for centre in np.unique(bins):
        sel = d[bins == centre]
        rows.append({"dir_bin": centre, "n": len(sel),
                     "mean_offset": _signed_mean(sel), "circ_sd": circ_std(sel)})
    return pd.DataFrame(rows, columns=["dir_bin", "n", "mean_offset", "circ_sd"])


def uv_summary(df):
    """Regression and bias of the u and v components, FT vs WI (no speed threshold)."""
    fu, fv = to_uv(df["ft_spd"], df["ft_dir"])
    wu, wv = to_uv(df["wi_spd"], df["wi_dir"])
    return pd.DataFrame({"u": speed_stats(fu, wu), "v": speed_stats(fv, wv)}).T


def plot_direction(df, path_prefix, threshold=SPEED_THRESHOLD_KN, bin_deg=15):
    """Save offset-vs-direction and u/v scatter PNGs; returns the file paths."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    tab = offset_by_direction(df, threshold, bin_deg)
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.errorbar(tab["dir_bin"], tab["mean_offset"], yerr=tab["circ_sd"], fmt="o-", capsize=3)
    ax.axhline(0, color="k", lw=0.5)
    ax.set(xlabel="200WX direction (deg)", ylabel="FT602 - 200WX direction (deg)",
           title=f"Direction offset vs direction (speed >= {threshold} kn)", xlim=(0, 360))
    off_path = f"{path_prefix}_offset_vs_dir.png"
    fig.savefig(off_path, dpi=120, bbox_inches="tight")
    plt.close(fig)

    fu, fv = to_uv(df["ft_spd"], df["ft_dir"])
    wu, wv = to_uv(df["wi_spd"], df["wi_dir"])
    n = len(df)
    idx = np.random.default_rng(0).choice(n, min(n, 200_000), replace=False)
    fig, axes = plt.subplots(1, 2, figsize=(12, 6))
    for ax, (x, y, name) in zip(axes, [(wu, fu, "u (east)"), (wv, fv, "v (north)")]):
        ax.hexbin(np.asarray(x)[idx], np.asarray(y)[idx], gridsize=80, bins="log",
                  cmap="viridis", mincnt=1)
        lim = max(np.abs(x).max(), np.abs(y).max())
        ax.plot([-lim, lim], [-lim, lim], "k:")
        ax.set(xlabel=f"200WX {name} (kn)", ylabel=f"FT602 {name} (kn)", aspect="equal",
               title=name)
    uv_path = f"{path_prefix}_uv.png"
    fig.savefig(uv_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return [off_path, uv_path]
