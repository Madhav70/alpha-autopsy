"""Monthly-rebalanced portfolio backtests with transaction costs."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class BacktestResult:
    gross: pd.Series          # monthly return before costs
    net: pd.Series            # after costs
    turnover: pd.Series       # sum of |trades| as a fraction of capital, per month
    weights: pd.DataFrame     # target weights chosen at each month-end


def target_weights(signal: pd.Series, fraction: float, side: str) -> pd.Series:
    """Equal weights on the top (side='long') or bottom (side='short') fraction."""
    s = signal.dropna()
    n = int(np.floor(len(s) * fraction))
    if n == 0:
        return pd.Series(dtype=float)
    picks = s.nlargest(n).index if side == "long" else s.nsmallest(n).index
    return pd.Series(1.0 / n, index=picks)


def run_leg(signal: pd.DataFrame, mret: pd.DataFrame, fraction: float, side: str,
            cost_bps: float) -> BacktestResult:
    """Hold an equal-weighted leg, rebalanced monthly.

    signal.loc[t] picks stocks at month-end t; they earn mret.loc[t+1].
    A stock whose next-month return is missing (e.g. its data stops) earns 0,
    i.e. it is treated as cash. We never peek at next month to decide whom to hold.
    """
    dates = signal.index
    gross, net, turn, wts = {}, {}, {}, {}
    prev_drifted = pd.Series(dtype=float)
    for t, t1 in zip(dates[:-1], dates[1:]):
        w = target_weights(signal.loc[t], fraction, side)
        if w.empty:
            continue
        trades = w.sub(prev_drifted, fill_value=0.0).abs().sum()
        r_next = mret.loc[t1].reindex(w.index).fillna(0.0)
        g = float((w * r_next).sum())
        cost = trades * cost_bps / 1e4
        gross[t1], net[t1], turn[t1], wts[t] = g, g - cost, trades, w
        grown = w * (1.0 + r_next)
        prev_drifted = grown / grown.sum()
    return BacktestResult(pd.Series(gross), pd.Series(net), pd.Series(turn),
                          pd.DataFrame(wts).T.fillna(0.0))


def long_short(signal: pd.DataFrame, mret: pd.DataFrame, fraction: float,
               cost_bps: float) -> BacktestResult:
    """Long the top fraction, short the bottom fraction, equal dollars each side."""
    lo = run_leg(signal, mret, fraction, "long", cost_bps)
    sh = run_leg(signal, mret, fraction, "short", cost_bps)
    return BacktestResult(
        gross=lo.gross - sh.gross,
        net=lo.net - sh.gross - (sh.gross - sh.net),   # pay costs on both legs
        turnover=lo.turnover + sh.turnover,
        weights=lo.weights.sub(sh.weights, fill_value=0.0),
    )


def equal_weight_market(mret: pd.DataFrame, eligible: pd.DataFrame,
                        cost_bps: float) -> BacktestResult:
    """Benchmark: every eligible stock, equal weight, rebalanced monthly."""
    sig = eligible.astype(float).where(eligible)       # 1 where eligible, NaN otherwise
    return run_leg(sig, mret, 1.0, "long", cost_bps)
