"""Market data sources.

Snapshot is the only currency between data sources and the rest of the agent,
so swapping live data for a replay (tests, offline dev) is a one-line config
change.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Protocol

import httpx

HYPERLIQUID_INFO_URL = "https://api.hyperliquid.xyz/info"


@dataclass
class AssetSnapshot:
    symbol: str
    mid_price: float
    mark_price: float
    funding_rate: float  # current hourly funding rate (as a fraction)
    open_interest: float  # in base units
    day_volume_usd: float
    prev_day_price: float

    @property
    def day_change_pct(self) -> float:
        if not self.prev_day_price:
            return 0.0
        return (self.mid_price - self.prev_day_price) / self.prev_day_price * 100


@dataclass
class MarketSnapshot:
    timestamp: float
    assets: dict[str, AssetSnapshot] = field(default_factory=dict)

    def to_prompt_dict(self) -> dict:
        return {
            "timestamp_utc": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(self.timestamp)),
            "assets": {
                sym: {
                    "mid_price": a.mid_price,
                    "mark_price": a.mark_price,
                    "funding_rate_hourly": a.funding_rate,
                    "open_interest": a.open_interest,
                    "24h_volume_usd": a.day_volume_usd,
                    "24h_change_pct": round(a.day_change_pct, 3),
                }
                for sym, a in self.assets.items()
            },
        }


class MarketDataSource(Protocol):
    def snapshot(self, symbols: list[str]) -> MarketSnapshot: ...


class HyperliquidDataSource:
    """Read-only public market data from Hyperliquid. No keys, no auth."""

    def __init__(self, timeout: float = 10.0):
        self._client = httpx.Client(timeout=timeout)

    def snapshot(self, symbols: list[str]) -> MarketSnapshot:
        resp = self._client.post(HYPERLIQUID_INFO_URL, json={"type": "metaAndAssetCtxs"})
        resp.raise_for_status()
        meta, ctxs = resp.json()
        wanted = set(symbols)
        snap = MarketSnapshot(timestamp=time.time())
        for asset_meta, ctx in zip(meta["universe"], ctxs):
            name = asset_meta["name"]
            if name not in wanted:
                continue
            mid = float(ctx.get("midPx") or ctx.get("markPx") or 0)
            snap.assets[name] = AssetSnapshot(
                symbol=name,
                mid_price=mid,
                mark_price=float(ctx.get("markPx") or mid),
                funding_rate=float(ctx.get("funding") or 0),
                open_interest=float(ctx.get("openInterest") or 0),
                day_volume_usd=float(ctx.get("dayNtlVlm") or 0),
                prev_day_price=float(ctx.get("prevDayPx") or 0),
            )
        missing = wanted - set(snap.assets)
        if missing:
            raise ValueError(f"Symbols not found on Hyperliquid: {sorted(missing)}")
        return snap


class ReplayDataSource:
    """Deterministic synthetic random walk. For tests and offline development."""

    BASE_PRICES = {"BTC": 100_000.0, "ETH": 3_500.0, "SOL": 150.0}

    def __init__(self, seed: int = 42):
        self._rng = random.Random(seed)
        self._prices: dict[str, float] = {}
        self._tick = 0

    def snapshot(self, symbols: list[str]) -> MarketSnapshot:
        self._tick += 1
        snap = MarketSnapshot(timestamp=time.time())
        for sym in symbols:
            price = self._prices.get(sym, self.BASE_PRICES.get(sym, 100.0))
            price *= 1 + self._rng.gauss(0, 0.002)
            self._prices[sym] = price
            snap.assets[sym] = AssetSnapshot(
                symbol=sym,
                mid_price=price,
                mark_price=price,
                funding_rate=self._rng.gauss(0.00001, 0.00002),
                open_interest=self._rng.uniform(1_000, 50_000),
                day_volume_usd=self._rng.uniform(1e7, 5e8),
                prev_day_price=price * (1 - self._rng.gauss(0, 0.01)),
            )
        return snap


def make_data_source(kind: str) -> MarketDataSource:
    if kind == "hyperliquid":
        return HyperliquidDataSource()
    if kind == "replay":
        return ReplayDataSource()
    raise ValueError(f"Unknown data source: {kind!r} (expected 'hyperliquid' or 'replay')")
