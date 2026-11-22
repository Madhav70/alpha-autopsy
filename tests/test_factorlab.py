import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from factorlab import backtest, data, signals, stats  # noqa: E402


def fake_daily(n_days=600, n_stocks=12, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2015-01-01", periods=n_days)
    cols = [f"S{i}" for i in range(n_stocks)]
    vols = np.linspace(0.01, 0.03, n_stocks)
    return pd.DataFrame(rng.normal(0.0004, vols, (n_days, n_stocks)), index=idx, columns=cols)


# ---------------------------------------------------------------- look-ahead
def test_signals_never_use_future_data():
    """Corrupt everything after month-end t; the signals dated t must not change."""
    daily = fake_daily()
    mret, sig = signals.build_signals(daily)
    t = mret.index[20]
    corrupted = daily.copy()
    corrupted.loc[corrupted.index > t] = 0.5            # absurd future returns
    mret2, sig2 = signals.build_signals(corrupted)
    for name in sig:
        a, b = sig[name].loc[:t], sig2[name].loc[:t]
        pd.testing.assert_frame_equal(a, b, check_freq=False, obj=name)


def test_portfolio_formed_at_t_earns_next_month_return():
    dates = pd.to_datetime(["2020-01-31", "2020-02-29", "2020-03-31"])
    sig = pd.DataFrame({"A": [2.0, 1.0, 1.0], "B": [1.0, 2.0, 2.0]}, index=dates)
    mret = pd.DataFrame({"A": [0.0, 0.10, 0.0], "B": [0.0, -0.05, 0.20]}, index=dates)
    res = backtest.run_leg(sig, mret, 0.5, "long", 0.0)
    # Jan signal picks A, which earns Feb's +10%; Feb signal picks B, earns Mar's +20%
    assert res.gross.loc["2020-02-29"] == pytest.approx(0.10)
    assert res.gross.loc["2020-03-31"] == pytest.approx(0.20)


# ---------------------------------------------------------------- costs
def test_turnover_and_costs():
    dates = pd.to_datetime(["2020-01-31", "2020-02-29", "2020-03-31"])
    sig = pd.DataFrame({"A": [2.0, 1.0, 1.0], "B": [1.0, 2.0, 2.0]}, index=dates)
    mret = pd.DataFrame(0.0, index=dates, columns=["A", "B"])
    res = backtest.run_leg(sig, mret, 0.5, "long", 100.0)
    # first month: buy A (100% traded); second: sell A, buy B (200% traded)
    assert list(res.turnover.round(6)) == [1.0, 2.0]
    assert res.net.loc["2020-03-31"] == pytest.approx(-0.02)   # 2.0 x 100 bp


def test_long_short_charges_both_legs():
    daily = fake_daily()
    mret, sig = signals.build_signals(daily)
    s = sig["Low volatility"].dropna(how="all")
    free = backtest.long_short(s, mret, 1 / 3, 0.0)
    paid = backtest.long_short(s, mret, 1 / 3, 50.0)
    drag = (free.net - paid.net)
    assert np.allclose(drag, paid.turnover * 50 / 1e4)


# ---------------------------------------------------------------- signals
def test_momentum_skips_most_recent_month():
    idx = pd.date_range("2020-01-31", periods=14, freq="ME")
    m = pd.DataFrame({"A": [0.01] * 14}, index=idx)
    m.iloc[-1] = 0.50                                  # huge final month
    mom = signals.momentum_12_1(m)
    assert mom.iloc[-1, 0] == pytest.approx(1.01 ** 11 - 1)   # final month ignored


def test_low_vol_ranks_calm_stock_highest():
    daily = fake_daily()
    _, sig = signals.build_signals(daily)
    last = sig["Low volatility"].dropna(how="all").iloc[-1]
    assert last.idxmax() == "S0" and last.idxmin() == "S11"


def test_monthly_return_compounds_daily():
    idx = pd.bdate_range("2020-01-01", "2020-01-31")
    d = pd.DataFrame({"A": 0.01}, index=idx)
    m = signals.monthly_returns(d, signals.month_ends(idx))
    assert m.iloc[0, 0] == pytest.approx(1.01 ** len(idx) - 1)


# ---------------------------------------------------------------- statistics
def test_newey_west_matches_statsmodels():
    sm = pytest.importorskip("statsmodels.api")
    rng = np.random.default_rng(1)
    e = rng.normal(size=300)
    x = 0.1 + np.convolve(e, [1, 0.6, 0.3], mode="same")    # autocorrelated
    ours = stats.newey_west_tstat(pd.Series(x), lags=4)
    fit = sm.OLS(x, np.ones_like(x)).fit(cov_type="HAC", cov_kwds={"maxlags": 4})
    assert ours == pytest.approx(fit.tvalues[0], rel=0.02)


def test_holm_adjustment():
    adj = stats.holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert adj["a"] == pytest.approx(0.03)
    assert adj["c"] == pytest.approx(0.06)
    assert adj["b"] == pytest.approx(0.06)       # monotone: never below the previous


def test_max_drawdown():
    r = pd.Series([0.10, -0.50, 0.20])
    assert stats.max_drawdown(r) == pytest.approx(-0.5)


# ---------------------------------------------------------------- data fixes
def test_documented_fixes_are_applied():
    idx = pd.bdate_range("2015-06-01", "2015-06-05")
    px = pd.DataFrame({"ADANIENT": [100, 101, 60, 61, 62.0]}, index=idx)
    r = data.daily_returns(px)
    assert np.isnan(r.loc["2015-06-03", "ADANIENT"])            # demerger day dropped
    assert r.loc["2015-06-04", "ADANIENT"] == pytest.approx(61 / 60 - 1)
