"""Gust factor and turbulence intensity over fixed windows."""

import numpy as np
import pandas as pd

from .speed import tls_fit


def window_stats(df, window="10min", min_coverage=0.8, min_mean=2.0):
    """Per-window mean, max (gust), std, gust factor and turbulence intensity for each instrument.

    Works on the 1 s aligned data (columns ts, ft_spd, wi_spd). Windows with fewer than
    min_coverage of the expected samples, or a mean speed below min_mean for either instrument,
    are dropped.
    """
    expected = pd.Timedelta(window).total_seconds()
    g = df.set_index("ts").resample(window)
    out = pd.DataFrame({"count": g["ft_spd"].count()})
    for tag in ("ft", "wi"):
        col = f"{tag}_spd"
        out[f"{tag}_mean"] = g[col].mean()
        out[f"{tag}_max"] = g[col].max()
        out[f"{tag}_std"] = g[col].std()
        out[f"{tag}_gf"] = out[f"{tag}_max"] / out[f"{tag}_mean"]
        out[f"{tag}_ti"] = out[f"{tag}_std"] / out[f"{tag}_mean"]
    ok = (out["count"] >= min_coverage * expected) & \
         (out["ft_mean"] >= min_mean) & (out["wi_mean"] >= min_mean)
    return out[ok].dropna()


def gust_summary(w):
    """Compare FT vs WI gust, gust factor and turbulence intensity across windows."""
    rows = {}
    for name in ("max", "gf", "ti"):
        a, b = w[f"ft_{name}"].to_numpy(), w[f"wi_{name}"].to_numpy()
        row = {"n_windows": len(w), "ft_mean": a.mean(), "wi_mean": b.mean(),
               "ratio_ft_over_wi": a.mean() / b.mean()}
        if len(w) >= 3:
            row["slope"], row["intercept"], row["r2"] = tls_fit(b, a)
        rows[{"max": "gust_max", "gf": "gust_factor", "ti": "turbulence_intensity"}[name]] = row
    return pd.DataFrame(rows).T


def plot_gusts(w, path_prefix):
    """Save a 3-panel FT vs WI comparison of window max, gust factor and turbulence intensity."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 3, figsize=(16, 5.5))
    for ax, (key, label) in zip(axes, [("max", "10-min max speed (kn)"),
                                       ("gf", "Gust factor (max/mean)"),
                                       ("ti", "Turbulence intensity (σ/mean)")]):
        x, y = w[f"wi_{key}"], w[f"ft_{key}"]
        ax.hexbin(x, y, gridsize=50, bins="log", cmap="viridis", mincnt=1)
        lim = [0, max(x.max(), y.max())]
        ax.plot(lim, lim, "k:")
        ax.set(xlabel=f"200WX {label}", ylabel=f"FT602 {label}", title=label)
    path = f"{path_prefix}_gusts.png"
    fig.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return [path]
