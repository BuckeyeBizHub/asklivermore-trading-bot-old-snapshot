"""
agents.reasoning_agent
======================
ReasoningAgent (7 of 9). Final decision-maker. Uses Claude Opus 4.7 to synthesize
all upstream signals (confluence, sentiment, memory, policy, peers) into a single
TradeDecision JSON.

Hard rule: returns action="skip" if policy_check.ok is False or no validated setup.
"""
from __future__ import annotations

from core.llm import call_structured
from core.logging import get_logger
from core.state import AgentState, TradeDecision

log = get_logger(__name__)


_SYSTEM = """You are the Reasoning Agent for an AskLivermore-style day-trading bot.
You receive structured outputs from 6 upstream agents. Your job is to decide:
- enter: open the trade now
- watch: keep monitoring, do not enter yet
- skip: discard this candidate

Hard rules (do not violate):
- If policy_check.ok is false → action MUST be "skip".
- If no validated setup is provided → action MUST be "skip".
- If sentiment is degraded AND memory is degraded → prefer "watch" over "enter".
- Confidence must reflect the agreement between confluence_score, sentiment, peer advice,
  and historical winrate. Be calibrated, not enthusiastic.

If you choose "enter", echo back the highest-scored ValidatedSetup as `setup`, set
`side=long` (this bot is long-only by design), and set `size_shares=null` (the
RiskExecutor sizes positions). Always provide a `reasoning` paragraph that names
which signals were decisive.

Return JSON matching the TradeDecision schema.
"""


class ReasoningAgent:
    name = "reasoning"

    def __call__(self, state: AgentState) -> AgentState:
        policy = state.get("policy_check")
        validated = state.get("validated", [])
        if (policy is not None and not policy.ok) or not validated:
            decision = TradeDecision(
                action="skip",
                reasoning=f"gate failed: policy={policy.violations if policy else 'missing'}, "
                          f"validated={len(validated)}",
                confidence=1.0,
            )
            state["decision"] = decision
            log.info("reasoning.skip", reason=decision.reasoning)
            return state

        focus = max(validated, key=lambda v: v.confluence_score)
        sent = state.get("sentiment", {}).get(focus.candidate.ticker)
        mem = state.get("memory_context")
        peers = state.get("peer_advice", [])

        user = (
            "<focus_setup>\n"
            f"{focus.model_dump_json(indent=2)}\n"
            "</focus_setup>\n\n"
            f"<sentiment>{sent.model_dump_json(indent=2) if sent else 'null'}</sentiment>\n\n"
            f"<memory>{mem.model_dump_json(indent=2) if mem else 'null'}</memory>\n\n"
            f"<policy>{policy.model_dump_json(indent=2) if policy else 'null'}</policy>\n\n"
            "<peers>\n"
            + "\n".join(p.model_dump_json() for p in peers)
            + "\n</peers>\n\n"
            "Produce the TradeDecision."
        )

        decision = call_structured(
            schema=TradeDecision,
            system=_SYSTEM,
            user=user,
            use_reasoning_model=True,
            max_tokens=1500,
        )
        log.info(
            "reasoning.done",
            action=decision.action,
            confidence=decision.confidence,
            ticker=decision.setup.candidate.ticker if decision.setup else None,
        )
        state["decision"] = decision
        return state
