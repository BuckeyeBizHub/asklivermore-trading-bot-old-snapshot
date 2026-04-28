"""
agents.confluence_validator_agent
=================================
ConfluenceValidatorAgent (2 of 9). Scores each Candidate against the AskLivermore
methodology: bull flag / VCP / Golden Pocket / RVOL / RS / Livermore 5-step.

Score is the count of components that pass (max 5). Only setups with score >=
settings.min_confluence_score advance.
"""
from __future__ import annotations

from pathlib import Path

import yaml

from core.config import settings
from core.llm import call_structured
from core.logging import get_logger
from core.state import AgentState, Candidate, PatternKind, PatternMatch, ValidatedSetup

log = get_logger(__name__)


_SYSTEM = """You are the Confluence Validator for an AskLivermore-style day-trading bot.
Given a single ticker candidate and current market context, evaluate:

1. Bull flag OR VCP (Minervini's Volatility Contraction Pattern) — does the chart show a clean
   consolidation after an impulsive move?
2. Golden Pocket — is price reacting to the 0.618-0.65 Fibonacci retracement of the prior leg?
3. RVOL — is relative volume >= 2.0x (strong participation)?
4. RS — is the relative-strength rating >= 80 (leader, not laggard)?
5. Livermore 5-step — does the move match Jesse Livermore's pivotal-point rules: clear pivot,
   line of least resistance, volume confirmation, no overhead supply, market in tone?

Return a JSON object that matches the schema. confluence_score = number of (1-5) that pass.
Be conservative: if you cannot tell from the data, score that component 0.
"""


def _load_patterns() -> dict:
    path = Path("knowledge/asklivermore_patterns.yaml")
    if not path.exists():
        return {}
    with path.open() as f:
        return yaml.safe_load(f) or {}


class ConfluenceValidatorAgent:
    name = "confluence"

    def __init__(self) -> None:
        self.patterns = _load_patterns()

    def __call__(self, state: AgentState) -> AgentState:
        validated: list[ValidatedSetup] = []
        for cand in state.get("candidates", []):
            try:
                setup = self._validate_one(cand)
                if setup is None:
                    continue
                if setup.confluence_score >= settings.min_confluence_score:
                    validated.append(setup)
                else:
                    log.info(
                        "confluence.rejected",
                        ticker=cand.ticker,
                        score=setup.confluence_score,
                    )
            except Exception as e:
                log.warning("confluence.error", ticker=cand.ticker, error=str(e))
        log.info("confluence.done", validated=len(validated))
        state["validated"] = validated
        return state

    def _validate_one(self, cand: Candidate) -> ValidatedSetup | None:
        user = (
            f"Ticker: {cand.ticker}\n"
            f"Last price: {cand.last_price}\n"
            f"RVOL (vs 30-day): {cand.rvol}\n"
            f"RS rating (0-100): {cand.rs_rating}\n"
            f"Source: {cand.source}\n"
            f"Pattern hint (if any): {cand.raw.get('pattern_hint')}\n"
            f"Notes: {cand.raw.get('note')}\n\n"
            "Canonical AskLivermore pattern library:\n"
            f"{self.patterns}\n\n"
            "Build a ValidatedSetup. The candidate object below should be echoed back unchanged.\n"
            f"<candidate>{cand.model_dump_json()}</candidate>"
        )
        return call_structured(
            schema=ValidatedSetup,
            system=_SYSTEM,
            user=user,
            use_reasoning_model=False,
            max_tokens=1200,
        )
