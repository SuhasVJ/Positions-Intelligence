import os
from threading import RLock
from typing import Any

from kiteconnect import KiteConnect


class KiteService:
    """Small read-only wrapper around the Kite Connect positions API."""

    def __init__(self) -> None:
        self.api_key = os.getenv("KITE_API_KEY", "").strip()
        self.api_secret = os.getenv("KITE_API_SECRET", "").strip()
        self._access_token = os.getenv("KITE_ACCESS_TOKEN", "").strip()
        self._client: KiteConnect | None = None
        self._lock = RLock()
        self._configure_client()

    def _configure_client(self) -> None:
        if not self.api_key:
            self._client = None
            return
        self._client = KiteConnect(api_key=self.api_key)
        if self._access_token:
            self._client.set_access_token(self._access_token)

    @property
    def authenticated(self) -> bool:
        return bool(self._client and self._access_token)

    def login_url(self) -> str:
        if not self._client:
            raise RuntimeError("KITE_API_KEY is not configured.")
        return self._client.login_url()

    def create_session(self, request_token: str) -> dict[str, Any]:
        if not self._client:
            raise RuntimeError("KITE_API_KEY is not configured.")
        if not self.api_secret:
            raise RuntimeError("KITE_API_SECRET is not configured.")
        data = self._client.generate_session(
            request_token, api_secret=self.api_secret
        )
        with self._lock:
            self._access_token = data["access_token"]
            self._client.set_access_token(self._access_token)
        # Never return or log the access token.
        return {"user_id": data.get("user_id"), "user_name": data.get("user_name")}

    def get_day_positions(self) -> list[dict[str, Any]]:
        with self._lock:
            if not self.authenticated or not self._client:
                raise RuntimeError("Kite session is not authenticated.")
            response = self._client.positions()
        positions = response.get("day", [])
        return [self._normalize_position(item) for item in positions]

    @staticmethod
    def _number(value: Any) -> float:
        try:
            return float(value or 0)
        except (TypeError, ValueError):
            return 0.0

    @classmethod
    def _normalize_position(cls, item: dict[str, Any]) -> dict[str, Any]:
        fields = (
            "tradingsymbol", "exchange", "instrument_token", "product",
            "quantity", "buy_quantity", "sell_quantity", "average_price",
            "buy_price", "sell_price", "last_price", "close_price",
            "realised", "unrealised", "pnl", "m2m",
        )
        result = {key: item.get(key) for key in fields}
        for key in (
            "average_price", "buy_price", "sell_price", "last_price",
            "close_price", "realised", "unrealised", "pnl", "m2m",
        ):
            result[key] = cls._number(result[key])
        result["quantity"] = int(result.get("quantity") or 0)
        result["buy_quantity"] = int(result.get("buy_quantity") or 0)
        result["sell_quantity"] = int(result.get("sell_quantity") or 0)
        return result

    @staticmethod
    def summarize(positions: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "position_count": len(positions),
            "open_positions": sum(1 for p in positions if p["quantity"] != 0),
            "realised": round(sum(p["realised"] for p in positions), 2),
            "unrealised": round(sum(p["unrealised"] for p in positions), 2),
            "pnl": round(sum(p["pnl"] for p in positions), 2),
        }
