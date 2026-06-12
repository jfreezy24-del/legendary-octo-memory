# Flip Zone Entry Model — TradingView Indicator

A Pine Script v6 overlay indicator ([`flip_zone_entry.pine`](flip_zone_entry.pine)) that automates the **flip zone entry model**:

> **Step 1:** Wait for price to mitigate your point of interest (POI).
> **Step 2:** Look for a failed reaction at the opposing zone.
> **Step 3:** That failed reaction becomes your flip zone.
> **Entry:** Enter on the pullback to the flip zone after the market shift confirms.

## How the indicator maps the model

Zones are built automatically from confirmed swing pivots: swing lows create **demand zones**, swing highs create **supply zones**. Every zone then moves through a state machine. For the bullish case (the bearish case is the exact mirror):

| Model concept | Indicator behavior |
|---|---|
| Point of interest | A demand zone from a confirmed swing low |
| Step 1 — Mitigation | Price trades back into that demand zone (`demand • mitigated`). This *arms* the bull side for `POI validity` bars. |
| Opposing zone | A supply zone overhead |
| Step 2 — Reaction | Price taps the supply, then pulls away from it by at least the minimum reaction size (`supply • reacting`) |
| Step 2 — Failed reaction | Price comes back and **closes through** the supply |
| Market shift | The close is also beyond the swing high the reaction created (toggleable) |
| Step 3 — Flip zone | The broken supply is repainted as a flip zone (`FLIP ▲ now demand`) and an orange diamond marks the confirmation bar |
| Entry | The first pullback into the flip zone prints a `LONG` triangle and fires an alert |

A flip zone is invalidated (greyed out or removed) if price closes back through its far side before the pullback entry occurs. A flip only counts if the POI on the *same side* was mitigated first — breaks of zones without a prior POI mitigation are discarded, which is what separates this model from a plain breakout-retest tool.

## Signals

- **Orange diamond** — flip zone confirmed (step 3 complete, market shift done).
- **Green `LONG` triangle** — price pulled back into a bullish flip zone.
- **Red `SHORT` triangle** — price pulled back into a bearish flip zone.

All four events have matching `alertcondition`s, so you can create TradingView alerts on flip confirmation (to get ready) and on the pullback entry (to act).

## Inputs

**Zone detection**
- *Pivot length* — bars on each side required to confirm a swing. Larger = fewer, more significant zones (zones appear with this delay, as pivots must confirm).
- *Zone width* — `Wick` (pivot extreme to candle body) or `Full bar` (high to low).
- *Max active zones per side* — oldest zones are dropped beyond this.
- *POI validity (bars)* — how long a POI mitigation keeps the model armed.

**Flip model**
- *Require a reaction before the flip* — enforces step 2 strictly. If off, any break of a mitigated opposing zone flips it.
- *Min. reaction size (% of zone height)* — how far price must pull away for the move to count as a reaction.
- *Require market structure shift* — the flip must close beyond the reaction swing, not just beyond the zone.
- *Pullback entry trigger* — `Touch` (signal on the first tag of the flip zone) or `Close inside` (wait for a close inside it, more conservative).

## Installation

1. Open TradingView → Pine Editor.
2. Paste the contents of `flip_zone_entry.pine`.
3. Click **Add to chart**, then set alerts on the conditions you want.

## Trade management (not automated)

The indicator signals entries only. Conventional management for this model: stop loss beyond the far side of the flip zone (the level whose breach also invalidates the zone on the chart), first target at the swing created by the move that confirmed the flip.

*This is an analysis tool, not financial advice. Backtest before trading it.*
