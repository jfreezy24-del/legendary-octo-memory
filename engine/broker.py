"""Paper broker: simulated fills, leverage, stops, and PnL.

This is the default (and currently only) execution backend. The interface is
small on purpose so a live adapter can be added later behind the same calls —
but nothing in this repo touches real funds.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

Side = Literal["long", "short"]


@dataclass
class Position:
    symbol: str
    side: Side
    qty: float  # base units, always positive
    entry_price: float
    leverage: float
    margin: float  # cash locked for this position
    stop_loss: float | None = None
    take_profit: float | None = None
    opened_at: float = field(default_factory=time.time)
    thesis: str = ""

    def unrealized_pnl(self, price: float) -> float:
        direction = 1 if self.side == "long" else -1
        return (price - self.entry_price) * self.qty * direction

    @property
    def notional(self) -> float:
        return self.qty * self.entry_price


@dataclass
class Fill:
    timestamp: float
    symbol: str
    side: str  # "open_long" | "open_short" | "close"
    qty: float
    price: float
    fee: float
    realized_pnl: float | None = None
    reason: str = ""  # "agent" | "stop_loss" | "take_profit"


@dataclass
class ClosedTrade:
    symbol: str
    side: Side
    qty: float
    entry_price: float
    exit_price: float
    realized_pnl: float
    opened_at: float
    closed_at: float
    exit_reason: str
    thesis: str = ""


class InsufficientMargin(Exception):
    pass


class PaperBroker:
    def __init__(self, starting_cash: float, fee_bps: float = 4.5, slippage_bps: float = 2.0,
                 state_path: Path | None = None):
        self.cash = starting_cash
        self.fee_bps = fee_bps
        self.slippage_bps = slippage_bps
        self.positions: dict[str, Position] = {}
        self.closed_trades: list[ClosedTrade] = []
        self.fills: list[Fill] = []
        self._state_path = state_path
        if state_path is not None and state_path.exists():
            self._load(state_path)

    # -- trading ------------------------------------------------------------

    def _exec_price(self, mid: float, aggressing_up: bool) -> float:
        slip = mid * self.slippage_bps / 10_000
        return mid + slip if aggressing_up else mid - slip

    def open(self, symbol: str, side: Side, size_usd: float, leverage: float, mid_price: float,
             stop_loss: float | None = None, take_profit: float | None = None,
             thesis: str = "") -> Position:
        if symbol in self.positions:
            raise ValueError(f"Position already open in {symbol}; close it first")
        price = self._exec_price(mid_price, aggressing_up=(side == "long"))
        qty = size_usd / price
        margin = size_usd / leverage
        fee = size_usd * self.fee_bps / 10_000
        if margin + fee > self.cash:
            raise InsufficientMargin(
                f"Need {margin + fee:.2f} (margin {margin:.2f} + fee {fee:.2f}), have {self.cash:.2f}"
            )
        self.cash -= margin + fee
        pos = Position(symbol=symbol, side=side, qty=qty, entry_price=price, leverage=leverage,
                       margin=margin, stop_loss=stop_loss, take_profit=take_profit, thesis=thesis)
        self.positions[symbol] = pos
        self.fills.append(Fill(time.time(), symbol, f"open_{side}", qty, price, fee, reason="agent"))
        self._save()
        return pos

    def close(self, symbol: str, mid_price: float, reason: str = "agent") -> Fill:
        pos = self.positions.pop(symbol, None)
        if pos is None:
            raise ValueError(f"No open position in {symbol}")
        price = self._exec_price(mid_price, aggressing_up=(pos.side == "short"))
        pnl = pos.unrealized_pnl(price)
        fee = pos.qty * price * self.fee_bps / 10_000
        self.cash += pos.margin + pnl - fee
        fill = Fill(time.time(), symbol, "close", pos.qty, price, fee, realized_pnl=pnl, reason=reason)
        self.fills.append(fill)
        self.closed_trades.append(ClosedTrade(
            symbol=symbol, side=pos.side, qty=pos.qty, entry_price=pos.entry_price,
            exit_price=price, realized_pnl=pnl - fee, opened_at=pos.opened_at,
            closed_at=fill.timestamp, exit_reason=reason, thesis=pos.thesis,
        ))
        self._save()
        return fill

    def mark(self, prices: dict[str, float]) -> list[Fill]:
        """Check stops / take-profits against current prices. Returns triggered fills."""
        triggered: list[Fill] = []
        for symbol in list(self.positions):
            pos = self.positions[symbol]
            price = prices.get(symbol)
            if price is None:
                continue
            hit_stop = pos.stop_loss is not None and (
                price <= pos.stop_loss if pos.side == "long" else price >= pos.stop_loss
            )
            hit_tp = pos.take_profit is not None and (
                price >= pos.take_profit if pos.side == "long" else price <= pos.take_profit
            )
            if hit_stop:
                triggered.append(self.close(symbol, price, reason="stop_loss"))
            elif hit_tp:
                triggered.append(self.close(symbol, price, reason="take_profit"))
        return triggered

    # -- accounting ---------------------------------------------------------

    def equity(self, prices: dict[str, float]) -> float:
        eq = self.cash
        for pos in self.positions.values():
            price = prices.get(pos.symbol, pos.entry_price)
            eq += pos.margin + pos.unrealized_pnl(price)
        return eq

    # -- persistence ----------------------------------------------------------

    def _save(self) -> None:
        if self._state_path is None:
            return
        state = {
            "cash": self.cash,
            "positions": {s: asdict(p) for s, p in self.positions.items()},
            "closed_trades": [asdict(t) for t in self.closed_trades],
        }
        self._state_path.write_text(json.dumps(state, indent=2))

    def _load(self, path: Path) -> None:
        state = json.loads(path.read_text())
        self.cash = state["cash"]
        self.positions = {s: Position(**p) for s, p in state["positions"].items()}
        self.closed_trades = [ClosedTrade(**t) for t in state.get("closed_trades", [])]
