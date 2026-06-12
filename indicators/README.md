# OHLC Stat Map

A TradingView **Pine Script v5** indicator (`ohlc_stat_map.pine`) that projects
statistical *manipulation* and *distribution* levels around the open of a chosen
anchor candle, based on the **Power of Three (Po3)** model:
**Accumulation → Manipulation → Distribution**.

## What it does

For an **anchor timeframe** (Weekly / Daily / 4H / …), every completed candle is
measured relative to its **open**:

| Candle    | Manipulation (fake move) | Distribution (true expansion) |
|-----------|--------------------------|-------------------------------|
| Bullish (`close ≥ open`) | `open − low`  (below open) | `high − open` (above open) |
| Bearish (`close < open`) | `high − open` (above open) | `open − low`  (below open) |

These distances are averaged over a **lookback** window. When a new anchor candle
opens, the average distances are projected above and below the opening price:

```
+ Distribution   = open + avgDistribution     ← top of the upper range
- Manipulation   = open + avgManipulation
================  OPEN  ================
+ Manipulation   = open − avgManipulation
- Distribution   = open − avgDistribution     ← bottom of the lower range
```

### Ranges
- **Manipulation range** — between `- Manipulation` and `+ Manipulation`; the
  main range where price first trades. `-M` acts as resistance, `+M` as support.
- **+ Distribution range** — between `- Manipulation` and `+ Distribution`; traded
  when price expands higher.
- **- Distribution range** — between `+ Manipulation` and `- Distribution`; traded
  when price expands lower.

Levels serve as potential reversal zones. They are statistical, not signals —
combine with HTF bias and an entry trigger (e.g. an IFVG / inversion FVG after a
liquidity sweep).

## Inputs

| Input | Default | Description |
|-------|---------|-------------|
| Anchor timeframe | `D` | HTF candle the map is anchored to. |
| Lookback (candles) | `20` | Completed anchor candles used to average distances. |
| Separate bull/bear averages | off | Average manipulation/distribution separately for bullish and bearish candles. |
| Shade ranges | on | Fill the manipulation and distribution ranges. |
| Show labels | on | Label each level. |
| Extend levels right | on | Extend lines past the current bar. |
| Colors / line width | — | Styling for manipulation, distribution and open lines. |

## Suggested anchor / entry pairing (from the source)

| Po3 cycle | Trade timeframe |
|-----------|-----------------|
| Monthly | 4H |
| Weekly  | 1H |
| Daily   | 15m |
| 4H      | 5m |
| 1H      | 1m |

## Alerts
- **Tagged Manipulation level** — price crosses `±` Manipulation.
- **Tagged Distribution level** — price crosses `±` Distribution.

## Install
1. Open TradingView → **Pine Editor**.
2. Paste the contents of `ohlc_stat_map.pine`.
3. **Add to chart** and adjust the anchor timeframe / lookback to taste.

> Educational tool based on the "Stat Map" / Po3 concept. Not financial advice.
