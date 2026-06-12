"""The agent loop: snapshot -> decide -> risk-check -> execute -> journal.

The decision engine proposes orders; this module is the authority. Every
guardrail lives here in plain code so the worst the model can do is propose
a bad trade *within* the limits you configured.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass

from .broker import InsufficientMargin, PaperBroker
from .config import Config
from .decision import Decision, DecisionEngine, Order
from .journal import Journal, trade_memory
from .marketdata import MarketDataSource


@dataclass
class CycleResult:
    decision: Decision
    executed: list[dict]
    rejected: list[dict]
    triggered_stops: list[dict]
    equity: float


class Agent:
    def __init__(self, config: Config, data: MarketDataSource, broker: PaperBroker,
                 engine: DecisionEngine, journal: Journal):
        self.config = config
        self.data = data
        self.broker = broker
        self.engine = engine
        self.journal = journal
        self._day_start_equity: float | None = None
        self._day: str | None = None

    # -- risk guardrails (code, not model) -----------------------------------

    def _roll_day(self, equity: float) -> None:
        today = time.strftime("%Y-%m-%d", time.gmtime())
        if self._day != today:
            self._day = today
            self._day_start_equity = equity

    def _daily_loss_breached(self, equity: float) -> bool:
        if not self._day_start_equity:
            return False
        drawdown_pct = (self._day_start_equity - equity) / self._day_start_equity * 100
        return drawdown_pct >= self.config.daily_loss_limit_pct

    def _vet_order(self, order: Order, equity: float, prices: dict[str, float]) -> str | None:
        """Returns a rejection reason, or None if the order may proceed (after clamping)."""
        if order.symbol not in self.config.symbols:
            return f"{order.symbol} is outside the configured universe {self.config.symbols}"
        if order.action == "close":
            if order.symbol not in self.broker.positions:
                return f"no open position in {order.symbol} to close"
            return None
        # opens
        if self._daily_loss_breached(equity):
            return "daily loss limit breached — no new positions until next UTC day"
        if len(self.broker.positions) >= self.config.max_open_positions:
            return f"already at max open positions ({self.config.max_open_positions})"
        if order.symbol in self.broker.positions:
            return f"position already open in {order.symbol}"
        if not order.size_usd or order.size_usd <= 0:
            return "open order missing a positive size_usd"
        # Clamp rather than reject: the model sizes within limits or gets trimmed.
        order.size_usd = min(order.size_usd, self.config.max_position_usd)
        order.leverage = min(max(order.leverage or 1.0, 1.0), self.config.max_leverage)
        # Sanity-check the stop is on the correct side of price.
        price = prices[order.symbol]
        if order.stop_loss is not None:
            wrong_side = (order.action == "open_long" and order.stop_loss >= price) or \
                         (order.action == "open_short" and order.stop_loss <= price)
            if wrong_side:
                return f"stop_loss {order.stop_loss} is on the wrong side of price {price}"
        return None

    # -- the loop -------------------------------------------------------------

    def run_cycle(self) -> CycleResult:
        snapshot = self.data.snapshot(self.config.symbols)
        prices = {s: a.mid_price for s, a in snapshot.assets.items()}

        # Stops/TPs fire on fresh prices before the model gets a say.
        triggered = self.broker.mark(prices)
        for fill in triggered:
            self.journal.write("fill", {
                "symbol": fill.symbol, "side": fill.side, "price": fill.price,
                "qty": fill.qty, "realized_pnl": fill.realized_pnl, "reason": fill.reason,
            })

        equity = self.broker.equity(prices)
        self._roll_day(equity)

        positions = [{
            "symbol": p.symbol, "side": p.side, "entry_price": p.entry_price,
            "qty": p.qty, "leverage": p.leverage, "stop_loss": p.stop_loss,
            "take_profit": p.take_profit,
            "unrealized_pnl": round(p.unrealized_pnl(prices.get(p.symbol, p.entry_price)), 2),
            "thesis": p.thesis,
        } for p in self.broker.positions.values()]

        decision = self.engine.decide(
            strategy=self._strategy_text(),
            snapshot=snapshot,
            positions=positions,
            equity=equity,
            recent_journal=self.journal.recent_for_prompt(),
            memory=trade_memory(self.broker.closed_trades),
            risk_limits={
                "max_position_usd": self.config.max_position_usd,
                "max_leverage": self.config.max_leverage,
                "max_open_positions": self.config.max_open_positions,
                "daily_loss_limit_pct": self.config.daily_loss_limit_pct,
            },
        )

        executed, rejected = [], []
        for order in decision.orders:
            reason = self._vet_order(order, equity, prices)
            if reason is not None:
                rejected.append({"order": order.model_dump(), "rejected_because": reason})
                continue
            try:
                executed.append(self._execute(order, prices))
            except (InsufficientMargin, ValueError) as exc:
                rejected.append({"order": order.model_dump(), "rejected_because": str(exc)})

        equity_after = self.broker.equity(prices)
        self.journal.write("decision", {
            "assessment": decision.assessment,
            "confidence": decision.confidence,
            "orders": [o.model_dump() for o in decision.orders],
            "executed": executed,
            "rejected": rejected,
            "equity": round(equity_after, 2),
            "prices": prices,
        })
        return CycleResult(decision=decision, executed=executed, rejected=rejected,
                           triggered_stops=[asdict(f) for f in triggered], equity=equity_after)

    def _execute(self, order: Order, prices: dict[str, float]) -> dict:
        price = prices[order.symbol]
        if order.action == "close":
            fill = self.broker.close(order.symbol, price)
            record = {"action": "close", "symbol": order.symbol, "price": fill.price,
                      "realized_pnl": round(fill.realized_pnl or 0, 2), "thesis": order.thesis}
        else:
            side = "long" if order.action == "open_long" else "short"
            pos = self.broker.open(order.symbol, side, order.size_usd, order.leverage, price,
                                   stop_loss=order.stop_loss, take_profit=order.take_profit,
                                   thesis=order.thesis)
            record = {"action": order.action, "symbol": order.symbol, "price": pos.entry_price,
                      "size_usd": order.size_usd, "leverage": order.leverage,
                      "stop_loss": order.stop_loss, "take_profit": order.take_profit,
                      "thesis": order.thesis}
        self.journal.write("fill", record)
        return record

    def _strategy_text(self) -> str:
        path = self.config.strategy_path
        if not path.exists():
            raise FileNotFoundError(
                f"No strategy file at {path}. Write your strategy in plain English there."
            )
        return path.read_text()
