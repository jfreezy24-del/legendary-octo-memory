"""Agent loop tests with a scripted (non-LLM) decision engine."""

from pathlib import Path

import pytest

from engine.agent import Agent
from engine.broker import PaperBroker
from engine.config import Config
from engine.decision import Decision, Order
from engine.journal import Journal
from engine.marketdata import ReplayDataSource


class ScriptedEngine:
    """Returns queued decisions in order; holds when the queue is empty."""

    def __init__(self, decisions=None):
        self.queue = list(decisions or [])
        self.calls = []

    def decide(self, **kwargs):
        self.calls.append(kwargs)
        if self.queue:
            return self.queue.pop(0)
        return Decision(assessment="nothing matches a setup", orders=[], confidence=0.9)


def make_agent(tmp_path: Path, decisions=None, **config_overrides) -> tuple[Agent, ScriptedEngine]:
    config = Config(data_dir=tmp_path)
    for k, v in config_overrides.items():
        setattr(config, k, v)
    (tmp_path / "STRATEGY.md").write_text("# Strategy\nTest strategy.")
    engine = ScriptedEngine(decisions)
    agent = Agent(
        config=config,
        data=ReplayDataSource(seed=7),
        broker=PaperBroker(config.starting_cash, fee_bps=0, slippage_bps=0),
        engine=engine,
        journal=Journal(config.journal_path),
    )
    return agent, engine


def open_order(symbol="BTC", action="open_long", size=500.0, lev=2.0, **kw):
    return Order(action=action, symbol=symbol, size_usd=size, leverage=lev,
                 thesis="scripted test order", **kw)


def test_hold_cycle_logs_decision(tmp_path):
    agent, engine = make_agent(tmp_path)
    result = agent.run_cycle()
    assert result.executed == [] and result.rejected == []
    last = agent.journal.last_decision()
    assert last["assessment"] == "nothing matches a setup"
    # The engine was shown account state and risk limits.
    assert engine.calls[0]["risk_limits"]["max_leverage"] == agent.config.max_leverage


def test_open_executes_and_journals(tmp_path):
    agent, _ = make_agent(tmp_path, decisions=[
        Decision(assessment="long it", orders=[open_order()], confidence=0.8),
    ])
    result = agent.run_cycle()
    assert len(result.executed) == 1
    assert "BTC" in agent.broker.positions
    fills = agent.journal.entries(kind="fill")
    assert fills and fills[0]["symbol"] == "BTC"


def test_oversize_order_is_clamped_not_rejected(tmp_path):
    agent, _ = make_agent(
        tmp_path,
        decisions=[Decision(assessment="huge", orders=[open_order(size=50_000, lev=20)], confidence=1.0)],
        max_position_usd=1_000.0, max_leverage=3.0,
    )
    result = agent.run_cycle()
    assert len(result.executed) == 1
    pos = agent.broker.positions["BTC"]
    assert pos.notional == pytest.approx(1_000.0, rel=1e-6)
    assert pos.leverage == 3.0


def test_unknown_symbol_rejected(tmp_path):
    agent, _ = make_agent(tmp_path, decisions=[
        Decision(assessment="off-universe", orders=[open_order(symbol="DOGE")], confidence=0.5),
    ])
    result = agent.run_cycle()
    assert result.executed == []
    assert "outside the configured universe" in result.rejected[0]["rejected_because"]


def test_max_open_positions_enforced(tmp_path):
    agent, _ = make_agent(
        tmp_path,
        decisions=[Decision(assessment="all in", orders=[
            open_order("BTC"), open_order("ETH"), open_order("SOL"),
        ], confidence=1.0)],
        max_open_positions=2,
    )
    result = agent.run_cycle()
    assert len(result.executed) == 2
    assert len(result.rejected) == 1
    assert "max open positions" in result.rejected[0]["rejected_because"]


def test_wrong_side_stop_rejected(tmp_path):
    agent, _ = make_agent(tmp_path, decisions=[
        Decision(assessment="bad stop", orders=[
            open_order(stop_loss=10_000_000.0),  # stop above price on a long
        ], confidence=0.7),
    ])
    result = agent.run_cycle()
    assert result.executed == []
    assert "wrong side" in result.rejected[0]["rejected_because"]


def test_daily_loss_kill_switch(tmp_path):
    open_decision = Decision(assessment="open", orders=[open_order()], confidence=0.9)
    agent, engine = make_agent(tmp_path, decisions=[], daily_loss_limit_pct=5.0)
    agent.run_cycle()  # establishes day-start equity
    agent.broker.cash -= agent.config.starting_cash * 0.10  # simulate 10% loss
    engine.queue.append(open_decision)
    result = agent.run_cycle()
    assert result.executed == []
    assert "daily loss limit" in result.rejected[0]["rejected_because"]


def test_close_order_round_trip(tmp_path):
    agent, engine = make_agent(tmp_path, decisions=[
        Decision(assessment="open", orders=[open_order()], confidence=0.8),
    ])
    agent.run_cycle()
    engine.queue.append(Decision(
        assessment="thesis played out",
        orders=[Order(action="close", symbol="BTC", thesis="done")],
        confidence=0.8,
    ))
    result = agent.run_cycle()
    assert result.executed[0]["action"] == "close"
    assert "BTC" not in agent.broker.positions
    assert len(agent.broker.closed_trades) == 1
    # Closed trade now appears in the memory fed to the next decision.
    agent.run_cycle()
    assert engine.calls[-1]["memory"][0]["symbol"] == "BTC"
