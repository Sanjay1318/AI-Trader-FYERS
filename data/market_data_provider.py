"""Provider contracts shared by market-data sources and future AI services."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Iterable


@dataclass(frozen=True)
class MarketQuote:
    """Provider-neutral latest market data; unavailable fields remain None."""

    symbol: str
    price: float
    timestamp: datetime | None = None
    bid_price: float | None = None
    ask_price: float | None = None
    volume: int | None = None
    open_interest: int | None = None
    average_price: float | None = None
    previous_close: float | None = None
    change: float | None = None
    change_percent: float | None = None
    provider: str = ""
    raw: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        if self.timestamp is not None:
            result["timestamp"] = self.timestamp.isoformat()
        return result


@dataclass(frozen=True)
class MarketTick:
    """Provider-neutral live update suitable for storage or feature pipelines."""

    symbol: str
    price: float
    timestamp: datetime | None = None
    volume: int | None = None
    bid_price: float | None = None
    ask_price: float | None = None
    open_interest: int | None = None
    provider: str = ""
    raw: dict[str, Any] | None = None


@dataclass(frozen=True)
class MarketCandle:
    """Provider-neutral OHLCV bar; interval remains explicit for model inputs."""

    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int = 0
    interval: str = "1m"
    provider: str = ""
    raw: list[Any] | dict[str, Any] | None = None


class MarketDataProvider(ABC):
    """Small, stable boundary for feeds now and model features later."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider identifier."""

    @abstractmethod
    def health_check(self) -> dict[str, Any]:
        """Return non-sensitive connectivity and credential status."""

    @abstractmethod
    def get_quotes(self, symbols: Iterable[str]) -> list[MarketQuote]:
        """Return normalized latest quotes for provider-specific symbols."""
