"""FYERS market-data foundation.

This module is intentionally data-only: it can validate access and normalize
quotes, but it exposes no order-placement capability.  Later stages can add
streaming and historical-data methods behind the same provider contract.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from config.settings import FYERS_ACCESS_TOKEN, FYERS_CLIENT_ID
from data.market_data_provider import MarketDataProvider, MarketQuote
from utils.logger import get_logger

logger = get_logger("fyers_provider")


class FyersProviderError(RuntimeError):
    """Raised when FYERS market data cannot be obtained or normalized."""


class FyersMarketDataProvider(MarketDataProvider):
    """FYERS implementation of the market-data provider contract."""

    def __init__(self, client_id: str | None = None, access_token: str | None = None):
        self._client_id = client_id if client_id is not None else FYERS_CLIENT_ID
        self._access_token = access_token if access_token is not None else FYERS_ACCESS_TOKEN
        self._client: Any | None = None

    @property
    def provider_name(self) -> str:
        return "fyers"

    @property
    def is_configured(self) -> bool:
        return bool(self._client_id and self._access_token)

    def _get_client(self) -> Any:
        if not self.is_configured:
            raise FyersProviderError("FYERS_CLIENT_ID and FYERS_ACCESS_TOKEN must be configured.")
        if self._client is None:
            try:
                from fyers_apiv3 import fyersModel
            except ImportError as exc:
                raise FyersProviderError("fyers-apiv3 is not installed. Run pip install -r requirements.txt.") from exc
            self._client = fyersModel.FyersModel(
                client_id=self._client_id,
                token=self._access_token,
                is_async=False,
                log_path="",
            )
        return self._client

    def health_check(self) -> dict[str, Any]:
        result: dict[str, Any] = {"provider": self.provider_name, "configured": self.is_configured}
        if not self.is_configured:
            return {**result, "connected": False, "reason": "missing FYERS credentials"}
        try:
            response = self._get_client().get_profile()
            return {**result, "connected": response.get("s") == "ok", "status": response.get("s")}
        except Exception as exc:
            logger.warning("FYERS profile check failed: %s", exc)
            return {**result, "connected": False, "reason": str(exc)}

    def get_quotes(self, symbols: Iterable[str]) -> list[MarketQuote]:
        requested = [symbol.strip() for symbol in symbols if symbol and symbol.strip()]
        if not requested:
            return []
        response = self._get_client().quotes(data={"symbols": ",".join(requested), "data_flag": "1"})
        if response.get("s") != "ok":
            raise FyersProviderError(response.get("message") or f"FYERS quote request failed: {response}")
        return [self._normalize_quote(item) for item in response.get("d", [])]

    def _normalize_quote(self, item: dict[str, Any]) -> MarketQuote:
        values = item.get("v", item)
        symbol = item.get("n") or values.get("symbol")
        if not symbol:
            raise FyersProviderError(f"FYERS quote did not include a symbol: {item}")
        timestamp = self._parse_timestamp(values.get("tt"))
        return MarketQuote(
            symbol=symbol,
            price=float(values.get("lp") or values.get("ltp") or 0),
            timestamp=timestamp,
            bid_price=self._as_float(values.get("bid")),
            ask_price=self._as_float(values.get("ask")),
            volume=self._as_int(values.get("vol_traded_today") or values.get("volume")),
            open_interest=self._as_int(values.get("oi")),
            average_price=self._as_float(values.get("atp")),
            previous_close=self._as_float(values.get("prev_close_price")),
            change=self._as_float(values.get("ch")),
            change_percent=self._as_float(values.get("chp")),
            provider=self.provider_name,
            raw=item,
        )

    @staticmethod
    def _as_float(value: Any) -> float | None:
        return float(value) if value not in (None, "") else None

    @staticmethod
    def _as_int(value: Any) -> int | None:
        return int(value) if value not in (None, "") else None

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime | None:
        if value in (None, "", 0):
            return None
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            return None
