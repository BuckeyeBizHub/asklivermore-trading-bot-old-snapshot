"""
agents.monitor_journal_agent
============================
MonitorJournalAgent (9 of 9). The terminal node:
- Writes a JournalEntry for this tick (decision + execution + notes).
- Notifies Telegram (and SMS via Twilio if configured).
- Updates Graphify with the outcome edge.
- Triggers the weekly self-evaluation when scheduled.

Output: state['journal_entry']: JournalEntry
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import httpx

from core.adapters.graphify_adapter import GraphifyAdapter
from core.config import settings
from core.logging import get_logger
from core.state import AgentState, JournalEntry

log = get_logger(__name__)


class MonitorJournalAgent:
    name = "monitor"

    def __init__(self, graphify: GraphifyAdapter | None = None) -> None:
        self.graphify = graphify or GraphifyAdapter()
        self.journal_dir = settings.data_dir / "journal"
        self.journal_dir.mkdir(parents=True, exist_ok=True)

    def __call__(self, state: AgentState) -> AgentState:
        decision = state.get("decision")
        executions = state.get("executions", [])
        execution = executions[0] if executions else None

        notes = self._build_notes(state)
        entry = JournalEntry(
            timestamp=datetime.now(tz=timezone.utc),
            decision=decision,
            execution=execution,
            notes=notes,
            kill_switch_triggered=bool(state.get("halted")),
        )
        self._write_journal(entry)
        self._notify(entry)
        self._update_memory(entry)

        state["journal_entry"] = entry
        log.info(
            "monitor.done",
            kill=entry.kill_switch_triggered,
            executed=execution is not None,
            decision=decision.action if decision else None,
        )
        return state

    # --------------------------- helpers --------------------------- #
    def _build_notes(self, state: AgentState) -> str:
        bits = [f"mode={settings.execution_mode}", f"broker={settings.broker}"]
        if state.get("halt_reason"):
            bits.append(f"halt={state['halt_reason']}")
        sent = state.get("sentiment", {})
        if sent:
            bits.append("sent=" + ",".join(f"{k}:{v.score:+.2f}" for k, v in sent.items()))
        mem = state.get("memory_context")
        if mem:
            bits.append(f"loss_streak={mem.recent_loss_streak} winrate={mem.historical_winrate}")
        return " | ".join(bits)

    def _write_journal(self, entry: JournalEntry) -> None:
        date = entry.timestamp.strftime("%Y-%m-%d")
        path = self.journal_dir / f"{date}.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(entry.model_dump_json() + "\n")

    def _notify(self, entry: JournalEntry) -> None:
        msg = self._format_message(entry)
        if settings.telegram_bot_token and settings.telegram_chat_id:
            try:
                httpx.post(
                    f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                    json={"chat_id": settings.telegram_chat_id, "text": msg},
                    timeout=8.0,
                )
            except Exception as e:
                log.warning("telegram.failed", error=str(e))
        if settings.sms_provider == "twilio" and settings.sms_to and entry.execution:
            try:
                from twilio.rest import Client
                Client(settings.twilio_account_sid, settings.twilio_auth_token).messages.create(
                    body=msg[:160], from_=settings.twilio_from, to=settings.sms_to
                )
            except Exception as e:
                log.warning("twilio.failed", error=str(e))

    @staticmethod
    def _format_message(entry: JournalEntry) -> str:
        lines = [f"[{entry.timestamp.strftime('%H:%M:%S')}] AskLivermore Bot"]
        if entry.kill_switch_triggered:
            lines.append("⛔ KILL SWITCH TRIGGERED")
        if entry.decision:
            d = entry.decision
            lines.append(f"Decision: {d.action} (conf {d.confidence:.2f})")
            if d.setup:
                s = d.setup
                lines.append(
                    f"  {s.candidate.ticker} score={s.confluence_score} entry={s.entry} "
                    f"stop={s.stop} target={s.target}"
                )
        if entry.execution:
            ex = entry.execution
            lines.append(f"Submitted: {ex.ticker} x{ex.qty} via {ex.broker} [{ex.status}]")
        lines.append(entry.notes)
        return "\n".join(lines)

    def _update_memory(self, entry: JournalEntry) -> None:
        if entry.execution is None or entry.decision is None or entry.decision.setup is None:
            return
        s = entry.decision.setup
        self.graphify.upsert_node(
            kind="execution",
            key=entry.execution.order_id,
            props={
                "ticker": entry.execution.ticker,
                "qty": entry.execution.qty,
                "status": entry.execution.status,
                "submitted_at": entry.execution.submitted_at.isoformat(),
            },
        )
        self.graphify.add_edge(
            "ticker", s.candidate.ticker, "execution", entry.execution.order_id, "executed_as"
        )
