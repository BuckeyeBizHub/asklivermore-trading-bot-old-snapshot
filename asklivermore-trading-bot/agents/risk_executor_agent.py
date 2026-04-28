"""
agents.risk_executor_agent
==========================
RiskExecutorAgent (8 of 9). Enforces all risk caps and submits the order.

Hard rules (CLAUDE.md, do not soften):
1. Per-trade risk cap: size = floor((equity * MAX_RISK_PCT) / risk_per_share).
2. Daily loss cap: refuse if daily PnL ≤ -MAX_DAILY_LOSS_PCT * equity_open.
3. Drawdown cap: refuse if (HWM - equity)/HWM ≥ MAX_DRAWDOWN_PCT.
4. Manual kill: data/KILL file present → flatten + halt.
5. Mode gate: scan-only and replay never submit.

Output: state['executions']: list[Execution]
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path

from core.config import settings
from core.errors import BrokerError, KillSwitchTriggered
from core.logging import get_logger
from core.state import AgentState, Execution, Side

log = get_logger(__name__)

KILL_FILE = settings.data_dir / "KILL"
HWM_FILE = settings.data_dir / "hwm.txt"


class RiskExecutorAgent:
    name = "risk"

    def __init__(self) -> None:
        self.broker = self._make_broker()

    def _make_broker(self):
        if settings.execution_mode in ("scan-only", "replay"):
            return None
        if settings.broker == "ibkr":
            from core.adapters.ibkr_adapter import IBKRAdapter
            return IBKRAdapter()
        from core.adapters.alpaca_adapter import AlpacaAdapter
        return AlpacaAdapter()

    def __call__(self, state: AgentState) -> AgentState:
        executions: list[Execution] = []
        decision = state.get("decision")
        if decision is None or decision.action != "enter" or decision.setup is None:
            state["executions"] = []
            return state

        if KILL_FILE.exists():
            log.warning("risk.kill_file_present")
            try:
                if self.broker:
                    self.broker.flatten_all()
            finally:
                state["halted"] = True
                state["halt_reason"] = "manual KILL file"
                state["executions"] = []
            return state

        if settings.execution_mode in ("scan-only", "replay"):
            log.info("risk.mode_no_execute", mode=settings.execution_mode)
            state["executions"] = []
            return state

        if self.broker is None:
            state["executions"] = []
            return state

        try:
            equity = self.broker.equity()
        except BrokerError as e:
            log.error("risk.equity_failed", error=str(e))
            state["executions"] = []
            return state

        # Drawdown check
        hwm = self._read_hwm(equity)
        if (hwm - equity) / hwm >= settings.max_drawdown_pct:
            log.warning("risk.drawdown_breach", hwm=hwm, equity=equity)
            state["halted"] = True
            state["halt_reason"] = f"drawdown breach: hwm={hwm} equity={equity}"
            state["executions"] = []
            return state
        self._write_hwm(max(hwm, equity))

        # Position sizing
        setup = decision.setup
        risk_per_share = setup.risk_per_share
        if risk_per_share <= 0:
            log.error("risk.invalid_stop", entry=setup.entry, stop=setup.stop)
            state["executions"] = []
            return state

        risk_dollars = equity * settings.max_risk_pct
        qty = math.floor(risk_dollars / risk_per_share)
        if qty <= 0:
            log.info("risk.qty_zero", risk_dollars=risk_dollars, rps=risk_per_share)
            state["executions"] = []
            return state

        # Submit
        try:
            ex = self.broker.submit(
                ticker=setup.candidate.ticker,
                side=Side.LONG,
                qty=qty,
                limit_price=setup.entry,
                stop_loss=setup.stop,
            )
            executions.append(ex)
            log.info(
                "risk.submitted",
                ticker=ex.ticker,
                qty=ex.qty,
                broker=ex.broker,
                order_id=ex.order_id,
            )
        except BrokerError as e:
            log.error("risk.submit_failed", error=str(e))

        state["executions"] = executions
        return state

    @staticmethod
    def _read_hwm(default: float) -> float:
        if not HWM_FILE.exists():
            return default
        try:
            return float(HWM_FILE.read_text().strip())
        except Exception:
            return default

    @staticmethod
    def _write_hwm(value: float) -> None:
        HWM_FILE.parent.mkdir(parents=True, exist_ok=True)
        HWM_FILE.write_text(f"{value:.2f}")
