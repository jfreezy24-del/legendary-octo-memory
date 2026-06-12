# Engine — a transparent, paper-first LLM trading agent

A self-built take on the "agentic trading" idea: an agent that trades the
strategy you describe in plain English, explains every decision it makes, and
learns from its own trade history — **on a simulated (paper) account**. No
exchange keys, no wallet, no real money anywhere in this codebase.

## How it works

```
STRATEGY.md ──┐
market data ──┤
positions   ──┼──> Claude decision engine ──> risk guardrails (code) ──> paper broker
trade memory ─┘            │                                                  │
                           └────────────── journal.jsonl <───────────────────┘
```

Each cycle the agent:

1. Pulls a market snapshot (price, funding, open interest, volume) from
   Hyperliquid's public read-only API — or a deterministic offline replay.
2. Fires any stop-losses / take-profits against fresh prices (in code, before
   the model is consulted).
3. Asks Claude for a decision, giving it your `STRATEGY.md`, current positions,
   recent journal entries, and the outcomes of its past trades.
4. Vets every proposed order against hard limits — max position size, max
   leverage, max open positions, a daily-loss kill-switch, stop-on-the-wrong-side
   sanity checks. Oversized orders are clamped; invalid ones are rejected and
   the rejection is logged.
5. Executes on the paper broker and writes everything — assessment, theses,
   fills, rejections, prices — to `journal.jsonl`.

The model proposes; the code disposes. The LLM can never exceed the limits in
`engine/config.py`, because they're enforced after it answers.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
export ANTHROPIC_API_KEY=sk-ant-...
```

## Usage

```bash
engine run --once          # one decision cycle
engine run --interval 300  # loop every 5 minutes
engine status              # cash, equity, positions, win rate
engine log -n 30           # tail the decision log
engine why                 # full reasoning behind the last decision
engine chat "why did you short ETH instead of BTC?"
```

Edit `STRATEGY.md` any time — the agent re-reads it every cycle.

## Configuration (env vars)

| Variable | Default | Meaning |
|---|---|---|
| `ENGINE_SYMBOLS` | `BTC,ETH,SOL` | Tradable universe |
| `ENGINE_STARTING_CASH` | `10000` | Paper account size (USD) |
| `ENGINE_MAX_POSITION_USD` | `1000` | Hard cap per position |
| `ENGINE_MAX_LEVERAGE` | `3` | Hard cap on leverage |
| `ENGINE_MAX_OPEN_POSITIONS` | `3` | Hard cap on concurrent positions |
| `ENGINE_DAILY_LOSS_LIMIT_PCT` | `5` | Stop opening new positions after this daily drawdown |
| `ENGINE_DATA_SOURCE` | `hyperliquid` | `hyperliquid` (live public data) or `replay` (offline synthetic) |
| `ENGINE_MODEL` | `claude-opus-4-8` | Decision model |
| `ENGINE_DATA_DIR` | `.` | Where strategy, journal, and broker state live |

## Tests

```bash
pytest
```

The test suite covers the paper broker (fills, fees, slippage, stops, margin,
persistence), the journal, and the agent loop with a scripted decision engine —
no API key or network needed.

## On going live

This project deliberately stops at paper trading. Before pointing anything like
this at real funds, you'd want: a long paper track record across different
market regimes, an exchange adapter with trade-only (non-withdrawal) key
permissions, much more conservative limits, monitoring/alerting, and a clear
understanding that leveraged perp trading loses money for most participants —
LLM or not. The decision quality you observe in the journal is the evidence to
weigh; collect a lot of it first.
