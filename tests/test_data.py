import sqlite3

import numpy as np
import pandas as pd
import pytest

from ft602_analysis.data import align, clean, load_mwv


def make_db(path, rows):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE MWV (timestamp INTEGER NOT NULL, talker TEXT NOT NULL, "
                "awa REAL, aws_knots REAL, PRIMARY KEY (timestamp, talker))")
    con.executemany("INSERT INTO MWV VALUES (?,?,?,?)", rows)
    con.commit()
    con.close()


def test_clean_drops_bad_rows():
    raw = pd.DataFrame({
        "timestamp": [1, 2, 3, 4, 4],
        "talker": ["FT", "FT", "WI", "XX", "XX"],
        "aws_knots": [5.0, -1.0, np.nan, 5.0, 5.0],
        "awa": [10.0, 10.0, 10.0, 10.0, 400.0],
    })
    assert list(clean(raw)["timestamp"]) == [1]


def test_load_bins_and_circular_mean(tmp_path):
    # FT: two samples in second 0, directions 350 and 10 -> mean 0 (not 180)
    make_db(tmp_path / "a.sdb", [(100, "FT", 350.0, 4.0), (600, "FT", 10.0, 6.0),
                                  (1100, "FT", 90.0, 5.0), (150, "WI", 5.0, 5.0)])
    make_db(tmp_path / "b.sdb", [(900, "FT", 0.0, 5.0)])  # same bin as a.sdb, merged exactly
    df = load_mwv([tmp_path / "a.sdb", tmp_path / "b.sdb"])
    ft0 = df[(df.talker == "FT")].iloc[0]
    assert ft0["n"] == 3
    assert ft0["spd"] == pytest.approx(5.0)
    assert min(ft0["dir"], 360 - ft0["dir"]) == pytest.approx(0.0, abs=1e-6)
    assert len(df) == 3


def test_align_tolerance():
    ts = pd.to_datetime([0, 1, 2, 10], unit="s", utc=True)
    df = pd.concat([
        pd.DataFrame({"ts": ts, "talker": "FT", "spd": 1.0, "dir": 10.0, "n": 1}),
        pd.DataFrame({"ts": ts[:3], "talker": "WI", "spd": 2.0, "dir": 20.0, "n": 1}),
    ])
    out = align(df, tol="1s")
    assert len(out) == 3
    assert (out["wi_spd"] == 2.0).all() and (out["ft_dir"] == 10.0).all()
