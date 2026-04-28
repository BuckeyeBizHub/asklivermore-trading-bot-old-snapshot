"""
core.adapters.polygon_adapter
=============================
Polygon real-time websocket adapter. Yields raw aggregate-minute bars and
exposes `scan_top_movers()` that produces Candidate objects from current snapshot.

Falls back to a stub if no API key is configured.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import AsyncIterator

import httpx
import websockets

from core.config import settings
from core.errors import DataSourceError
from core.logging import get_logger
from core.state import Candidate

log = get_logger(__name__)


class PolygonAdapter:
    def __init__(self) -> None:
        self.api_key = settings.polygon_api_key
        self.ws_url = settings.polygon_websocket_url

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    async def stream_aggregates(self, tickers: list[str]) -> AsyncIterator[dict]:
        if not self.configured:
            log.warning("polygon.not_configured")
            return
        sub = "AM." + ",AM.".join(tickers)
        async for ws in websockets.connect(self.ws_url, ping_interval=20):
            try:
                await ws.send(json.dumps({"action": "auth", "params": self.api_key}))
                await ws.send(json.dumps({"action": "subscribe", "params": sub}))
                async for raw in ws:
                    for evt in json.loads(raw):
                        if evt.get("ev") == "AM":
                            yield evt
            except websockets.ConnectionClosed:
                log.warning("polygon.ws_reconnect")
                continue

    def scan_top_movers(self, limit: int = 25) -> list[Candidate]:
        """REST snapshot of top gainers as a synchronous fallback / warm-up."""
        if not self.configured:
            return []
        url = "https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/gainers"
        try:
            with httpx.Client(timeout=10.0) as c:
                r = c.get(url, params={"apiKey": self.api_key})
                r.raise_for_status()
                data = r.json()
        except (httpx.HTTPError, ValueError) as e:
            raise DataSourceError(f"polygon snapshot failed: {e}") from e

        out: list[Candidate] = []
        for t in (data.get("tickers") or [])[:limit]:
            sym = t.get("ticker")
            day = t.get("day", {}) or {}
            prev = t.get("prevDay", {}) or {}
            last = day.get("c") or t.get("lastTrade", {}).get("p") or 0.0
            vol = day.get("v") or 0
            avg_vol = prev.get("v") or 1
            rvol = float(vol) / float(avg_vol) if avg_vol else 1.0
            try:
                out.append(
                    Candidate(
                        ticker=sym,
                        last_price=float(last),
                        rvol=rvol,
                        rs_rating=50.0,  # Polygon does not provide RS; populated later
                        source="polygon",
                        captured_at=datetime.now(tz=timezone.utc),
                        raw=t,
                    )
                )
            except Exception as e:
                log.warning("polygon.candidate_skip", ticker=sym, error=str(e))
        return out
