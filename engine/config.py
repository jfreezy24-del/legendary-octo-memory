"""Configuration. Everything is env-driven with safe defaults.

The risk limits here are hard guardrails enforced in code (see agent.py).
The LLM never gets to override them.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    return float(raw) if raw else default


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw else default


@dataclass
class Config:
    # Where STRATEGY.md, the journal, and paper-broker state live.
    data_dir: Path = field(
        default_factory=lambda: Path(os.environ.get("ENGINE_DATA_DIR", "."))
    )
    strategy_file: str = os.environ.get("ENGINE_STRATEGY_FILE", "STRATEGY.md")
    model: str = os.environ.get("ENGINE_MODEL", "claude-opus-4-8")

    # Universe the agent is allowed to trade.
    symbols: list[str] = field(
        default_factory=lambda: os.environ.get("ENGINE_SYMBOLS", "BTC,ETH,SOL").split(",")
    )

    # Paper account.
    starting_cash: float = field(default_factory=lambda: _env_float("ENGINE_STARTING_CASH", 10_000.0))
    fee_bps: float = field(default_factory=lambda: _env_float("ENGINE_FEE_BPS", 4.5))
    slippage_bps: float = field(default_factory=lambda: _env_float("ENGINE_SLIPPAGE_BPS", 2.0))

    # Hard risk guardrails — enforced in code, not by the model.
    max_position_usd: float = field(default_factory=lambda: _env_float("ENGINE_MAX_POSITION_USD", 1_000.0))
    max_leverage: float = field(default_factory=lambda: _env_float("ENGINE_MAX_LEVERAGE", 3.0))
    max_open_positions: int = field(default_factory=lambda: _env_int("ENGINE_MAX_OPEN_POSITIONS", 3))
    # If equity drops this fraction below the day's starting equity, the agent
    # stops opening new positions until the next UTC day.
    daily_loss_limit_pct: float = field(default_factory=lambda: _env_float("ENGINE_DAILY_LOSS_LIMIT_PCT", 5.0))

    # Market data: "hyperliquid" (live, read-only) or "replay" (offline synthetic).
    data_source: str = os.environ.get("ENGINE_DATA_SOURCE", "hyperliquid")

    @property
    def strategy_path(self) -> Path:
        return self.data_dir / self.strategy_file

    @property
    def journal_path(self) -> Path:
        return self.data_dir / "journal.jsonl"

    @property
    def broker_state_path(self) -> Path:
        return self.data_dir / "paper_broker.json"
