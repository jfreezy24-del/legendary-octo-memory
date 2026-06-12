"""The decision engine: Claude reads the market, your strategy, and its own
trading history, and returns a typed, fully-reasoned decision.

The model proposes; code disposes. Risk limits are enforced in agent.py after
this returns — nothing the model says can exceed them.
"""

from __future__ import annotations

import json
from typing import Literal, Protocol

import anthropic
from pydantic import BaseModel, Field

from .marketdata import MarketSnapshot


class Order(BaseModel):
    action: Literal["open_long", "open_short", "close"]
    symbol: str
    size_usd: float | None = Field(
        default=None, description="Notional size in USD. Required for opens, ignored for closes."
    )
    leverage: float | None = Field(
        default=None, description="Leverage for opens. Will be clamped to the configured maximum."
    )
    stop_loss: float | None = Field(default=None, description="Stop-loss price. Strongly recommended for opens.")
    take_profit: float | None = Field(default=None, description="Take-profit price, if the thesis has a target.")
    thesis: str = Field(description="Why this order, in plain English, citing the numbers that support it.")


class Decision(BaseModel):
    assessment: str = Field(
        description="Plain-English read of current conditions across the universe: funding, momentum, "
        "regime, and how it relates to the strategy. This is logged verbatim."
    )
    orders: list[Order] = Field(
        default_factory=list,
        description="Orders to execute now. Empty list means hold / do nothing.",
    )
    confidence: float = Field(description="Overall conviction in this decision, 0 to 1.")


class DecisionEngine(Protocol):
    def decide(self, *, strategy: str, snapshot: MarketSnapshot, positions: list[dict],
               equity: float, recent_journal: list[dict], memory: list[dict],
               risk_limits: dict) -> Decision: ...


SYSTEM_PROMPT = """\
You are Engine, an autonomous trading agent operating a PAPER (simulated) account.
You trade exactly one thing: the strategy the operator wrote, reproduced below.
You are not a general assistant; every output is a trading decision.

Principles:
- Trade the strategy as written. If current conditions don't match any setup the
  strategy describes, the correct decision is an empty order list.
- Weigh signals together (funding, momentum, volume, your own past trades in
  similar conditions) rather than reacting to one number.
- Learn from your trade memory: if a pattern keeps losing, stop repeating it and
  say so in your assessment.
- Every open should carry a stop_loss. Size positions so a stop-out is survivable.
- Your assessment and theses are logged verbatim and shown to the operator —
  write them so a human can audit the decision from the numbers you cite.
- Hard risk limits (max position size, max leverage, max open positions, daily
  loss kill-switch) are enforced by the harness after you respond. Don't try to
  exceed them; size within them.

THE OPERATOR'S STRATEGY (STRATEGY.md):
---
{strategy}
---
"""


class ClaudeDecisionEngine:
    def __init__(self, model: str = "claude-opus-4-8"):
        self.client = anthropic.Anthropic()
        self.model = model

    def decide(self, *, strategy: str, snapshot: MarketSnapshot, positions: list[dict],
               equity: float, recent_journal: list[dict], memory: list[dict],
               risk_limits: dict) -> Decision:
        state = {
            "market": snapshot.to_prompt_dict(),
            "account": {"equity_usd": round(equity, 2), "open_positions": positions},
            "risk_limits": risk_limits,
            "recent_activity": recent_journal,
            "trade_memory": memory,
        }
        response = self.client.messages.parse(
            model=self.model,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            system=[{
                "type": "text",
                "text": SYSTEM_PROMPT.format(strategy=strategy),
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{
                "role": "user",
                "content": (
                    "Current state follows as JSON. Decide what, if anything, to do this cycle.\n\n"
                    + json.dumps(state, indent=2)
                ),
            }],
            output_format=Decision,
        )
        decision = response.parsed_output
        if decision is None:
            raise RuntimeError(f"Model returned no parseable decision (stop_reason={response.stop_reason})")
        return decision


def build_chat_reply(model: str, strategy: str, journal_entries: list[dict],
                     positions: list[dict], question: str) -> str:
    """One-shot Q&A with the agent over its own decision log ("why did you...")."""
    client = anthropic.Anthropic()
    context = {
        "open_positions": positions,
        "decision_log": journal_entries,
    }
    with client.messages.stream(
        model=model,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=[{
            "type": "text",
            "text": SYSTEM_PROMPT.format(strategy=strategy)
            + "\nRight now you are answering the operator's question about your own past "
            "decisions. Answer from the decision log below — cite the actual numbers and "
            "theses recorded there. If the log doesn't contain the answer, say so.",
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{
            "role": "user",
            "content": json.dumps(context, indent=2) + f"\n\nOperator question: {question}",
        }],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
        print()
        final = stream.get_final_message()
    return next((b.text for b in final.content if b.type == "text"), "")
