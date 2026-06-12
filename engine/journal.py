"""The journal: every decision, fill, and error, timestamped, in plain JSONL.

This is the transparency layer — `engine log` and `engine why` read from it,
and the decision engine feeds recent entries and past-trade outcomes back into
the model so it can learn from what worked.
"""

from __future__ import annotations

import json
import time
from pathlib import Path


class Journal:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, kind: str, payload: dict) -> dict:
        entry = {"ts": time.time(), "kind": kind, **payload}
        with self.path.open("a") as f:
            f.write(json.dumps(entry) + "\n")
        return entry

    def entries(self, limit: int | None = None, kind: str | None = None) -> list[dict]:
        if not self.path.exists():
            return []
        out = []
        with self.path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                if kind is None or entry.get("kind") == kind:
                    out.append(entry)
        return out[-limit:] if limit else out

    def last_decision(self) -> dict | None:
        decisions = self.entries(limit=1, kind="decision")
        return decisions[0] if decisions else None

    def recent_for_prompt(self, limit: int = 10) -> list[dict]:
        """Compact recent history for the decision prompt."""
        out = []
        for e in self.entries(limit=limit):
            compact = {"when": _ago(e["ts"]), "kind": e["kind"]}
            if e["kind"] == "decision":
                compact["assessment"] = e.get("assessment", "")[:300]
                compact["orders"] = e.get("orders", [])
            elif e["kind"] == "fill":
                compact.update({k: e.get(k) for k in ("symbol", "side", "price", "realized_pnl", "reason")})
            out.append(compact)
        return out


def trade_memory(closed_trades: list, symbol: str | None = None, limit: int = 8) -> list[dict]:
    """Outcomes of past closed trades, most recent first — the agent's memory."""
    trades = [t for t in closed_trades if symbol is None or t.symbol == symbol]
    out = []
    for t in trades[-limit:][::-1]:
        out.append({
            "symbol": t.symbol,
            "side": t.side,
            "entry": round(t.entry_price, 6),
            "exit": round(t.exit_price, 6),
            "pnl_usd": round(t.realized_pnl, 2),
            "exit_reason": t.exit_reason,
            "held_minutes": round((t.closed_at - t.opened_at) / 60, 1),
            "thesis": t.thesis[:200],
        })
    return out


def _ago(ts: float) -> str:
    delta = max(0, time.time() - ts)
    if delta < 90:
        return f"{int(delta)}s ago"
    if delta < 90 * 60:
        return f"{int(delta / 60)}m ago"
    return f"{delta / 3600:.1f}h ago"
