"""Tests for the Zodchiii policy gate."""
from __future__ import annotations

from datetime import datetime, timezone

from agents.zodchiii_best_practices_agent import ZodchiiiBestPracticesAgent
from core.state import (
    AgentState,
    Candidate,
    MemoryContext,
    PatternMatch,
    PatternKind,
    SentimentScore,
    ValidatedSetup,
)


def _setup(score: int = 4) -> ValidatedSetup:
    c = Candidate(
        ticker="AAPL",
        last_price=190,
        rvol=3.0,
        rs_rating=88,
        source="polygon",
        captured_at=datetime.now(tz=timezone.utc),
    )
    return ValidatedSetup(
        candidate=c,
        patterns=[PatternMatch(kind=PatternKind.BULL_FLAG, confidence=0.8)],
        confluence_score=score,
        livermore_step_passed=True,
        entry=190.5,
        stop=188.0,
        target=200.0,
        rationale="ok",
    )


def test_policy_passes_with_clean_inputs() -> None:
    s: AgentState = {
        "validated": [_setup(4)],
        "sentiment": {"AAPL": SentimentScore(score=0.4, volume=20, sources=["x"])},
        "memory_context": MemoryContext(recent_loss_streak=0),
    }
    out = ZodchiiiBestPracticesAgent()(s)
    assert out["policy_check"].ok is True


def test_policy_blocks_low_confluence() -> None:
    s: AgentState = {
        "validated": [_setup(2)],
        "sentiment": {"AAPL": SentimentScore(score=0.5, volume=10, sources=[])},
        "memory_context": MemoryContext(recent_loss_streak=0),
    }
    out = ZodchiiiBestPracticesAgent()(s)
    assert out["policy_check"].ok is False
    assert any("confluence" in v for v in out["policy_check"].violations)


def test_policy_blocks_negative_sentiment() -> None:
    s: AgentState = {
        "validated": [_setup(5)],
        "sentiment": {"AAPL": SentimentScore(score=-0.3, volume=5, sources=[])},
        "memory_context": MemoryContext(recent_loss_streak=0),
    }
    out = ZodchiiiBestPracticesAgent()(s)
    assert out["policy_check"].ok is False
    assert any("sentiment" in v for v in out["policy_check"].violations)


def test_policy_blocks_loss_streak() -> None:
    s: AgentState = {
        "validated": [_setup(5)],
        "sentiment": {"AAPL": SentimentScore(score=0.4, volume=10, sources=[])},
        "memory_context": MemoryContext(recent_loss_streak=3),
    }
    out = ZodchiiiBestPracticesAgent()(s)
    assert out["policy_check"].ok is False
    assert any("loss streak" in v for v in out["policy_check"].violations)
