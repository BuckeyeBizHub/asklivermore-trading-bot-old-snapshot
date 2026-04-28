"""
core.adapters.social_skill_adapter
==================================
Wraps the charlie947/social-media-skills package plus optional MarketAux/Styvio
enrichment. Public API: `score(ticker) -> SentimentScore`.

If the skill repo isn't installed at EXTERNAL_PATH_SOCIAL_SKILLS, falls back to
MarketAux (if key) and finally to a neutral degraded score.
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import datetime
from pathlib import Path

import httpx

from core.config import settings
from core.logging import get_logger
from core.state import SentimentScore

log = get_logger(__name__)


class SocialSkillAdapter:
    def __init__(self) -> None:
        self._skill = self._try_load_skill()

    def _try_load_skill(self):
        path = settings.external_path_social_skills
        if not Path(path).exists():
            log.warning("social_skills.not_installed", path=str(path))
            return None
        # The skill ships a python module; we add it to sys.path and import.
        skill_pkg = Path(path) / "src"
        if str(skill_pkg) not in sys.path:
            sys.path.insert(0, str(skill_pkg))
        try:
            spec = importlib.util.find_spec("social_media_skills")
            if spec is None:
                return None
            return importlib.import_module("social_media_skills")
        except Exception as e:
            log.warning("social_skills.import_failed", error=str(e))
            return None

    def score(self, ticker: str) -> SentimentScore:
        # 1) primary: charlie947 skill
        if self._skill is not None:
            try:
                result = self._skill.analyze_ticker(ticker)  # type: ignore[attr-defined]
                return SentimentScore(
                    score=float(result.get("score", 0.0)),
                    volume=int(result.get("volume", 0)),
                    sources=list(result.get("sources", [])),
                    summary=str(result.get("summary", "")),
                    degraded=False,
                )
            except Exception as e:
                log.warning("social_skills.call_failed", ticker=ticker, error=str(e))
        # 2) fallback: MarketAux
        if settings.marketaux_api_key:
            try:
                return self._marketaux_fallback(ticker)
            except Exception as e:
                log.warning("marketaux.fallback_failed", ticker=ticker, error=str(e))
        # 3) degraded: neutral
        log.info("social.degraded_neutral", ticker=ticker)
        return SentimentScore(score=0.0, volume=0, sources=[], summary="degraded", degraded=True)

    def _marketaux_fallback(self, ticker: str) -> SentimentScore:
        url = "https://api.marketaux.com/v1/news/all"
        params = {
            "symbols": ticker,
            "filter_entities": "true",
            "language": "en",
            "limit": 10,
            "api_token": settings.marketaux_api_key,
        }
        with httpx.Client(timeout=8.0) as c:
            r = c.get(url, params=params)
            r.raise_for_status()
            data = r.json()
        articles = data.get("data", [])
        if not articles:
            return SentimentScore(score=0.0, volume=0, sources=[], summary="no news", degraded=True)
        scores = []
        sources = []
        for a in articles:
            for ent in a.get("entities", []):
                if ent.get("symbol") == ticker and ent.get("sentiment_score") is not None:
                    scores.append(float(ent["sentiment_score"]))
            sources.append(a.get("source", ""))
        avg = sum(scores) / len(scores) if scores else 0.0
        return SentimentScore(
            score=max(-1.0, min(1.0, avg)),
            volume=len(articles),
            sources=list({s for s in sources if s})[:5],
            summary=f"marketaux:{len(articles)} articles, avg={avg:.2f}",
            degraded=False,
        )
