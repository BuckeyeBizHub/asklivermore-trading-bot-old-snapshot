"""
core.state
==========
Typed state contracts for the LangGraph pipeline.
Every agent reads and writes this object; nothing else is shared.
"""
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, TypedDict

from pydantic import BaseModel, Field, field_validator


# ------------------------------ enums ------------------------------ #
class Side(StrEnum):
    LONG = "long"
    SHORT = "short"


class PatternKind(StrEnum):
    BULL_FLAG = "bull_flag"
    VCP = "vcp"
    GOLDEN_POCKET = "golden_pocket"
    LIVERMORE_5_STEP = "livermore_5_step"


# ------------------------------ models ------------------------------ #
class Candidate(BaseModel):
    """A ticker that the scanner believes is worth deeper analysis."""

    ticker: str
    last_price: float
    rvol: float = Field(description="Relative volume vs 30-day avg")
    rs_rating: float = Field(description="Relative strength 0-100")
    source: Literal["polygon", "csv", "fallback"]
    captured_at: datetime
    raw: dict = Field(default_factory=dict)

    @field_validator("ticker")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper().strip()


class PatternMatch(BaseModel):
    kind: PatternKind
    confidence: float = Field(ge=0, le=1)
    notes: str = ""


class ValidatedSetup(BaseModel):
    """Output of ConfluenceValidatorAgent."""

    candidate: Candidate
    patterns: list[PatternMatch]
    confluence_score: int = Field(ge=0, le=5)
    livermore_step_passed: bool
    entry: float
    stop: float
    target: float
    rationale: str

    @property
    def risk_per_share(self) -> float:
        return abs(self.entry - self.stop)


class SentimentScore(BaseModel):
    score: float = Field(ge=-1, le=1)
    volume: int = Field(ge=0, description="number of mentions sampled")
    sources: list[str] = Field(default_factory=list)
    summary: str = ""
    degraded: bool = False


class MemoryContext(BaseModel):
    recent_loss_streak: int = 0
    historical_winrate: float | None = None
    similar_setups: list[dict] = Field(default_factory=list)
    notes: str = ""
    degraded: bool = False


class PolicyResult(BaseModel):
    ok: bool
    violations: list[str] = Field(default_factory=list)


class PeerMessage(BaseModel):
    from_peer: str
    content: str
    confidence: float = Field(ge=0, le=1, default=0.5)


class TradeDecision(BaseModel):
    action: Literal["enter", "skip", "watch"]
    side: Side | None = None
    setup: ValidatedSetup | None = None
    size_shares: int | None = None
    reasoning: str
    confidence: float = Field(ge=0, le=1)


class Execution(BaseModel):
    ticker: str
    side: Side
    qty: int
    avg_fill: float | None = None
    order_id: str
    status: Literal["submitted", "filled", "rejected", "cancelled"]
    submitted_at: datetime
    broker: Literal["alpaca", "ibkr", "paper-stub"]


class JournalEntry(BaseModel):
    timestamp: datetime
    decision: TradeDecision | None
    execution: Execution | None
    notes: str
    kill_switch_triggered: bool = False


# ------------------------------ graph state ------------------------------ #
class AgentState(TypedDict, total=False):
    """The single object that flows through every LangGraph node."""

    run_id: str
    started_at: datetime

    # produced incrementally:
    candidates: list[Candidate]
    validated: list[ValidatedSetup]
    sentiment: dict[str, SentimentScore]
    memory_context: MemoryContext
    policy_check: PolicyResult
    peer_advice: list[PeerMessage]
    decision: TradeDecision
    executions: list[Execution]
    journal_entry: JournalEntry

    # control:
    halted: bool
    halt_reason: str
    errors: Annotated[list[str], "append-only error log"]
