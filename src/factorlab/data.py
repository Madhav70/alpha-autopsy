"""Load and clean the raw price data.

Every manual correction is listed in DATA_FIXES with the reason, so that a
reader can audit exactly what was changed. Nothing else is altered.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# (symbol, start, end, action, reason)
#   action "drop_return": the daily return on these dates is not an investor
#                         return (corporate action or bad adjustment) -> set to NaN
#   action "stale":       prices are frozen with zero volume -> treat as missing
DATA_FIXES = [
    ("ADANIENT", "2015-06-03", "2015-06-03", "drop_return",
     "Ex-date of the demerger of the port, power and transmission businesses; "
     "shareholders received shares in other companies, so the -39% move is not a loss."),
    ("TATASTEEL", "2022-06-16", "2022-06-16", "drop_return",
     "Break in the source's adjusted-price series (adjusted close jumps from 45 to 90 "
     "while the traded close falls 6%)."),
    ("HDFC", "2013-12-12", "2015-12-24", "stale",
     "Price frozen at 818.20 with zero volume for two years in the source data."),
]


def _read_one(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    # Two files in the source use DD-MM-YYYY, the rest ISO dates.
    if df["Date"].str.match(r"^\d{2}-\d{2}-\d{4}$").all():
        df["Date"] = pd.to_datetime(df["Date"], format="%d-%m-%Y")
    else:
        df["Date"] = pd.to_datetime(df["Date"], format="%Y-%m-%d")
    return df.set_index("Date").sort_index()


def load_prices(raw_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (adjusted close, volume) panels: rows = dates, columns = symbols."""
    closes, vols = {}, {}
    for f in sorted(raw_dir.glob("*.csv")):
        if f.name.startswith("NIFTY50_INDEX"):
            continue
        df = _read_one(f)
        closes[f.stem] = pd.to_numeric(df["Adj Close"], errors="coerce")
        vols[f.stem] = pd.to_numeric(df["Volume"], errors="coerce")
    return pd.DataFrame(closes), pd.DataFrame(vols)


def daily_returns(adj_close: pd.DataFrame) -> pd.DataFrame:
    """Simple daily returns with the documented fixes applied."""
    px = adj_close.copy()
    for sym, start, end, action, _ in DATA_FIXES:
        if sym in px and action == "stale":
            px.loc[start:end, sym] = np.nan
    rets = px.pct_change(fill_method=None)
    for sym, start, end, action, _ in DATA_FIXES:
        if sym not in rets:
            continue
        if action == "drop_return":
            rets.loc[start:end, sym] = np.nan
        elif action == "stale":
            # also drop the first return after the stale window (it spans two years)
            after = rets.index[rets.index > pd.Timestamp(end)]
            if len(after):
                rets.loc[after[0], sym] = np.nan
    return rets


def load_index(raw_dir: Path) -> pd.Series:
    df = pd.read_csv(raw_dir / "NIFTY50_INDEX.csv", parse_dates=["Date"])
    return df.set_index("Date")["Close"].sort_index()
