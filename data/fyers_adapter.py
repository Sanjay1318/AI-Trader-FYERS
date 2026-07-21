"""Data-only FYERS adapter for normalized quotes, ticks, and candles.

This adapter is deliberately isolated from collectors, storage, execution, and
UI.  It is safe to exercise independently while legacy TrueData ingestion
remains operational.  Future model pipelines can consume the typed records
without depending on FYERS response formats.
"""

from __future__ import annotations

import threading
from datetime import date, datetime, timezone
from typing import Any, Callable, Iterable

from config.settings import FYERS_ACCESS_TOKEN, FYERS_CLIENT_ID
from data.fyers_provider import FyersMarketDataProvider, FyersProviderError
from data.market_data_provider import MarketCandle, MarketTick
from utils.logger import get_logger

logger = get_logger("fyers_adapter")

TickHandler = Callable[[MarketTick], None]
StatusHandler = Callable[[dict[str, Any]], None]


class FyersMarketDataAdapter(FyersMarketDataProvider):
    """FYERS REST and WebSocket adapter with normalized, data-only outputs."""

    def __init__(
        self,
        client_id: str | None = None,
        access_token: str | None = None,
        reconnect_retries: int = 5,
    ):
        super().__init__(client_id=client_id, access_token=access_token)
        self._reconnect_retries = reconnect_retries
        self._socket: Any | None = None
        self._socket_thread: threading.Thread | None = None
        self._subscriptions: set[str] = set()
        self._tick_handler: TickHandler | None = None
        self._status_handler: StatusHandler | None = None
        self._streaming = False
        self._lock = threading.RLock()

    def get_candles(
        self,
        symbol: str,
        start: date | datetime | str,
        end: date | datetime | str,
        interval: str = "1",
    ) -> list[MarketCandle]:
        """Fetch and normalize FYERS historical bars; does not persist them."""
        payload = {
            "symbol": symbol,
            "resolution": interval,
            "date_format": "1",
            "range_from": self._format_date(start),
            "range_to": self._format_date(end),
            "cont_flag": "1",
        }
        response = self._get_client().history(data=payload)
        if response.get("s") != "ok":
            raise FyersProviderError(response.get("message") or f"FYERS candle request failed: {response}")
        return [self._normalize_candle(symbol, row, interval) for row in response.get("candles", [])]

    def start_stream(
        self,
        symbols: Iterable[str],
        on_tick: TickHandler,
        on_status: StatusHandler | None = None,
    ) -> None:
        """Start a daemonized FYERS SymbolUpdate stream with automatic reconnect."""
        requested = {symbol.strip() for symbol in symbols if symbol and symbol.strip()}
        if not requested:
            raise ValueError("At least one FYERS symbol is required to start a stream.")
        if not callable(on_tick):
            raise TypeError("on_tick must be callable.")
        if not self.is_configured:
            raise FyersProviderError("FYERS_CLIENT_ID and FYERS_ACCESS_TOKEN must be configured.")

        with self._lock:
            self._subscriptions = requested
            self._tick_handler = on_tick
            self._status_handler = on_status
            if self._streaming:
                self._subscribe_current_symbols()
                return
            self._socket = self._build_socket()
            self._streaming = True
            self._socket_thread = threading.Thread(
                target=self._socket.connect,
                name="fyers-market-data",
                daemon=True,
            )
            self._socket_thread.start()

    def update_subscriptions(self, symbols: Iterable[str]) -> None:
        """Replace subscriptions; safe while disconnected because reconnect replays them."""
        requested = {symbol.strip() for symbol in symbols if symbol and symbol.strip()}
        if not requested:
            raise ValueError("At least one FYERS symbol is required.")
        with self._lock:
            previous = self._subscriptions
            self._subscriptions = requested
            if self._socket is not None and self._streaming:
                removed = sorted(previous - requested)
                if removed:
                    self._socket.unsubscribe(symbols=removed, data_type="SymbolUpdate")
                self._subscribe_current_symbols()

    def stop_stream(self, join_timeout: float = 5.0) -> None:
        """Close the socket and discard callbacks; no retry loop remains active."""
        with self._lock:
            self._streaming = False
            socket, thread = self._socket, self._socket_thread
            self._socket = None
            self._socket_thread = None
        if socket is not None:
            try:
                socket.close_connection()
            except Exception as exc:
                logger.warning("FYERS socket close failed: %s", exc)
        if thread is not None and thread.is_alive():
            thread.join(timeout=join_timeout)

    def _build_socket(self) -> Any:
        try:
            from fyers_apiv3.FyersWebsocket.data_ws import FyersDataSocket
        except ImportError as exc:
            raise FyersProviderError("FYERS WebSocket support is unavailable in fyers-apiv3.") from exc
        return FyersDataSocket(
            access_token=self._websocket_access_token(),
            litemode=False,
            write_to_file=False,
            reconnect=True,
            reconnect_retry=self._reconnect_retries,
            on_connect=self._on_socket_connect,
            on_message=self._on_socket_message,
            on_error=self._on_socket_error,
            on_close=self._on_socket_close,
        )

    def _websocket_access_token(self) -> str:
        return self._access_token if ":" in self._access_token else f"{self._client_id}:{self._access_token}"

    def _on_socket_connect(self) -> None:
        self._emit_status({"provider": self.provider_name, "event": "connected"})
        self._subscribe_current_symbols()

    def _subscribe_current_symbols(self) -> None:
        with self._lock:
            if self._socket is None or not self._subscriptions:
                return
            self._socket.subscribe(symbols=sorted(self._subscriptions), data_type="SymbolUpdate")
        self._emit_status({"provider": self.provider_name, "event": "subscribed", "symbols": sorted(self._subscriptions)})

    def _on_socket_message(self, message: dict[str, Any]) -> None:
        if self._is_control_message(message):
            self._emit_status({
                "provider": self.provider_name,
                "event": "socket_status",
                "type": message.get("type"),
                "message": message.get("message", ""),
            })
            return
        try:
            tick = self._normalize_tick(message)
            handler = self._tick_handler
            if handler is not None:
                handler(tick)
        except Exception as exc:
            logger.warning("FYERS message normalization failed: %s", exc)
            self._emit_status({"provider": self.provider_name, "event": "message_error", "reason": str(exc)})

    def _on_socket_error(self, error: Any) -> None:
        self._emit_status({"provider": self.provider_name, "event": "error", "reason": str(error)})

    def _on_socket_close(self, message: Any = None) -> None:
        self._emit_status({"provider": self.provider_name, "event": "closed", "reason": str(message or "")})

    def _emit_status(self, event: dict[str, Any]) -> None:
        handler = self._status_handler
        if handler is not None:
            handler(event)

    def _normalize_tick(self, message: dict[str, Any]) -> MarketTick:
        values = message.get("v", message)
        symbol = values.get("symbol") or message.get("symbol") or message.get("n")
        if not symbol:
            raise FyersProviderError(f"FYERS update did not include a symbol: {message}")
        price = values.get("ltp", values.get("lp"))
        if price is None:
            raise FyersProviderError(f"FYERS update did not include a price: {message}")
        return MarketTick(
            symbol=symbol,
            price=float(price),
            timestamp=self._parse_timestamp(values.get("last_traded_time") or values.get("tt")),
            volume=self._as_int(values.get("vol_traded_today") or values.get("volume")),
            bid_price=self._as_float(values.get("bid")),
            ask_price=self._as_float(values.get("ask")),
            open_interest=self._as_int(values.get("oi")),
            provider=self.provider_name,
            raw=message,
        )

    @staticmethod
    def _is_control_message(message: dict[str, Any]) -> bool:
        """FYERS emits connection and subscription acknowledgements as messages."""
        values = message.get("v", message)
        return bool(
            message.get("type") in {"cn", "ful", "sub", "unsub"}
            and not (values.get("symbol") or message.get("symbol") or message.get("n"))
        )

    def _normalize_candle(self, symbol: str, row: list[Any], interval: str) -> MarketCandle:
        if len(row) < 6:
            raise FyersProviderError(f"Invalid FYERS candle payload: {row}")
        timestamp = self._parse_timestamp(row[0])
        if timestamp is None:
            raise FyersProviderError(f"Invalid FYERS candle timestamp: {row[0]}")
        return MarketCandle(
            symbol=symbol,
            timestamp=timestamp,
            open=float(row[1]),
            high=float(row[2]),
            low=float(row[3]),
            close=float(row[4]),
            volume=int(row[5] or 0),
            interval=self._display_interval(interval),
            provider=self.provider_name,
            raw=row,
        )

    @staticmethod
    def _format_date(value: date | datetime | str) -> str:
        return value.strftime("%Y-%m-%d") if isinstance(value, (date, datetime)) else str(value)

    @staticmethod
    def _display_interval(interval: str) -> str:
        return f"{interval}m" if interval.isdigit() else interval
