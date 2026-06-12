import time

from engine.broker import ClosedTrade
from engine.journal import Journal, trade_memory


def test_journal_round_trip(tmp_path):
    j = Journal(tmp_path / "journal.jsonl")
    j.write("decision", {"assessment": "hold", "confidence": 0.5, "orders": []})
    j.write("fill", {"symbol": "BTC", "side": "open_long", "price": 100.0})
    j.write("decision", {"assessment": "still hold", "confidence": 0.6, "orders": []})

    assert len(j.entries()) == 3
    assert len(j.entries(kind="decision")) == 2
    assert j.last_decision()["assessment"] == "still hold"
    assert len(j.entries(limit=1)) == 1


def test_recent_for_prompt_is_compact(tmp_path):
    j = Journal(tmp_path / "journal.jsonl")
    j.write("decision", {"assessment": "x" * 1000, "orders": []})
    compact = j.recent_for_prompt()
    assert len(compact[0]["assessment"]) == 300
    assert "when" in compact[0]


def test_trade_memory_filters_and_orders():
    now = time.time()
    trades = [
        ClosedTrade("BTC", "long", 1, 100, 110, 10.0, now - 600, now - 300, "agent", thesis="a"),
        ClosedTrade("ETH", "short", 1, 200, 210, -10.0, now - 500, now - 200, "stop_loss", thesis="b"),
        ClosedTrade("BTC", "long", 1, 105, 100, -5.0, now - 400, now - 100, "stop_loss", thesis="c"),
    ]
    mem = trade_memory(trades)
    assert [m["symbol"] for m in mem] == ["BTC", "ETH", "BTC"]  # most recent first
    assert mem[0]["pnl_usd"] == -5.0

    btc_only = trade_memory(trades, symbol="BTC")
    assert all(m["symbol"] == "BTC" for m in btc_only)
    assert len(btc_only) == 2
