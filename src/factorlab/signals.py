"""Monthly returns and factor signals.

Timing convention (the most important thing in any backtest):
  * A signal dated month-end t uses ONLY data up to and including day t.
  * It is used to form a portfolio held from t to the next month-end t+1.
The test suite checks this by corrupting all data after t and confirming that
the signal at t does not change.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

MIN_DAYS_IN_MONTH = 15     # need this many valid daily returns for a monthly return
LOOKBACK_DAYS = 252        # one trading year for volatility and beta
MIN_LOOKBACK_OBS = 200


def month_ends(daily_index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Last trading day of each calendar month present in the data."""
    s = pd.Series(daily_index, index=daily_index)
    return pd.DatetimeIndex(s.groupby([daily_index.year, daily_index.month]).max().values)


def monthly_returns(daily: pd.DataFrame, ends: pd.DatetimeIndex) -> pd.DataFrame:
    """Compound daily returns into returns for the month ending at each date in `ends`."""
    out = {}
    prev = None
    for t in ends:
        window = daily.loc[(daily.index > prev) & (daily.index <= t)] if prev is not None \
            else daily.loc[daily.index <= t]
        valid = window.notna().sum()
        r = (1.0 + window.fillna(0.0)).prod() - 1.0
        out[t] = r.where(valid >= MIN_DAYS_IN_MONTH)
        prev = t
    return pd.DataFrame(out).T


def momentum_12_1(mret: pd.DataFrame) -> pd.DataFrame:
    """Return over months t-11 ... t-1 (skipping the most recent month t).

    Skipping month t avoids mixing momentum with the short-term reversal effect.
    """
    gross = (1.0 + mret).shift(1)                      # months up to t-1
    valid = gross.notna().rolling(11).sum()
    mom = gross.fillna(1.0).rolling(11).apply(np.prod, raw=True) - 1.0
    return mom.where(valid >= 9)


def short_term_reversal(mret: pd.DataFrame) -> pd.DataFrame:
    """Minus last month's return: last month's losers are expected to bounce."""
    return -mret


def low_volatility(daily: pd.DataFrame, ends: pd.DatetimeIndex) -> pd.DataFrame:
    """Minus the standard deviation of daily returns over the past year."""
    vol = daily.rolling(LOOKBACK_DAYS, min_periods=MIN_LOOKBACK_OBS).std()
    return -vol.reindex(ends)


def low_beta(daily: pd.DataFrame, ends: pd.DatetimeIndex) -> pd.DataFrame:
    """Minus each stock's beta against the equal-weighted market, past year."""
    mkt = daily.mean(axis=1)
    cov = daily.rolling(LOOKBACK_DAYS, min_periods=MIN_LOOKBACK_OBS).cov(mkt)
    var = mkt.rolling(LOOKBACK_DAYS, min_periods=MIN_LOOKBACK_OBS).var()
    beta = cov.div(var, axis=0)
    return -beta.reindex(ends)


def zscore(x: pd.DataFrame) -> pd.DataFrame:
    """Cross-sectional z-score each month (row)."""
    return x.sub(x.mean(axis=1), axis=0).div(x.std(axis=1), axis=0)


def combo(*signals: pd.DataFrame) -> pd.DataFrame:
    """Equal-weight average of z-scored signals (needs every component)."""
    zs = [zscore(s) for s in signals]
    total = sum(zs)
    return total / len(zs)


def build_signals(daily: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    ends = month_ends(daily.index)
    mret = monthly_returns(daily, ends)
    mom = momentum_12_1(mret)
    lowvol = low_volatility(daily, ends)
    signals = {
        "Momentum (12-1)": mom,
        "Short-term reversal": short_term_reversal(mret),
        "Low volatility": lowvol,
        "Low beta": low_beta(daily, ends),
        "Momentum + low vol": combo(mom, lowvol),
    }
    return mret, signals
