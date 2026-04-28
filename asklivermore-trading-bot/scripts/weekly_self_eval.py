"""
scripts/weekly_self_eval.py
===========================
Reads the past week of journal entries and asks the ReasoningAgent (Opus 4.7)
to propose adjustments to confluence weights. Writes proposals to
data/journal/proposed_changes/YYYY-WW.json. NEVER auto-applies.

Run weekly via cron, e.g. on Sunday 18:00 ET:
  0 18 * * 0  cd /opt/asklivermore-trading-bot && python -m scripts.weekly_self_eval
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from core.config import settings
from core.llm import call_structured
from core.logging import get_logger

log = get_logger(__name__)


class ProposedChange(BaseModel):
    component: str = Field(description="one of bull_flag_or_vcp / golden_pocket / rvol_ge_2 / rs_ge_80 / livermore_5_step")
    current_weight: int
    proposed_weight: int
    rationale: str
    supporting_trade_ids: list[str] = Field(default_factory=list)


class WeeklyReview(BaseModel):
    period_start: str
    period_end: str
    n_decisions: int
    n_executions: int
    win_rate: float | None = None
    proposed_changes: list[ProposedChange] = Field(default_factory=list)
    summary: str


_SYSTEM = """You are reviewing the trading bot's last 7 days of journal entries to find
miscalibrated confluence weights. Be conservative: propose a change only if you can
cite ≥3 supporting entries. Never propose lowering all weights at once. Output JSON
matching the WeeklyReview schema."""


def gather_journals(days: int = 7) -> list[dict]:
    journal_dir = settings.data_dir / "journal"
    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    out: list[dict] = []
    for jp in sorted(journal_dir.glob("*.jsonl")):
        try:
            d = datetime.strptime(jp.stem, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if d < cutoff:
            continue
        for line in jp.read_text().splitlines():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def main() -> None:
    entries = gather_journals(7)
    if not entries:
        log.info("weekly.no_entries")
        return
    user = (
        f"Total entries: {len(entries)}\n"
        f"<entries>\n{json.dumps(entries[:200])}\n</entries>\n"
        "Produce the WeeklyReview."
    )
    review = call_structured(
        schema=WeeklyReview,
        system=_SYSTEM,
        user=user,
        use_reasoning_model=True,
        max_tokens=2500,
    )
    out_dir = settings.data_dir / "journal" / "proposed_changes"
    out_dir.mkdir(parents=True, exist_ok=True)
    iso_year, iso_week, _ = datetime.now(tz=timezone.utc).isocalendar()
    out_path = out_dir / f"{iso_year}-W{iso_week:02d}.json"
    out_path.write_text(review.model_dump_json(indent=2))
    log.info("weekly.written", path=str(out_path), proposed=len(review.proposed_changes))


if __name__ == "__main__":
    main()
