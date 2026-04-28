"""
core.graph
==========
Wires the 9 agents into a LangGraph StateGraph with a self-evaluation feedback edge.

Order:
  scanner → confluence → social → memory → policy → peers → reasoning → risk → monitor
                                                                                  │
                                                          self-eval feedback ◄────┘
"""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from agents.confluence_validator_agent import ConfluenceValidatorAgent
from agents.memory_graph_agent import MemoryGraphAgent
from agents.monitor_journal_agent import MonitorJournalAgent
from agents.peer_coordinator_agent import PeerCoordinatorAgent
from agents.reasoning_agent import ReasoningAgent
from agents.risk_executor_agent import RiskExecutorAgent
from agents.scanner_agent import ScannerAgent
from agents.social_sentiment_agent import SocialSentimentAgent
from agents.zodchiii_best_practices_agent import ZodchiiiBestPracticesAgent
from core.logging import get_logger
from core.state import AgentState

log = get_logger(__name__)


def build_graph():
    g: StateGraph = StateGraph(AgentState)

    g.add_node("scanner", ScannerAgent())
    g.add_node("confluence", ConfluenceValidatorAgent())
    g.add_node("social", SocialSentimentAgent())
    g.add_node("memory", MemoryGraphAgent())
    g.add_node("policy", ZodchiiiBestPracticesAgent())
    g.add_node("peers", PeerCoordinatorAgent())
    g.add_node("reasoning", ReasoningAgent())
    g.add_node("risk", RiskExecutorAgent())
    g.add_node("monitor", MonitorJournalAgent())

    g.set_entry_point("scanner")
    g.add_edge("scanner", "confluence")
    g.add_edge("confluence", "social")
    g.add_edge("social", "memory")
    g.add_edge("memory", "policy")
    g.add_edge("policy", "peers")
    g.add_edge("peers", "reasoning")
    g.add_edge("reasoning", "risk")
    g.add_edge("risk", "monitor")
    g.add_edge("monitor", END)

    return g.compile()
