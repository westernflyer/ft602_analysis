import numpy as np
import pandas as pd
import pytest

from ft602_analysis.gusts import gust_summary, plot_gusts, window_stats


def make_df(hours=3, scale=1.0):
    rng = np.random.default_rng(0)
    n = hours * 3600
    ts = pd.date_range("2026-01-01", periods=n, freq="1s", tz="UTC")
    base = 10 + rng.normal(0, 1, n)
    return pd.DataFrame({"ts": ts, "wi_spd": base, "ft_spd": base * scale})


def test_window_stats_scale():
    w = window_stats(make_df(scale=1.1))
    assert len(w) == 18
    assert (w["ft_max"] / w["wi_max"]).mean() == pytest.approx(1.1)
    assert w["ft_gf"].mean() == pytest.approx(w["wi_gf"].mean())
    assert w["wi_ti"].mean() == pytest.approx(0.1, abs=0.01)


def test_low_coverage_dropped():
    df = make_df(hours=1).iloc[::5]  # 20% coverage
    assert window_stats(df).empty


def test_summary_and_plot(tmp_path):
    w = window_stats(make_df(scale=1.1))
    s = gust_summary(w)
    assert s.loc["gust_max", "ratio_ft_over_wi"] == pytest.approx(1.1)
    assert len(plot_gusts(w, tmp_path / "g")) == 1
