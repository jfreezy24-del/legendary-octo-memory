import pytest

from engine.broker import InsufficientMargin, PaperBroker


def make_broker(**kw):
    defaults = dict(starting_cash=10_000.0, fee_bps=0.0, slippage_bps=0.0)
    defaults.update(kw)
    return PaperBroker(**defaults)


def test_open_long_locks_margin_and_tracks_pnl():
    b = make_broker()
    b.open("BTC", "long", size_usd=1_000, leverage=2, mid_price=100.0)
    assert b.cash == pytest.approx(10_000 - 500)  # margin = 1000/2
    pos = b.positions["BTC"]
    assert pos.qty == pytest.approx(10.0)
    assert pos.unrealized_pnl(110.0) == pytest.approx(100.0)
    assert b.equity({"BTC": 110.0}) == pytest.approx(10_100.0)


def test_close_realizes_pnl():
    b = make_broker()
    b.open("ETH", "short", size_usd=2_000, leverage=1, mid_price=200.0)
    fill = b.close("ETH", mid_price=180.0)
    assert fill.realized_pnl == pytest.approx(200.0)  # short 10 units, +20/unit
    assert b.cash == pytest.approx(10_200.0)
    assert "ETH" not in b.positions
    assert len(b.closed_trades) == 1
    assert b.closed_trades[0].realized_pnl == pytest.approx(200.0)


def test_fees_and_slippage_are_charged():
    b = make_broker(fee_bps=10.0, slippage_bps=10.0)
    b.open("BTC", "long", size_usd=1_000, leverage=1, mid_price=100.0)
    pos = b.positions["BTC"]
    assert pos.entry_price == pytest.approx(100.10)  # 10bps slippage against us
    assert b.cash == pytest.approx(10_000 - 1_000 - 1.0)  # margin + 10bps fee


def test_insufficient_margin_raises():
    b = make_broker(starting_cash=100.0)
    with pytest.raises(InsufficientMargin):
        b.open("BTC", "long", size_usd=1_000, leverage=1, mid_price=100.0)


def test_stop_loss_triggers_on_mark():
    b = make_broker()
    b.open("SOL", "long", size_usd=1_000, leverage=1, mid_price=100.0, stop_loss=95.0)
    assert b.mark({"SOL": 96.0}) == []
    fills = b.mark({"SOL": 94.0})
    assert len(fills) == 1
    assert fills[0].reason == "stop_loss"
    assert "SOL" not in b.positions


def test_take_profit_triggers_for_short():
    b = make_broker()
    b.open("SOL", "short", size_usd=1_000, leverage=1, mid_price=100.0, take_profit=90.0)
    fills = b.mark({"SOL": 89.0})
    assert len(fills) == 1
    assert fills[0].reason == "take_profit"
    assert fills[0].realized_pnl == pytest.approx(110.0)


def test_state_round_trips(tmp_path):
    path = tmp_path / "state.json"
    b = make_broker(state_path=path)
    b.open("BTC", "long", size_usd=1_000, leverage=2, mid_price=100.0, thesis="test thesis")
    b2 = PaperBroker(starting_cash=999.0, state_path=path)  # starting_cash ignored when state exists
    assert b2.cash == pytest.approx(b.cash)
    assert b2.positions["BTC"].qty == pytest.approx(10.0)
    assert b2.positions["BTC"].thesis == "test thesis"
