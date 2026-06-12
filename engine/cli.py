"""CLI: run the loop, inspect state, and chat with the agent about its decisions.

  engine run [--once] [--interval 300]
  engine status
  engine log [-n 20]
  engine why
  engine chat "why did you short ETH?"
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from .agent import Agent
from .broker import PaperBroker
from .config import Config
from .decision import ClaudeDecisionEngine, build_chat_reply
from .journal import Journal
from .marketdata import make_data_source


def _build_agent(config: Config) -> Agent:
    return Agent(
        config=config,
        data=make_data_source(config.data_source),
        broker=PaperBroker(config.starting_cash, config.fee_bps, config.slippage_bps,
                           state_path=config.broker_state_path),
        engine=ClaudeDecisionEngine(config.model),
        journal=Journal(config.journal_path),
    )


def cmd_run(config: Config, args: argparse.Namespace) -> None:
    agent = _build_agent(config)
    print(f"engine: paper trading {config.symbols} | data={config.data_source} | model={config.model}")
    print(f"engine: limits — max ${config.max_position_usd:.0f}/position, {config.max_leverage:.0f}x, "
          f"{config.max_open_positions} positions, {config.daily_loss_limit_pct:.0f}% daily loss kill-switch")
    while True:
        result = agent.run_cycle()
        print(f"\n[{time.strftime('%H:%M:%S')}] equity ${result.equity:,.2f} "
              f"| confidence {result.decision.confidence:.2f}")
        print(f"  {result.decision.assessment}")
        for fill in result.triggered_stops:
            print(f"  ! {fill['reason']} hit on {fill['symbol']} @ {fill['price']:.4f} "
                  f"(pnl {fill['realized_pnl']:+.2f})")
        for ex in result.executed:
            print(f"  -> {ex['action']} {ex['symbol']} @ {ex['price']:.4f}  ({ex['thesis'][:120]})")
        for rej in result.rejected:
            print(f"  x  rejected {rej['order']['action']} {rej['order']['symbol']}: "
                  f"{rej['rejected_because']}")
        if not result.decision.orders:
            print("  (holding — no orders this cycle)")
        if args.once:
            break
        time.sleep(args.interval)


def cmd_status(config: Config, _args: argparse.Namespace) -> None:
    broker = PaperBroker(config.starting_cash, state_path=config.broker_state_path)
    prices = {}
    try:
        snap = make_data_source(config.data_source).snapshot(config.symbols)
        prices = {s: a.mid_price for s, a in snap.assets.items()}
    except Exception as exc:  # offline: fall back to entry-price marks
        print(f"(could not fetch live prices: {exc})", file=sys.stderr)
    print(f"cash:   ${broker.cash:,.2f}")
    print(f"equity: ${broker.equity(prices):,.2f}")
    if not broker.positions:
        print("positions: none")
    for p in broker.positions.values():
        mark = prices.get(p.symbol, p.entry_price)
        print(f"  {p.symbol} {p.side} {p.qty:.6g} @ {p.entry_price:.4f} "
              f"({p.leverage:.0f}x, stop {p.stop_loss}, tp {p.take_profit}) "
              f"upnl {p.unrealized_pnl(mark):+.2f}")
    closed = broker.closed_trades
    if closed:
        total = sum(t.realized_pnl for t in closed)
        wins = sum(1 for t in closed if t.realized_pnl > 0)
        print(f"closed trades: {len(closed)} ({wins} wins), realized pnl {total:+.2f}")


def cmd_log(config: Config, args: argparse.Namespace) -> None:
    for e in Journal(config.journal_path).entries(limit=args.n):
        ts = time.strftime("%m-%d %H:%M:%S", time.gmtime(e["ts"]))
        if e["kind"] == "decision":
            print(f"{ts} DECIDE conf={e.get('confidence', 0):.2f} {e.get('assessment', '')[:140]}")
            for ex in e.get("executed", []):
                print(f"{' ' * 17}-> {ex['action']} {ex['symbol']} @ {ex['price']:.4f}")
        elif e["kind"] == "fill":
            pnl = e.get("realized_pnl")
            pnl_s = f" pnl {pnl:+.2f}" if pnl is not None else ""
            print(f"{ts} FILL   {e.get('side', e.get('action', ''))} {e['symbol']} "
                  f"@ {e['price']:.4f}{pnl_s} [{e.get('reason', 'agent')}]")
        else:
            print(f"{ts} {e['kind'].upper()} {json.dumps({k: v for k, v in e.items() if k not in ('ts', 'kind')})[:160]}")


def cmd_why(config: Config, _args: argparse.Namespace) -> None:
    last = Journal(config.journal_path).last_decision()
    if last is None:
        print("No decisions logged yet. Run `engine run --once` first.")
        return
    print(f"At {time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(last['ts']))} UTC "
          f"(confidence {last.get('confidence', 0):.2f}):\n")
    print(last.get("assessment", ""))
    for o in last.get("orders", []):
        print(f"\n{o['action']} {o['symbol']}"
              + (f" ${o['size_usd']:.0f} @ {o.get('leverage', 1)}x" if o.get("size_usd") else ""))
        print(f"  thesis: {o['thesis']}")
    for r in last.get("rejected", []):
        print(f"\nrejected: {r['order']['action']} {r['order']['symbol']} — {r['rejected_because']}")
    print(f"\nprices at decision time: {json.dumps(last.get('prices', {}))}")


def cmd_chat(config: Config, args: argparse.Namespace) -> None:
    journal = Journal(config.journal_path)
    broker = PaperBroker(config.starting_cash, state_path=config.broker_state_path)
    positions = [{
        "symbol": p.symbol, "side": p.side, "entry_price": p.entry_price,
        "stop_loss": p.stop_loss, "take_profit": p.take_profit, "thesis": p.thesis,
    } for p in broker.positions.values()]
    build_chat_reply(
        model=config.model,
        strategy=config.strategy_path.read_text() if config.strategy_path.exists() else "(no strategy file)",
        journal_entries=journal.entries(limit=40),
        positions=positions,
        question=args.question,
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="engine", description="Paper-trading LLM agent")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="run the agent loop")
    p_run.add_argument("--once", action="store_true", help="run a single cycle and exit")
    p_run.add_argument("--interval", type=int, default=300, help="seconds between cycles")

    sub.add_parser("status", help="account, positions, pnl")

    p_log = sub.add_parser("log", help="tail the decision log")
    p_log.add_argument("-n", type=int, default=20)

    sub.add_parser("why", help="explain the most recent decision")

    p_chat = sub.add_parser("chat", help="ask the agent about its decisions")
    p_chat.add_argument("question")

    args = parser.parse_args(argv)
    config = Config()
    {
        "run": cmd_run,
        "status": cmd_status,
        "log": cmd_log,
        "why": cmd_why,
        "chat": cmd_chat,
    }[args.command](config, args)


if __name__ == "__main__":
    main()
