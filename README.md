# legendary-octo-memory

## ICT Unicorn Model — Indicator

A TradingView **Pine Script v5** indicator that reproduces the *ICT Unicorn Model*
"High Probability Entry Framework" shown in the reference chart.

> The Unicorn forms when a **Breaker Block** overlaps with a **Fair Value Gap (FVG)**.
> This confluence creates a precision entry zone after liquidity is taken and structure shifts.
>
> `Liquidity → MSS → Breaker + FVG overlap → Retrace → Expansion`

File: [`ICT_Unicorn_Model.pine`](ICT_Unicorn_Model.pine)

### What it draws (matches the photo)

| Element | Visual |
| --- | --- |
| **Unicorn zone** | Green shaded box = the Breaker × FVG overlap (the entry zone) |
| **MSS** | Dashed line + `MSS` label where structure shifts with displacement |
| **Breaker** | Outlined box + `Breaker` label on the breaker block |
| **Overlapped FVG** | Green-filled box + `Overlapped FVG` label |
| **Liquidity lines** | Toggleable red previous-candle high/low lines per timeframe |

### Liquidity — Previous Candle High / Low (toggleable)

Each timeframe has its own on/off switch under **Liquidity — Previous Candle High / Low**:

| Toggle | Draws |
| --- | --- |
| Previous Day | `PDH` / `PDL` |
| Previous Week | `PWH` / `PWL` |
| Previous Month | `PMH` / `PML` |
| Previous 4H | `P4H` / `P4L` |
| Previous 1H | `P1H` / `P1L` |

Shared controls: unswept line color, **raided line color**, base style (Solid / Dashed /
Dotted), width, and label visibility. Each level pulls the **previous completed candle's**
high/low for that timeframe, so they act as standing liquidity pools to target.

**Swept state:** each side of a level is drawn **solid** in the unswept color until price
takes it out, then flips to **dashed** in the raided color (high and low tracked
independently). The state resets when a new period prints a fresh level.

### Standard-deviation targets (fractal projection)

On a valid setup the indicator projects standard-deviation multiples anchored to the
**Unicorn zone**: `0` = the zone edge (entry / `BB`), `1` = C2 (the manipulation extreme
that swept liquidity), and negatives (`-1`, `-2`, `-2.5`, …) are the **draw-on-liquidity
targets**. The unit = C2 − zone, so the whole ladder scales with the zone. Levels are drawn as a tick ladder at the right edge with `C2` / `BB` labels, and
an optional shaded **target zone** between two chosen multiples. Edit the set under
**Standard Deviation Targets → Levels** (comma-separated, e.g. `1, 0, -1, -2, -2.5`).

### Fractal HTF candle panel

Set an **HTF Timeframe** (e.g. `60` for 1H while charting 5m). The last *N* completed HTF
candles are drawn as a mini candle panel to the right of price — the "5m – 1H" fractal view
from the reference — with hour labels and a **model info label** (`5 – 60 Model` + Bias).
Configure under **Fractal Pair (HTF candle panel)**.

### How the logic works

1. **Liquidity** — swing pivots (`Swing Pivot Length`) mark engineered liquidity; a
   wick beyond a swing that closes back inside counts as a sweep / raid.
2. **MSS** — a close that breaks the opposing swing **with displacement**
   (body ≥ `Displacement Strength × ATR`) confirms the Market Structure Shift.
3. **Breaker + FVG overlap** — the last opposing candle becomes the breaker block;
   the 3-candle imbalance is the FVG. Their intersection is drawn as the **Unicorn zone**.
4. **Narrative gate** — with `Require Liquidity Sweep` on, no sweep = no model
   (*No narrative = No model*). Choose which pools count as the raid under
   **Structure / Narrative**: swing highs/lows and/or previous **Day / Week / Month**
   high/low. A sweep stays valid as narrative for `Raid Memory (bars)` while the
   model waits for the MSS — e.g. price raids the **previous week low**, then a
   bullish MSS within that window validates the Unicorn.
5. **Targets** — draw on opposing-side liquidity (PDH / PDL lines) for the expansion leg.

### Install

1. Open [TradingView](https://www.tradingview.com/) → **Pine Editor**.
2. Paste the contents of `ICT_Unicorn_Model.pine`.
3. **Add to chart**. Tune inputs (swing length, displacement, colors) under the gear icon.
4. Optional: create alerts from the **Bullish / Bearish Unicorn** conditions.

### Display / History

- **Limit Max Lookback** — when on, detection and drawing only happen within the last
  *N* bars (`Max Lookback (bars)`), keeping the chart light on long histories.
- **Historical Setups on Chart** — how many of the most recent Unicorn setups to keep
  drawn (1–50). Older setups (their zone, breaker, FVG, MSS line and labels) are removed
  automatically as new ones print.

### Alerts

- **Unicorn:** `Bullish Unicorn`, `Bearish Unicorn` — fire when a valid setup forms.
- **Liquidity sweeps:** `PDH/PDL`, `PWH/PWL`, `PMH/PML`, plus `Any High Swept` /
  `Any Low Swept` — fire when price takes out an **enabled** previous-candle high/low.

Create alerts from these conditions (Add Alert → Condition → *ICT Unicorn Model*), or use
the built-in `alert()` pushes toggled by **Enable Unicorn Alerts** /
**Enable Liquidity Sweep Alerts**.

> Educational tool for discretionary ICT-style analysis — not financial advice.
