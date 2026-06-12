# Quantum Pivot — TradingView Indicator

A Pine Script v6 overlay indicator ([`quantum_pivot.pine`](quantum_pivot.pine)) implementing the **Quantum Pivot** strategy by Bitcoin Playboy, automating its four chapters:

1. **Where to find a bias shift**
2. **Where to find entry on imbalances after the bias shift**
3. **What liquidity to target after entry**
4. **How to produce multiple trades within the same trend**

## 01 — Bias shift (Strong / Weak levels)

Swings are detected from confirmed pivots and classified exactly as the model defines — only *after* the next move resolves them:

| Rule | Classification |
|---|---|
| High resulted in a lower low | **Strong High** |
| High failed to make a lower low | **Weak High** |
| Low resulted in a higher high | **Strong Low** |
| Low failed to make a higher high | **Weak Low** |

Strong levels are drawn as **solid lines** (where you look to enter), weak levels as **dashed lines** (where you look to target). A **bias shift / MSB** fires when price closes through a *Strong* level — that bar is marked with a `QP` diamond, and the background tint flips to the new bias.

## 02 — Entry on the imbalance

When a strong level breaks, the script scans the impulse that broke it for the most recent **fair value gap** (falling back to the last opposite-direction candle — an **order block** — if no FVG exists). That imbalance is boxed as the entry zone. A `LONG`/`SHORT` triangle prints on the pullback into it (touch or close-inside, your choice). Stops belong below/above the imbalance — the zone is greyed out as *invalidated* if price closes through its far side first.

## 03 — Targets

Enter on the **internal** imbalance, target the **external** levels: after a bullish pivot, the previous downtrend's highs (the lines drawn overhead) are the target ladder, and vice versa.

## 04 — Multiple trades per trend

Each time another level is taken out in the direction of the bias (marked with a small circle), the imbalance formed before *that* raid is boxed as the next entry zone — so a single pivot chains into a sequence of continuation entries, exactly as chapter 04 describes.

## Signals & alerts

- `QP` diamond — quantum pivot (strong level broken, bias shifted)
- Small circle — continuation raid (next level taken in-trend, fresh zone marked)
- `LONG` / `SHORT` triangle — pullback into the active imbalance

All six events have `alertcondition`s for TradingView alerts.

## Inputs

- **Pivot length** — bars each side to confirm a swing; larger = higher-timeframe structure.
- **Imbalance scan depth** — how far back to look for the FVG left by the breaking impulse.
- **Fall back to order block** — use the last opposite candle when no FVG exists.
- **Pullback entry trigger** — `Touch` or `Close inside` (more conservative).
- **Style** — colors, swing labels, level lines, bias background tint.

## Notes

- The model notes that MSBs inside a sideways range are irrelevant until an out-of-range strong level breaks, and that the best setups follow an interaction with a higher-timeframe POI — both remain discretionary judgements for the trader; the indicator marks every qualifying strong-level break.
- Install: paste `quantum_pivot.pine` into TradingView's Pine Editor → *Add to chart*.

*Analysis tool only — not financial advice. Backtest before trading.*
