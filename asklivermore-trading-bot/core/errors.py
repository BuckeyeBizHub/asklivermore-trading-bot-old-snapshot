"""core.errors — typed exception hierarchy. Agents raise these; graph routes them."""
from __future__ import annotations


class TradingBotError(Exception):
    """Base."""


class LLMOutputError(TradingBotError):
    """Claude returned invalid or schema-violating output."""


class DataSourceError(TradingBotError):
    """Polygon, MarketAux, etc. failed."""


class BrokerError(TradingBotError):
    """Alpaca / IBKR rejected an order or is unreachable."""


class PolicyViolation(TradingBotError):
    """zodchiii policy agent flagged the run."""


class KillSwitchTriggered(TradingBotError):
    """Halt the entire loop. The watchdog flattens positions."""


class MemoryUnavailable(TradingBotError):
    """Graphify is down. Run continues in degraded mode."""
