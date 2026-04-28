"""
core.adapters.alpaca_adapter
============================
Alpaca paper or live trading adapter. Used by RiskExecutorAgent.
"""
from __future__ import annotations

from datetime import datetime, timezone

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import LimitOrderRequest, StopLossRequest

from core.config import settings
from core.errors import BrokerError
from core.logging import get_logger
from core.state import Execution, Side

log = get_logger(__name__)


class AlpacaAdapter:
    def __init__(self) -> None:
        paper = "paper" in settings.alpaca_base_url
        self.client = TradingClient(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_api_secret,
            paper=paper,
        )

    def equity(self) -> float:
        try:
            acct = self.client.get_account()
            return float(acct.equity)
        except Exception as e:
            raise BrokerError(f"alpaca account fetch failed: {e}") from e

    def submit(
        self,
        *,
        ticker: str,
        side: Side,
        qty: int,
        limit_price: float,
        stop_loss: float,
    ) -> Execution:
        try:
            req = LimitOrderRequest(
                symbol=ticker,
                qty=qty,
                side=OrderSide.BUY if side == Side.LONG else OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
                limit_price=round(limit_price, 2),
                stop_loss=StopLossRequest(stop_price=round(stop_loss, 2)),
            )
            order = self.client.submit_order(req)
            return Execution(
                ticker=ticker,
                side=side,
                qty=qty,
                avg_fill=float(order.filled_avg_price) if order.filled_avg_price else None,
                order_id=str(order.id),
                status="filled" if order.status == "filled" else "submitted",
                submitted_at=datetime.now(tz=timezone.utc),
                broker="alpaca",
            )
        except Exception as e:
            raise BrokerError(f"alpaca submit failed: {e}") from e

    def flatten_all(self) -> None:
        try:
            self.client.close_all_positions(cancel_orders=True)
            log.warning("alpaca.flatten_all")
        except Exception as e:
            raise BrokerError(f"alpaca flatten failed: {e}") from e
