# Interview guide: Alpha Autopsy

Quant interviewers love backtests because they are full of traps. This project is
built around those traps, so the questions you get will probably be about them.
Read this guide, run the code, and do the exercises before listing the project.

## Part 1: the 60-second story

> "I backtested five classic stock-selection signals on the NIFTY 50: momentum,
> short-term reversal, low volatility, low beta and a blend. The interesting part
> wasn't the strategies, it was the biases. My data only had today's 50 index
> members, and equal-weighting them earned 22% a year against 12% for the actual
> index. That's survivorship bias, and it flipped the low-volatility result: low
> vol lost 15% a year, mainly because the long-short portfolio was short the
> market, and because five volatile stocks like Adani Enterprises and Bajaj
> Finance became huge winners. Reversal looked great before costs and lost money
> after. Momentum was the only signal with market-adjusted alpha that survived a
> multiple-testing correction, 12.6% a year with a t-stat of 2.6, but I'd want
> point-in-time index data before believing it."

## Part 2: glossary

| Term | Plain English |
|---|---|
| **Factor / signal** | A rule for ranking stocks, e.g. "past 12-month return". |
| **Long-short** | Buy the top-ranked third and short-sell the bottom third with equal money. This isolates the signal from the market's general direction (in theory). |
| **Look-ahead bias** | Accidentally using information you wouldn't have had at the time, e.g. using today's closing price to decide today's trade at the open. |
| **Survivorship bias** | Testing only on companies that still exist or are still in the index today. They are the winners, so everything looks better. |
| **Turnover** | The share of the portfolio replaced each month. More turnover means more trading costs. |
| **Basis point (bp)** | 0.01%. 25 bp = 0.25% per trade. |
| **Sharpe ratio** | Average return ÷ volatility, annualised. Above 1 is very good for a real strategy. |
| **t-statistic** | How many standard errors the average is from zero. About 2 is the usual bar; for a strategy picked from many tries, 3 is safer (Harvey, Liu & Zhu, 2016). |
| **Newey-West** | A way of computing standard errors that allows returns to be correlated over time. Without it, t-stats are too optimistic. |
| **Beta** | How much a portfolio moves with the market. Beta −0.6 means it falls 0.6% when the market rises 1%. |
| **Alpha (CAPM)** | Return left over after removing what the portfolio's beta explains. It is the real "skill" part. |
| **Multiple testing / Holm** | Test five signals and one may look significant by luck. Holm's correction raises the bar to account for that. |
| **Drawdown** | The fall from a previous peak to a later low. |

## Part 3: read the code in this order

1. **`src/factorlab/data.py`.** How the raw files are loaded, and the
   `DATA_FIXES` list. Be ready to explain each of the three fixes and how you
   found them: they showed up as extreme daily returns, which you then checked
   against news reports.
2. **`src/factorlab/signals.py`.** The timing convention at the top is the most
   important paragraph in the project. Make sure you can explain why momentum
   *skips* the most recent month.
3. **`src/factorlab/backtest.py`.** `run_leg` is the core loop. It picks stocks at
   *t* and earns the return of *t+1*. Turnover compares the new target weights with
   the old weights *after they drifted* with prices.
4. **`src/factorlab/stats.py`.** These are short functions. Make sure you can
   write a Newey-West t-stat on a whiteboard.
5. **`tests/test_factorlab.py`.** Start with `test_signals_never_use_future_data`:
   it is the single most impressive thing in the repo, so mention it.

## Part 4: exercises (do at least three)

1. Change `FRACTION` from 1/3 to 1/5 (quintiles) in `experiments/run_all.py`.
   What happens to the t-stats, and why are they noisier?
2. Change `COST_BPS` to 10. Does reversal come back?
3. Remove the "skip a month" from momentum: use months *t−11 … t* instead.
   What happens? (Hint: you mix in reversal.)
4. Make the low-vol portfolio beta-neutral: scale the short leg so the two legs
   have equal beta. Does the loss disappear?
5. Delete one entry from `DATA_FIXES` and rerun. How much does a single bad data
   point move the results?

## Part 5: questions you will probably get

**Q: How do you know you have no look-ahead bias?**
Signals at *t* use data up to *t* only, and portfolios earn the return of *t+1*.
A unit test checks this directly: it replaces every return after *t* with
nonsense and confirms the signals at *t* are unchanged.

**Q: Your equal-weighted universe made 22% a year. Is that real?**
No. The dataset contains only today's index members, so every stock in it is, by
construction, a company that did well enough to be in the index in 2022. Compared
with the real NIFTY 50 index, which held the stocks that later dropped out, the
gap is about 10 points a year. Some of that is equal weighting and the index's
missing dividends, but most is survivorship.

**Q: Low volatility is a famous anomaly. Why does it lose money here?**
Three reasons:
- The long-short portfolio has a beta of −0.61, so it is short a market that rose
  22% a year. After adjusting for beta, the alpha is about zero.
- Survivorship: the volatile stocks that made it into the 2022 index are the ones
  whose volatility turned into big gains.
- Five stocks explain about half the loss.

**Q: Why use Newey-West instead of a normal t-test?**
Monthly strategy returns are autocorrelated because portfolios change slowly, and
that makes ordinary standard errors too small. The code checks that my Newey-West
implementation matches statsmodels.

**Q: You tested five factors. Isn't one bound to look good?**
Yes. That's why I applied a Holm correction. Momentum's alpha p-value rises from
0.010 to 0.048, which is just under 5%. I'd call it a lead, not a discovery.

**Q: Why did reversal fail?**
It replaces about 70% of its holdings every month. At 25 bp per trade on both
legs, that costs more than the 8% a year it earns before costs.

**Q: Could you trade this?**
Probably not the long-short version: holding short positions in Indian stocks
overnight requires borrowing them, and the stock-lending market is thin. The long-only versions are in `results/summary.json`. Long-only
momentum beat the equal-weighted market by about 3% a year, which is not
statistically significant.

**Q: What would you do with more time or data?**
- Get point-in-time NIFTY 50 (or NIFTY 500) membership, so delisted stocks and
  stocks that left the index are included.
- Add accounting data for value and quality signals.
- Model costs from bid-ask spreads instead of a flat 25 bp.

## Part 6: resume bullets

- Backtested five equity factors on NIFTY-50 stocks (2013–2022) in Python, with
  unit tests proving no look-ahead bias, cost-aware turnover, and Newey-West and
  Holm-corrected inference.
- Showed that survivorship bias inflated a naive backtest's annual return from
  12% to 22%, and traced a "negative low-volatility premium" to market beta and
  five stocks.
- Found that momentum was the only factor with significant market-adjusted alpha
  (12.6% a year, t = 2.6) after a multiple-testing correction.

**For consulting interviews**, lead with the lesson: "Most impressive-looking
backtests are wrong, and here's how I found out why in mine." Say this before
mentioning any statistics.
