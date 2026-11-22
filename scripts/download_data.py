"""Download the raw data used by this project into ./data/raw/.

Sources (both public GitHub mirrors of Yahoo Finance data):
  * Daily OHLCV for the 50 NIFTY-50 constituents (as of 2022), Oct 2012 - Oct 2022:
    https://github.com/Ram9219/NIFTY-50-Stock-Market-Data-2000---2022-
  * The NIFTY 50 index level (^NSEI), used only as a reference benchmark:
    https://github.com/kalilurrahman/NIFTY_50_STOCK_DATA

Usage:  python scripts/download_data.py
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

STOCKS_URL = ("https://raw.githubusercontent.com/Ram9219/"
              "NIFTY-50-Stock-Market-Data-2000---2022-/main/{sym}.csv")
INDEX_URL = ("https://raw.githubusercontent.com/kalilurrahman/"
             "NIFTY_50_STOCK_DATA/main/NIFTY50_stock_history.csv")

SYMBOLS = [
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK",
    "BAJAJ-AUTO", "BAJAJFINSV", "BAJFINANCE", "BHARTIARTL", "BPCL",
    "BRITANNIA", "CIPLA", "COALINDIA", "DIVISLAB", "DRREDDY", "EICHERMOT",
    "GRASIM", "HCLTECH", "HDFC", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO",
    "HINDALCO", "HINDUNILVR", "ICICIBANK", "INDUSINDBK", "INFY", "ITC",
    "JSWSTEEL", "KOTAKBANK", "LT", "MARUTI", "M_and_M", "NESTLEIND", "NTPC",
    "ONGC", "POWERGRID", "RELIANCE", "SBILIFE", "SBIN", "SUNPHARMA",
    "TATACONSUM", "TATAMOTORS", "TATASTEEL", "TCS", "TECHM", "TITAN",
    "ULTRACEMCO", "UPL", "WIPRO",
]


def fetch(url: str, dest: Path) -> None:
    with urllib.request.urlopen(url, timeout=60) as r:
        dest.write_bytes(r.read())


def main() -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    failed = []
    for sym in SYMBOLS:
        dest = RAW / f"{sym}.csv"
        if dest.exists():
            continue
        try:
            fetch(STOCKS_URL.format(sym=sym), dest)
        except Exception as exc:  # noqa: BLE001
            failed.append((sym, exc))
    idx = RAW / "NIFTY50_INDEX.csv"
    if not idx.exists():
        fetch(INDEX_URL, idx)
    print(f"{len(SYMBOLS) - len(failed)}/{len(SYMBOLS)} stock files in {RAW}")
    for sym, exc in failed:
        print(f"  failed: {sym}: {exc}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
