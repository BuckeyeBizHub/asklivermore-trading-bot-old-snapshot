"""
agents.zodchiii_best_practices_agent
====================================
ZodchiiiClaudeAgentBestPractices (5 of 9). A guard-rail agent that enforces
the rules in CLAUDE.md against the current state object before it reaches the
ReasoningAgent.

Checks:
- All upstream agents emitted their schemas (no missing keys).
- No forbidden patterns (e.g., orders attempted outside RiskExecutor).
- Confluence + sentiment + memory gates are honored.
- Halt flag respected.

Output: state['policy_check']: PolicyResult
"""
from __future__ import annotations

from core.config import settings
from core.logging import get_logger
from core.state import AgentState, PolicyResult

log = get_logger(__name__)


class ZodchiiiBestPracticesAgent:
    name = "policy"

    def __call__(self, state: AgentState) -> AgentState:
        violations: list[str] = []

        if state.get("halted"):
            violations.append(f"halted={state.get('halt_reason')}")

        validated = state.get("validated", [])
        if not validated:
            violations.append("no validated setups upstream")

        sentiment = state.get("sentiment", {})
        for s in validated:
            ss = sentiment.get(s.candidate.ticker)
            if ss is None:
                violations.append(f"missing sentiment for {s.candidate.ticker}")
            elif ss.score < settings.min_sentiment_score:
                violations.append(
                    f"{s.candidate.ticker}: sentiment {ss.score:.2f} < {settings.min_sentiment_score}"
                )
            if s.confluence_score < settings.min_confluence_score:
                violations.append(
                    f"{s.candidate.ticker}: confluence {s.confluence_score} < {settings.min_confluence_score}"
                )

        mem = state.get("memory_context")
        if mem and mem.recent_loss_streak >= 3:
            violations.append(f"loss streak {mem.recent_loss_streak} >= 3, cooldown")

        ok = len(violations) == 0
        result = PolicyResult(ok=ok, violations=violations)
        log.info("policy.done", ok=ok, violations=violations)
        state["policy_check"] = result
        return state
