"""Wind speed comparison: bias, RMSE, total least squares regression, Bland-Altman."""

import numpy as np
import pandas as pd

LOW_WIND_KN = 2.0


def tls_fit(x, y):
    """Orthogonal (total least squares) fit y = slope*x + intercept; returns slope, intercept, r2."""
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    mx, my = x.mean(), y.mean()
    sxx = ((x - mx) ** 2).mean()
    syy = ((y - my) ** 2).mean()
    sxy = ((x - mx) * (y - my)).mean()
    # Closed-form orthogonal regression (equal error variances in x and y)
    slope = (syy - sxx + np.sqrt((syy - sxx) ** 2 + 4 * sxy ** 2)) / (2 * sxy)
    intercept = my - slope * mx
    r2 = sxy ** 2 / (sxx * syy)
    return float(slope), float(intercept), float(r2)


def speed_stats(a, b):
    """Statistics of A vs B (A - B differences)."""
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    d = a - b
    out = {"n": len(a), "bias": np.nan, "sd_diff": np.nan, "rmse": np.nan,
           "slope": np.nan, "intercept": np.nan, "r2": np.nan}
    if len(a) < 3:
        return out
    out.update(bias=float(d.mean()), sd_diff=float(d.std(ddof=1)),
               rmse=float(np.sqrt((d ** 2).mean())))
    out["slope"], out["intercept"], out["r2"] = tls_fit(b, a)
    return out


def speed_summary(df, low=LOW_WIND_KN, a="ft_spd", b="wi_spd"):
    """Stats for all/low-wind/high-wind subsets, split on the mean of the two speeds."""
    mean = (df[a] + df[b]) / 2
    subsets = {"all": slice(None), "low": mean < low, "high": mean >= low}
    rows = {}
    for name, mask in subsets.items():
        sub = df if name == "all" else df[mask]
        rows[name] = speed_stats(sub[a], sub[b])
    return pd.DataFrame(rows).T


def bland_altman(df, a="ft_spd", b="wi_spd"):
    """Return (mean, diff) arrays for a Bland-Altman plot."""
    return ((df[a] + df[b]) / 2).to_numpy(), (df[a] - df[b]).to_numpy()


def plot_speed(df, path_prefix, a="ft_spd", b="wi_spd", max_points=200_000):
    """Save Bland-Altman and scatter/regression PNGs; returns the file paths."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    if len(df) > max_points:
        df = df.sample(max_points, random_state=0)
    mean, diff = bland_altman(df, a, b)
    bias, sd = diff.mean(), diff.std(ddof=1)

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.hexbin(mean, diff, gridsize=80, bins="log", cmap="viridis", mincnt=1)
    ax.axhline(bias, color="r", label=f"bias {bias:.2f} kn")
    for k in (-1.96, 1.96):
        ax.axhline(bias + k * sd, color="r", ls="--")
    ax.set(xlabel="Mean of FT602 and 200WX apparent wind speed (kn)",
           ylabel="FT602 - 200WX apparent wind speed (kn)",
           title="Bland-Altman: apparent wind speed")
    ax.legend()
    ba_path = f"{path_prefix}_bland_altman.png"
    fig.savefig(ba_path, dpi=120, bbox_inches="tight")
    plt.close(fig)

    slope, intercept, r2 = tls_fit(df[b], df[a])
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.hexbin(df[b], df[a], gridsize=80, bins="log", cmap="viridis", mincnt=1)
    lim = np.array([0, max(df[a].max(), df[b].max())])
    ax.plot(lim, lim, "k:", label="1:1")
    ax.plot(lim, slope * lim + intercept, "r",
            label=f"TLS: y={slope:.3f}x+{intercept:.2f}, R²={r2:.3f}")
    ax.set(xlabel="200WX apparent wind speed (kn)", ylabel="FT602 apparent wind speed (kn)",
           title="Apparent wind speed regression", aspect="equal")
    ax.legend()
    sc_path = f"{path_prefix}_scatter.png"
    fig.savefig(sc_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return [ba_path, sc_path]
