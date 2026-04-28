"""
agents.peer_coordinator_agent
=============================
SoAinsightPeerCoordinator (6 of 9). Publishes the current focus setup to the
shared peer topic and fetches advice from sibling bot instances. Used by the
ReasoningAgent to incorporate distributed agreement signals.

Output: state['peer_advice']: list[PeerMessage]
"""
from __future__ import annotations

from core.adapters.peers_adapter import PeersAdapter
from core.logging import get_logger
from core.state import AgentState

log = get_logger(__name__)


class PeerCoordinatorAgent:
    name = "peers"

    def __init__(self, peers: PeersAdapter | None = None) -> None:
        self.peers = peers or PeersAdapter()

    def __call__(self, state: AgentState) -> AgentState:
        validated = state.get("validated", [])
        if validated:
            focus = max(validated, key=lambda v: v.confluence_score)
            self.peers.publish(
                content=(
                    f"focus={focus.candidate.ticker} "
                    f"score={focus.confluence_score} "
                    f"entry={focus.entry} stop={focus.stop} target={focus.target}"
                ),
                confidence=focus.confluence_score / 5.0,
            )
        advice = self.peers.fetch_recent(max_age_s=120)
        log.info("peers.done", n=len(advice))
        state["peer_advice"] = advice
        return state
