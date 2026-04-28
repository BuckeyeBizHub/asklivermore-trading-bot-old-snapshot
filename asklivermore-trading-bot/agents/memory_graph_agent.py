"""
agents.memory_graph_agent
=========================
MemoryGraphAgent (4 of 9). Reads relevant history from Graphify for the current
candidates and writes back the latest scan as nodes/edges. Also surfaces the
recent loss streak per ticker for the confluence gate.

Output: state['memory_context']: MemoryContext
"""
from __future__ import annotations

from core.adapters.graphify_adapter import GraphifyAdapter
from core.logging import get_logger
from core.state import AgentState, MemoryContext

log = get_logger(__name__)


class MemoryGraphAgent:
    name = "memory"

    def __init__(self, graphify: GraphifyAdapter | None = None) -> None:
        self.graphify = graphify or GraphifyAdapter()

    def __call__(self, state: AgentState) -> AgentState:
        validated = state.get("validated", [])
        if not validated:
            state["memory_context"] = MemoryContext()
            return state

        # Pick the top-scored ticker as the focus for memory context (single trade per tick).
        focus = max(validated, key=lambda v: v.confluence_score)
        ticker = focus.candidate.ticker

        history = self.graphify.query_ticker_history(ticker, limit=25)
        loss_streak = self._loss_streak(history)
        winrate = self._winrate(history)

        # Persist this scan.
        self.graphify.upsert_node(
            kind="setup",
            key=f"{ticker}:{focus.candidate.captured_at.isoformat()}",
            props={
                "ticker": ticker,
                "score": focus.confluence_score,
                "patterns": [p.kind.value for p in focus.patterns],
                "entry": focus.entry,
                "stop": focus.stop,
                "target": focus.target,
            },
        )
        self.graphify.add_edge(
            "ticker", ticker, "setup",
            f"{ticker}:{focus.candidate.captured_at.isoformat()}",
            "had_setup",
        )

        ctx = MemoryContext(
            recent_loss_streak=loss_streak,
            historical_winrate=winrate,
            similar_setups=history[:5],
            notes=f"focus={ticker}",
            degraded=self.graphify.degraded,
        )
        log.info(
            "memory.done", ticker=ticker, loss_streak=loss_streak, winrate=winrate, degraded=ctx.degraded
        )
        state["memory_context"] = ctx
        return state

    @staticmethod
    def _loss_streak(history: list[dict]) -> int:
        streak = 0
        for h in history:
            outcome = h.get("props", {}).get("outcome")
            if outcome == "loss":
                streak += 1
            else:
                break
        return streak

    @staticmethod
    def _winrate(history: list[dict]) -> float | None:
        if not history:
            return None
        wins = sum(1 for h in history if h.get("props", {}).get("outcome") == "win")
        total = sum(1 for h in history if h.get("props", {}).get("outcome") in ("win", "loss"))
        return wins / total if total else None
