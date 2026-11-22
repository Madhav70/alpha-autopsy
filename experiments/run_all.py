"""Reproduce every number and figure in the README.

    python scripts/download_data.py      # once
    python experiments/run_all.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import NullFormatter  # noqa: E402

from factorlab import backtest, data, signals, stats  # noqa: E402
from factorlab.plotting import SERIES, TEXT_2, label_end, style, subtitle  # noqa: E402

RAW = ROOT / "data" / "raw"
FIG = ROOT / "figures"
RES = ROOT / "results"

START = "2013-10-31"      # first month-end with 12 months of history for every signal
END = "2022-09-30"        # last complete month in the data
SPLIT = "2018-03-31"      # halves for the out-of-sample check
FRACTION = 1 / 3          # long top third, short bottom third
COST_BPS = 25             # one-way cost per unit traded (brokerage + taxes + impact)
COST_GRID = [0, 10, 25, 50, 75, 100]


def r2(x):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), 2)


def main():
    FIG.mkdir(exist_ok=True)
    RES.mkdir(exist_ok=True)
    style()

    px, _ = data.load_prices(RAW)
    daily = data.daily_returns(px).loc[:END]
    mret, sigs = signals.build_signals(daily)
    sigs = {k: v.loc[START:END] for k, v in sigs.items()}
    idx = data.load_index(RAW)
    ends = mret.index
    nifty = idx.reindex(idx.index.union(ends)).ffill().reindex(ends).pct_change()

    eligible = sigs["Low volatility"].notna() & sigs["Momentum (12-1)"].notna()
    ew = backtest.equal_weight_market(mret, eligible, COST_BPS)
    mkt = ew.gross
    nifty = nifty.reindex(mkt.index)

    out = {"period": [str(mkt.index[0].date()), str(mkt.index[-1].date())],
           "months": len(mkt), "stocks": int(eligible.sum(axis=1).median()),
           "cost_bps": COST_BPS, "data_fixes": [list(f) for f in data.DATA_FIXES]}

    # ---- 1. survivorship bias -------------------------------------------
    s_ew, s_ix = stats.summarize(ew.gross), stats.summarize(nifty)
    out["survivorship"] = {
        "ew_2022_constituents_ann_pct": r2(s_ew["ann_return_pct"]),
        "nifty50_price_index_ann_pct": r2(s_ix["ann_return_pct"]),
        "gap_pct_per_year": r2(s_ew["ann_return_pct"] - s_ix["ann_return_pct"]),
    }
    fig, ax = plt.subplots(figsize=(7.4, 4.3))
    g1 = (1 + ew.gross).cumprod()
    g2 = (1 + nifty).cumprod()
    ax.plot(g1.index, g1.values, color=SERIES[0], label="Today's 50 NIFTY stocks, equal-weighted")
    ax.plot(g2.index, g2.values, color=SERIES[1], label="NIFTY 50 index (what investors actually held)")
    label_end(ax, g1.index[-1], g1.iloc[-1], f"₹{g1.iloc[-1]:.1f}")
    label_end(ax, g2.index[-1], g2.iloc[-1], f"₹{g2.iloc[-1]:.1f}")
    ax.set_ylabel("Growth of ₹1")
    ax.set_title("Backtesting on today's index members inflates returns", pad=22)
    subtitle(ax, f"{s_ew['ann_return_pct']:.1f}% vs {s_ix['ann_return_pct']:.1f}% a year, "
                 f"{mkt.index[0]:%b %Y} – {mkt.index[-1]:%b %Y} · gap = survivorship + equal weighting"
                 " + index dividends (~1–1.5%)")
    ax.legend(loc="upper left")
    fig.savefig(FIG / "fig1_survivorship.svg")
    plt.close(fig)

    # ---- 2. factor long-short backtests ------------------------------------
    rows, ls_net, pvals, alpha_p = {}, {}, {}, {}
    for name, sg in sigs.items():
        ls = backtest.long_short(sg, mret, FRACTION, COST_BPS)
        lo = backtest.run_leg(sg, mret, FRACTION, "long", COST_BPS)
        g, n = stats.summarize(ls.gross), stats.summarize(ls.net)
        active = (lo.net - ew.net).dropna()
        a = stats.summarize(active)
        h1 = stats.summarize(ls.net.loc[:SPLIT])
        h2 = stats.summarize(ls.net.loc[SPLIT:].iloc[1:])
        cap = stats.capm(ls.net, mkt)
        cap1 = stats.capm(ls.net.loc[:SPLIT], mkt.loc[:SPLIT])
        cap2 = stats.capm(ls.net.loc[SPLIT:].iloc[1:], mkt.loc[SPLIT:].iloc[1:])
        pvals[name] = stats.two_sided_p(n["t_stat_nw"])
        alpha_p[name] = stats.two_sided_p(cap["alpha_t_nw"])
        ls_net[name] = ls.net
        rows[name] = {
            "ls_gross_ann_pct": r2(g["ann_return_pct"]),
            "ls_net_ann_pct": r2(n["ann_return_pct"]),
            "ls_net_sharpe": r2(n["sharpe"]),
            "ls_net_t_nw": r2(n["t_stat_nw"]),
            "ls_max_dd_pct": r2(n["max_drawdown_pct"]),
            "ls_market_beta": r2(cap["beta"]),
            "ls_capm_alpha_ann_pct": r2(cap["alpha_ann_pct"]),
            "ls_capm_alpha_t_nw": r2(cap["alpha_t_nw"]),
            # one-way turnover per leg: share of each leg replaced per month
            "monthly_turnover_pct": r2(100 * ls.turnover.mean() / 4),
            "first_half_net_ann_pct": r2(h1["ann_return_pct"]),
            "second_half_net_ann_pct": r2(h2["ann_return_pct"]),
            "first_half_alpha_ann_pct": r2(cap1["alpha_ann_pct"]),
            "first_half_alpha_t_nw": r2(cap1["alpha_t_nw"]),
            "second_half_alpha_ann_pct": r2(cap2["alpha_ann_pct"]),
            "second_half_alpha_t_nw": r2(cap2["alpha_t_nw"]),
            "long_only_active_ann_pct": r2(a["ann_return_pct"]),
            "long_only_info_ratio": r2(a["sharpe"]),
            "long_only_active_t_nw": r2(a["t_stat_nw"]),
        }
    holm = stats.holm(pvals)
    holm_a = stats.holm(alpha_p)
    for k in rows:
        rows[k]["alpha_p_value"] = round(alpha_p[k], 3)
        rows[k]["alpha_p_value_holm"] = round(holm_a[k], 3)
        rows[k]["p_value"] = round(pvals[k], 3)
        rows[k]["p_value_holm"] = round(holm[k], 3)
    out["factors"] = rows

    names = list(sigs)
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    for i, k in enumerate(names):
        w = (1 + ls_net[k]).cumprod()
        ax.plot(w.index, w.values, color=SERIES[i], label=k, linewidth=1.8)
    ax.axhline(1, color=TEXT_2, linewidth=1)
    ax.set_yscale("log")
    ax.yaxis.set_minor_formatter(NullFormatter())
    ax.set_yticks([0.25, 0.5, 1, 1.5, 2])
    ax.set_yticklabels(["0.25", "0.5", "1", "1.5", "2"])
    ax.set_ylabel("Growth of ₹1, long-short, after costs (log)")
    ax.set_title("No factor earned a statistically reliable premium after costs", pad=22)
    subtitle(ax, f"Long top third, short bottom third, monthly rebalance, {COST_BPS} bp per trade")
    ax.legend(loc="lower left", ncol=2, fontsize=9)
    fig.savefig(FIG / "fig2_factor_returns.svg")
    plt.close(fig)

    # ---- 3. gross vs net: what trading costs eat --------------------------
    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    y = np.arange(len(names))
    gross = [rows[k]["ls_gross_ann_pct"] for k in names]
    net = [rows[k]["ls_net_ann_pct"] for k in names]
    ax.barh(y - 0.19, gross, height=0.36, color=SERIES[0], label="Before costs")
    ax.barh(y + 0.19, net, height=0.36, color=SERIES[1], label=f"After {COST_BPS} bp costs")
    for i, k in enumerate(names):
        xpos = max(gross[i], net[i], 0) + 0.6
        ax.text(xpos, i, f"replaces {rows[k]['monthly_turnover_pct']:.0f}% a month",
                va="center", fontsize=8.5, color=TEXT_2)
    ax.axvline(0, color=TEXT_2, linewidth=1)
    ax.set_yticks(y)
    ax.set_yticklabels(names)
    ax.invert_yaxis()
    ax.set_xlabel("Long-short return (% a year)")
    ax.set_title("Reversal earns 8% a year on paper and nothing after costs", pad=22)
    subtitle(ax, "Costs grow with how much of the portfolio is replaced each month")
    ax.legend(loc="lower left")
    ax.set_xlim(min(min(gross), min(net)) - 2, max(max(gross), max(net)) + 12)
    fig.savefig(FIG / "fig3_costs.svg")
    plt.close(fig)

    # ---- 4. cost sensitivity ---------------------------------------------
    grid = {}
    fig, ax = plt.subplots(figsize=(7.4, 4.3))
    for i, k in enumerate(names):
        srs = [stats.summarize(backtest.long_short(sigs[k], mret, FRACTION, c).net)["sharpe"]
               for c in COST_GRID]
        grid[k] = [r2(v) for v in srs]
        ax.plot(COST_GRID, srs, color=SERIES[i], marker="o", markeredgecolor="white", label=k)
    ax.axhline(0, color=TEXT_2, linewidth=1)
    ax.set_xlabel("One-way trading cost (bp)")
    ax.set_ylabel("Long-short Sharpe ratio")
    ax.set_title("Reversal\u2019s edge is gone once trading costs reach about 25 bp", pad=22)
    subtitle(ax, "Sharpe ratio of each long-short factor as trading costs rise")
    ax.legend(loc="lower left", ncol=2, fontsize=9)
    fig.savefig(FIG / "fig4_cost_sensitivity.svg")
    plt.close(fig)
    out["sharpe_vs_cost"] = {"cost_bps": COST_GRID, **grid}

    # ---- 5. autopsy of the low-volatility result ---------------------------
    sg = sigs["Low volatility"]
    short_leg = backtest.run_leg(sg, mret, FRACTION, "short", 0)
    contrib = {}
    for t, t1 in zip(sg.index[:-1], sg.index[1:]):
        w = short_leg.weights.loc[t]
        for s in w[w > 0].index:
            r = mret.loc[t1, s]
            contrib[s] = contrib.get(s, 0.0) + w[s] * np.log1p(0.0 if pd.isna(r) else r)
    top = pd.Series(contrib).sort_values(ascending=False).head(5)
    excl = top.index.tolist()
    ex_rows = {}
    for k in names:
        full = backtest.long_short(sigs[k], mret, FRACTION, COST_BPS)
        drop = backtest.long_short(sigs[k].drop(columns=excl), mret.drop(columns=excl),
                                   FRACTION, COST_BPS)
        f, d = stats.summarize(full.net), stats.summarize(drop.net)
        mkt_drop = backtest.equal_weight_market(mret.drop(columns=excl),
                                                eligible.drop(columns=excl), COST_BPS).gross
        ca, cd = stats.capm(full.net, mkt), stats.capm(drop.net, mkt_drop)
        ex_rows[k] = {"all_50": r2(f["ann_return_pct"]), "all_50_t": r2(f["t_stat_nw"]),
                      "without_5": r2(d["ann_return_pct"]), "without_5_t": r2(d["t_stat_nw"]),
                      "alpha_all_50": r2(ca["alpha_ann_pct"]), "alpha_all_50_t": r2(ca["alpha_t_nw"]),
                      "alpha_without_5": r2(cd["alpha_ann_pct"]),
                      "alpha_without_5_t": r2(cd["alpha_t_nw"])}
    out["autopsy"] = {"top5_high_vol_winners": excl,
                      "their_log_return_contribution": [r2(v) for v in top.values],
                      "results": ex_rows}

    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    a = [ex_rows[k]["all_50"] for k in names]
    b = [ex_rows[k]["without_5"] for k in names]
    ax.barh(y - 0.19, a, height=0.36, color=SERIES[0], label="All 50 stocks")
    ax.barh(y + 0.19, b, height=0.36, color=SERIES[1], label="Without the 5 biggest winners")
    for i, k in enumerate(names):
        for val, t, off in ((a[i], ex_rows[k]["all_50_t"], -0.19), (b[i], ex_rows[k]["without_5_t"], 0.19)):
            ax.text(min(val, 0) - 0.4, i + off, f"t={t:+.1f}", va="center", ha="right",
                    fontsize=8, color=TEXT_2)
    ax.axvline(0, color=TEXT_2, linewidth=1)
    ax.set_yticks(y)
    ax.set_yticklabels(names)
    ax.invert_yaxis()
    ax.set_xlabel("Long-short return after costs (% a year)")
    ax.set_title("Five stocks drive the low-volatility result", pad=22)
    subtitle(ax, "Dropping " + ", ".join(excl) + " (t = Newey-West t-stat)")
    ax.legend(loc="upper left")
    ax.set_xlim(min(a + b) - 6, max(a + b + [0]) + 3)
    fig.savefig(FIG / "fig5_autopsy.svg")
    plt.close(fig)

    # ---- 6. raw return vs market-adjusted alpha ----------------------------
    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    raw = [rows[k]["ls_net_ann_pct"] for k in names]
    alp = [rows[k]["ls_capm_alpha_ann_pct"] for k in names]
    ax.barh(y - 0.19, raw, height=0.36, color=SERIES[0], label="Raw return after costs")
    ax.barh(y + 0.19, alp, height=0.36, color=SERIES[1], label="Alpha after removing market exposure")
    for i, k in enumerate(names):
        ax.text(max(raw[i], alp[i], 0) + 0.5, i,
                f"beta {rows[k]['ls_market_beta']:+.2f} · alpha t={rows[k]['ls_capm_alpha_t_nw']:+.1f}",
                va="center", fontsize=8.5, color=TEXT_2)
    ax.axvline(0, color=TEXT_2, linewidth=1)
    ax.set_yticks(y)
    ax.set_yticklabels(names)
    ax.invert_yaxis()
    ax.set_xlabel("Long-short (% a year)")
    ax.set_title("After removing market exposure, only momentum shows real alpha", pad=22)
    subtitle(ax, "CAPM regression on the equal-weighted market; t = Newey-West t-stat")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.16), ncol=2)
    ax.set_xlim(min(raw + alp) - 2, max(raw + alp) + 13)
    fig.savefig(FIG / "fig6_market_adjusted.svg")
    plt.close(fig)

    (RES / "summary.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
