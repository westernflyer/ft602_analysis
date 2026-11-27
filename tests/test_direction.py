import numpy as np
import pandas as pd
import pytest

from ft602_analysis.direction import (circ_mean, circ_std, direction_stats, offset_by_direction,
                                      plot_direction, to_uv, uv_summary, wrap_diff)


def test_wrap_diff_across_north():
    assert wrap_diff(5, 355) == pytest.approx(10)
    assert wrap_diff(355, 5) == pytest.approx(-10)
    assert wrap_diff(180, 0) == pytest.approx(-180)


def test_circ_mean_across_north():
    assert wrap_diff(circ_mean([350, 10]), 0) == pytest.approx(0, abs=1e-9)
    assert circ_std([10, 10, 10]) == pytest.approx(0, abs=1e-6)


def make_df(offset, n=1000, spd=10.0):
    rng = np.random.default_rng(0)
    wi = rng.uniform(0, 360, n)
    return pd.DataFrame({"wi_dir": wi, "ft_dir": (wi + offset) % 360,
                         "wi_spd": spd, "ft_spd": spd})


def test_constant_offset_10():
    st = direction_stats(make_df(10))
    assert st["mean_offset"] == pytest.approx(10, abs=1e-6)
    assert st["circ_sd"] == pytest.approx(0, abs=1e-3)
    tab = offset_by_direction(make_df(10))
    assert np.allclose(tab["mean_offset"], 10)


def test_threshold_filters_calm():
    df = make_df(10, spd=1.0)
    assert direction_stats(df)["n"] == 0


def test_uv_components_and_summary(tmp_path):
    u, v = to_uv(10, 90)
    assert u == pytest.approx(10) and v == pytest.approx(0, abs=1e-9)
    df = make_df(0)
    df["ft_spd"] = df["wi_spd"] * 1.1
    s = uv_summary(df)
    assert s.loc["u", "slope"] == pytest.approx(1.1, abs=1e-6)
    assert len(plot_direction(df, tmp_path / "d")) == 2
