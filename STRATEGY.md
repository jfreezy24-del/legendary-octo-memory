# Strategy

This file is the agent's entire mandate. Edit it in plain English; the agent
re-reads it every cycle, so changes take effect on the next decision.

## Universe

BTC, ETH, SOL perpetuals only.

## Setups I want traded

**Funding fade.** When hourly funding is strongly positive (crowded longs) while
24h price change is flat or negative, open a small short. Mirror logic for
strongly negative funding with flat/positive price action: open a small long.
"Strongly" means clearly elevated versus the other assets in the universe this
cycle — use judgment, don't anchor on a fixed threshold.

**Momentum continuation.** If an asset is up or down more than 4% on the day on
elevated volume and funding is NOT already stretched in the move's direction,
take a small position with the move.

## What I never want

- No averaging down into losing positions.
- No new positions when conditions don't clearly match a setup above. Holding
  is the default, not the exception.
- Every position carries a stop-loss between 1.5% and 3% from entry.

## Sizing & exits

- Risk small: roughly 5–10% of equity notional per position, 1–2x leverage.
- Take profit at 2–3x the stop distance, or close early if the entry reason
  disappears (e.g. funding normalizes on a funding-fade trade).
- If two of my last four trades on the same setup lost, halve size on that
  setup and say so in the assessment.
