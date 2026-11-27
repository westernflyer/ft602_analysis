import numpy as np
import pandas as pd
import pytest

from ft602_analysis.speed import plot_speed, speed_stats, speed_summary, tls_fit


def test_tls_slope_recovers_scale():
    rng = np.random.default_rng(0)
    a = rng.uniform(1, 30, 2000)
    b = 1.05 * a
    slope, intercept, r2 = tls_fit(a, b)
    assert slope == pytest.approx(1.05, abs=1e-3)
    assert intercept == pytest.approx(0, abs=1e-2)
    assert r2 == pytest.approx(1.0)


def test_tls_with_noise_in_both():
    rng = np.random.default_rng(1)
    t = rng.uniform(1, 30, 5000)
    x = t + rng.normal(0, 0.5, t.size)
    y = 1.05 * t + rng.normal(0, 0.5, t.size)
    assert tls_fit(x, y)[0] == pytest.approx(1.05, abs=0.02)


def test_stats_bias_rmse():
    a = np.array([1.0, 2.0, 3.0, 4.0])
    s = speed_stats(a + 0.5, a)
    assert s["bias"] == pytest.approx(0.5)
    assert s["rmse"] == pytest.approx(0.5)
    assert s["sd_diff"] == pytest.approx(0.0, abs=1e-12)


def test_summary_low_split_and_plot(tmp_path):
    rng = np.random.default_rng(2)
    b = rng.uniform(0, 20, 500)
    df = pd.DataFrame({"wi_spd": b, "ft_spd": b + 0.3})
    summ = speed_summary(df)
    assert summ.loc["all", "n"] == 500
    assert summ.loc["low", "n"] + summ.loc["high", "n"] == 500
    assert len(plot_speed(df, tmp_path / "s")) == 2
