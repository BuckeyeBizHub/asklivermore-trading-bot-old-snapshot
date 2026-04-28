"""Sanity tests for state contracts."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from core.state import Candidate, ValidatedSetup, PatternMatch, PatternKind


def test_candidate_uppercases_ticker():
    c = Candidate(
        ticker="aapl",
        last_price=190.0,
        rvol=2.1,
        rs_rating=85,
        source="polygon",
        captured_at=datetime.now(tz=timezone.utc),
    )
    assert c.ticker == "AAPL"


def test_validated_setup_risk_per_share():
    c = Candidate(
        ticker="NVDA",
        last_price=100.0,
        rvol=3.0,
        rs_rating=92,
        source="polygon",
        captured_at=datetime.now(tz=timezone.utc),
    )
    s = ValidatedSetup(
        candidate=c,
        patterns=[PatternMatch(kind=PatternKind.BULL_FLAG, confidence=0.8)],
        confluence_score=4,
        livermore_step_passed=True,
        entry=100.5,
        stop=98.0,
        target=110.0,
        rationale="clean flag, RVOL 3x, RS 92",
    )
    assert s.risk_per_share == pytest.approx(2.5)


def test_confluence_score_bounds():
    c = Candidate(
        ticker="X",
        last_price=10,
        rvol=1,
        rs_rating=50,
        source="polygon",
        captured_at=datetime.now(tz=timezone.utc),
    )
    with pytest.raises(ValidationError):
        ValidatedSetup(
            candidate=c,
            patterns=[],
            confluence_score=99,  # out of range
            livermore_step_passed=False,
            entry=10,
            stop=9,
            target=12,
            rationale="x",
        )
