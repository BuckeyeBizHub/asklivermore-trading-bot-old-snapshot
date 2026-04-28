"""
agents.scanner_agent
====================
ScannerAgent (1 of 9). Produces a list of `Candidate` tickers each tick from:
- Polygon REST snapshot of top movers (real-time WS available for live mode)
- CSV imports dropped into data/csv_imports/
- Optional public-apis fallbacks if Polygon is not configured

Output: state['candidates']: list[Candidate]
"""
from __future__ import annotations

from core.adapters.polygon_adapter import PolygonAdapter
from core.csv_ingest import ingest_directory
from core.logging import get_logger
from core.state import AgentState, Candidate

log = get_logger(__name__)


class ScannerAgent:
    name = "scanner"

    def __init__(self, polygon: PolygonAdapter | None = None) -> None:
        self.polygon = polygon or PolygonAdapter()

    def __call__(self, state: AgentState) -> AgentState:
        candidates: list[Candidate] = []

        # 1) Polygon top movers
        try:
            if self.polygon.configured:
                candidates.extend(self.polygon.scan_top_movers(limit=25))
        except Exception as e:
            log.warning("scanner.polygon_failed", error=str(e))

        # 2) CSV imports (manual asklivermore.com exports)
        try:
            candidates.extend(ingest_directory())
        except Exception as e:
            log.warning("scanner.csv_failed", error=str(e))

        # de-dup by ticker, keep highest rvol
        by_ticker: dict[str, Candidate] = {}
        for c in candidates:
            existing = by_ticker.get(c.ticker)
            if existing is None or c.rvol > existing.rvol:
                by_ticker[c.ticker] = c

        out = list(by_ticker.values())
        log.info("scanner.done", count=len(out))
        state["candidates"] = out
        return state
