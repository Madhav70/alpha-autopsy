"""Performance statistics, with honest standard errors."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


def newey_west_tstat(x: pd.Series, lags: int | None = None) -> float:
    """t-statistic of the mean of x with Newey-West (HAC) standard errors.

    Monthly strategy returns are autocorrelated (overlapping signals, slow-moving
    portfolios); ordinary t-stats would overstate significance.
    Default lag length: floor(4 (T/100)^(2/9)), the Newey-West (1994) rule.
    """
    x = pd.Series(x).dropna().to_numpy()
    T = len(x)
    if lags is None:
        lags = int(math.floor(4 * (T / 100) ** (2 / 9)))
    u = x - x.mean()
    s = u @ u / T
    for L in range(1, lags + 1):
        w = 1 - L / (lags + 1)                      # Bartlett kernel
        s += 2 * w * (u[L:] @ u[:-L]) / T
    se = math.sqrt(s / T)
    return x.mean() / se


def max_drawdown(r: pd.Series) -> float:
    wealth = (1 + r.fillna(0)).cumprod()
    return float((wealth / wealth.cummax() - 1).min())


def summarize(r: pd.Series) -> dict:
    r = r.dropna()
    mu, sd = r.mean(), r.std(ddof=1)
    return {
        "months": len(r),
        "ann_return_pct": 100 * ((1 + r).prod() ** (12 / len(r)) - 1),
        "ann_vol_pct": 100 * sd * math.sqrt(12),
        "sharpe": mu / sd * math.sqrt(12) if sd > 0 else float("nan"),
        "t_stat_nw": newey_west_tstat(r),
        "max_drawdown_pct": 100 * max_drawdown(r),
        "hit_rate_pct": 100 * (r > 0).mean(),
    }


def capm(r: pd.Series, mkt: pd.Series) -> dict:
    """Regress r on the market; alpha annualised in %, with NW t-stat."""
    df = pd.concat([r, mkt], axis=1).dropna()
    y, x = df.iloc[:, 0].to_numpy(), df.iloc[:, 1].to_numpy()
    beta = np.cov(y, x, ddof=1)[0, 1] / np.var(x, ddof=1)
    alpha_series = pd.Series(y - beta * x)
    return {"beta": beta, "alpha_ann_pct": 1200 * alpha_series.mean(),
            "alpha_t_nw": newey_west_tstat(alpha_series)}


def holm(pvalues: dict[str, float]) -> dict[str, float]:
    """Holm-Bonferroni adjusted p-values (controls the chance of ANY false discovery)."""
    items = sorted(pvalues.items(), key=lambda kv: kv[1])
    m, out, running = len(items), {}, 0.0
    for i, (k, p) in enumerate(items):
        running = max(running, min(1.0, (m - i) * p))
        out[k] = running
    return out


def two_sided_p(t: float) -> float:
    """Normal approximation to the two-sided p-value of a t-statistic."""
    return math.erfc(abs(t) / math.sqrt(2))
