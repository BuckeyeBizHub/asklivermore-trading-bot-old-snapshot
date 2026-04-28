"""
agents.social_sentiment_agent
=============================
SocialSentimentAgent (3 of 9). For each validated setup, query the
charlie947/social-media-skills package (with MarketAux fallback) for current
social/news sentiment.

Output: state['sentiment']: dict[ticker, SentimentScore]
"""
from __future__ import annotations

from core.adapters.social_skill_adapter import SocialSkillAdapter
from core.logging import get_logger
from core.state import AgentState, SentimentScore

log = get_logger(__name__)


class SocialSentimentAgent:
    name = "social"

    def __init__(self, adapter: SocialSkillAdapter | None = None) -> None:
        self.adapter = adapter or SocialSkillAdapter()

    def __call__(self, state: AgentState) -> AgentState:
        scores: dict[str, SentimentScore] = {}
        for setup in state.get("validated", []):
            t = setup.candidate.ticker
            if t in scores:
                continue
            try:
                scores[t] = self.adapter.score(t)
            except Exception as e:
                log.warning("social.error", ticker=t, error=str(e))
                scores[t] = SentimentScore(
                    score=0.0, volume=0, sources=[], summary=f"error:{e}", degraded=True
                )
        log.info("social.done", n=len(scores))
        state["sentiment"] = scores
        return state
