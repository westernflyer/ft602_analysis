"""Command line entry point: run the full FT602 vs Airmar 200WX comparison."""

import argparse
import warnings
from pathlib import Path

import pandas as pd

from .data import align, coverage, default_paths, estimate_clock_offset, load_mwv
from .direction import SPEED_THRESHOLD_KN, direction_stats, offset_by_direction, plot_direction, \
    uv_summary
from .gusts import gust_summary, plot_gusts, window_stats
from .speed import LOW_WIND_KN, plot_speed, speed_summary


def build_parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir", help="directory holding the nmea_database-2026-N.sdb files")
    p.add_argument("--out", default="out", help="output directory (default: out)")
    p.add_argument("--tol", default="1s", help="alignment tolerance (default: 1s)")
    p.add_argument("--speed-threshold", type=float, default=SPEED_THRESHOLD_KN,
                   help="knots; minimum speed for direction comparison")
    p.add_argument("--low-wind", type=float, default=LOW_WIND_KN,
                   help="knots; low-wind split for speed stats")
    p.add_argument("--window", default="10min", help="gust/turbulence window (default: 10min)")
    p.add_argument("--no-cache", action="store_true", help="re-read the databases")
    return p


def _load(args, out):
    cache = out / "binned_1s.pkl"
    if cache.exists() and not args.no_cache:
        return pd.read_pickle(cache)
    paths = default_paths(args.data_dir) if args.data_dir else default_paths()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        df = load_mwv(paths)
    for w in caught:
        print(f"WARNING: {w.message}")
    df.to_pickle(cache)
    return df


def main(argv=None):
    args = build_parser().parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    binned = _load(args, out)
    lines = ["FT602 (talker FT) vs Airmar 200WX (talker WI) comparison",
             "Both instruments are averaged to 1 s bins (direction via unit vectors) before pairing.",
             "Wind is apparent wind; direction is relative to the boat.", "",
             "== Coverage ==", coverage(binned).to_string(), ""]

    clock = estimate_clock_offset(binned)
    lines += ["== Clock offset (cross-correlation of speed changes) ==",
              f"best lag: {clock['lag_s']} s (correlation {clock['corr']:.3f}); "
              "no correction applied", ""]

    df = align(binned, args.tol)
    lines += [f"== Aligned pairs (tolerance {args.tol}) ==", f"{len(df)} pairs", ""]

    speed = speed_summary(df, args.low_wind)
    speed.to_csv(out / "speed_stats.csv")
    lines += [f"== Speed (FT - WI, knots; low wind = mean < {args.low_wind} kn) ==",
              speed.to_string(float_format="%.4f"),
              "slope/intercept/r2: orthogonal regression of FT (y) on WI (x)", ""]

    dstat = direction_stats(df, args.speed_threshold)
    offset_by_direction(df, args.speed_threshold).to_csv(out / "direction_offset_by_bin.csv",
                                                         index=False)
    lines += [f"== Direction (FT - WI, deg; both speeds >= {args.speed_threshold} kn) ==",
              f"n={dstat['n']}  circular mean offset={dstat['mean_offset']:.3f}  "
              f"circular SD={dstat['circ_sd']:.3f}", ""]

    uv = uv_summary(df)
    uv.to_csv(out / "uv_stats.csv")
    lines += ["== u (east) / v (north) components (knots) ==", uv.to_string(float_format="%.4f"), ""]

    win = window_stats(df, args.window)
    win.to_csv(out / "window_stats.csv")
    lines += [f"== Gusts / turbulence ({args.window} windows, gust = max of 1 s values) ==",
              gust_summary(win).to_string(float_format="%.4f"), ""]

    plots = plot_speed(df, str(out / "speed")) + plot_direction(
        df, str(out / "direction"), args.speed_threshold) + plot_gusts(win, str(out / "gusts"))
    lines += ["== Plots =="] + plots
    text = "\n".join(lines)
    (out / "summary.txt").write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
