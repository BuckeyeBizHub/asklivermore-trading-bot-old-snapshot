"""
core.adapters.ibkr_adapter
==========================
IBKR adapter via ib_insync. Connects to a running IB Gateway / TWS.

Note: ib_insync is sync-by-default; we run blocking calls. The graph is fine
with this because RiskExecutorAgent is a single-shot node per candidate.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ib_insync import IB, LimitOrder, Stock

from core.config import settings
from core.errors import BrokerError
from core.logging import get_logger
from core.state import Execution, Side

log = get_logger(__name__)


class IBKRAdapter:
    def __init__(self) -> None:
        self.ib = IB()

    def connect(self) -> None:
        if self.ib.isConnected():
            return
        try:
            self.ib.connect(
                host=settings.ibkr_host,
                port=settings.ibkr_port,
                clientId=settings.ibkr_client_id,
                timeout=10,
            )
        except Exception as e:
            raise BrokerError(f"ibkr connect failed: {e}") from e

    def equity(self) -> float:
        self.connect()
        try:
            summary = self.ib.accountSummary(settings.ibkr_account or "")
            for row in summary:
                if row.tag == "NetLiquidation":
                    return float(row.value)
            raise BrokerError("ibkr: NetLiquidation not in account summary")
        except Exception as e:
            raise BrokerError(f"ibkr equity fetch failed: {e}") from e

    def submit(
        self,
        *,
        ticker: str,
        side: Side,
        qty: int,
        limit_price: float,
        stop_loss: float,
    ) -> Execution:
        self.connect()
        try:
            contract = Stock(ticker, "SMART", "USD")
            self.ib.qualifyContracts(contract)
            action = "BUY" if side == Side.LONG else "SELL"
            order = LimitOrder(action=action, totalQuantity=qty, lmtPrice=round(limit_price, 2))
            trade = self.ib.placeOrder(contract, order)
            self.ib.sleep(1)  # let the order register
            return Execution(
                ticker=ticker,
                side=side,
                qty=qty,
                avg_fill=trade.orderStatus.avgFillPrice or None,
                order_id=str(trade.order.orderId),
                status=trade.orderStatus.status.lower() or "submitted",  # type: ignore[arg-type]
                submitted_at=datetime.now(tz=timezone.utc),
                broker="ibkr",
            )
        except Exception as e:
            raise BrokerError(f"ibkr submit failed: {e}") from e

    def flatten_all(self) -> None:
        self.connect()
        try:
            for pos in self.ib.positions():
                contract = pos.contract
                qty = int(abs(pos.position))
                if qty == 0:
                    continue
                action = "SELL" if pos.position > 0 else "BUY"
                order = LimitOrder(action=action, totalQuantity=qty, lmtPrice=0.0)  # market-ish
                self.ib.placeOrder(contract, order)
            log.warning("ibkr.flatten_all")
        except Exception as e:
            raise BrokerError(f"ibkr flatten failed: {e}") from e
