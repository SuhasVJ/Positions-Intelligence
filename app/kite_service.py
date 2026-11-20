import os
from collections import defaultdict
from threading import RLock
from typing import Any

from kiteconnect import KiteConnect


class KiteService:
    """Small read-only wrapper around the Kite Connect positions and charges APIs."""

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

    @property
    def ticker_credentials(self) -> tuple[str, str] | None:
        return (self.api_key, self._access_token) if self.authenticated else None

    def clear_session(self) -> None:
        with self._lock:
            self._access_token = ""
            if self._client:
                self._client.set_access_token("")

    def login_url(self) -> str:
        if not self._client:
            raise RuntimeError("KITE_API_KEY is not configured.")
        return self._client.login_url()

    def create_session(self, request_token: str) -> dict[str, Any]:
        if not self._client:
            raise RuntimeError("KITE_API_KEY is not configured.")
        if not self.api_secret:
            raise RuntimeError("KITE_API_SECRET is not configured.")
        data = self._client.generate_session(request_token, api_secret=self.api_secret)
        with self._lock:
            self._access_token = data["access_token"]
            self._client.set_access_token(self._access_token)
        return {"user_id": data.get("user_id"), "user_name": data.get("user_name")}

    def get_positions(self) -> dict[str, list[dict[str, Any]]]:
        """Return today's activity (day) and current carry-forward positions (net)."""
        with self._lock:
            if not self.authenticated or not self._client:
                raise RuntimeError("Kite session is not authenticated.")
            response = self._client.positions()
        return {
            "day": [self._normalize_position(item) for item in response.get("day", [])],
            "net": [self._normalize_position(item) for item in response.get("net", [])],
        }



    def get_funds(self) -> dict[str, Any]:
        """Return Kite available funds and utilised margins for equity and commodity."""
        with self._lock:
            if not self.authenticated or not self._client:
                raise RuntimeError("Kite session is not authenticated.")
            margins = self._client.margins()

        result: dict[str, Any] = {"available": True, "segments": {}}
        totals = {
            "cash": 0.0, "opening_balance": 0.0, "live_balance": 0.0,
            "collateral": 0.0, "intraday_payin": 0.0, "adhoc_margin": 0.0,
            "net": 0.0, "utilised": 0.0, "m2m_realised": 0.0,
            "m2m_unrealised": 0.0, "span": 0.0, "exposure": 0.0,
        }
        for segment in ("equity", "commodity"):
            data = margins.get(segment) or {}
            available = data.get("available") or {}
            utilised = data.get("utilised") or {}
            values = {
                "cash": self._number(available.get("cash")),
                "opening_balance": self._number(available.get("opening_balance")),
                "live_balance": self._number(available.get("live_balance")),
                "collateral": self._number(available.get("collateral")),
                "intraday_payin": self._number(available.get("intraday_payin")),
                "adhoc_margin": self._number(available.get("adhoc_margin")),
                "net": self._number(data.get("net")),
                "utilised": self._number(utilised.get("debits")),
                "m2m_realised": self._number(utilised.get("m2m_realised")),
                "m2m_unrealised": self._number(utilised.get("m2m_unrealised")),
                "span": self._number(utilised.get("span")),
                "exposure": self._number(utilised.get("exposure")),
            }
            result["segments"][segment] = {
                "enabled": bool(data.get("enabled", False)),
                **{key: round(value, 2) for key, value in values.items()},
            }
            for key, value in values.items():
                totals[key] += value

        result["total"] = {key: round(value, 2) for key, value in totals.items()}
        return result

    def get_day_margins_pnl(self) -> dict[str, Any]:
        """Read Kite's account-level booked/unbooked intraday P&L from margins."""
        with self._lock:
            if not self.authenticated or not self._client:
                raise RuntimeError("Kite session is not authenticated.")
            margins = self._client.margins()

        realised = 0.0
        unrealised = 0.0
        segments: dict[str, dict[str, float]] = {}
        for segment in ("equity", "commodity"):
            segment_data = margins.get(segment) or {}
            utilised = segment_data.get("utilised") or {}
            segment_realised = self._number(utilised.get("m2m_realised"))
            segment_unrealised = self._number(utilised.get("m2m_unrealised"))
            segments[segment] = {
                "realised": round(segment_realised, 2),
                "unrealised": round(segment_unrealised, 2),
            }
            realised += segment_realised
            unrealised += segment_unrealised

        return {
            "realised": round(realised, 2),
            "unrealised": round(unrealised, 2),
            "source": "kite_margins",
            "segments": segments,
        }

    def get_day_charges(self) -> dict[str, Any]:
        """Calculate today's estimated charges from executed trades via Kite's virtual contract note."""
        with self._lock:
            if not self.authenticated or not self._client:
                raise RuntimeError("Kite session is not authenticated.")
            trades = self._client.trades()
            if not trades:
                return self._empty_charges()
            orders = self._client.orders()

            orders_by_id = {str(order.get("order_id")): order for order in orders}
            trades_by_order: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for trade in trades:
                trades_by_order[str(trade.get("order_id"))].append(trade)

            charge_requests = []
            for order_id, fills in trades_by_order.items():
                order = orders_by_id.get(order_id)
                if not order:
                    continue
                quantity = sum(int(fill.get("quantity") or 0) for fill in fills)
                turnover = sum(
                    self._number(fill.get("quantity")) * self._number(fill.get("average_price"))
                    for fill in fills
                )
                if quantity <= 0 or not order.get("exchange") or not order.get("tradingsymbol"):
                    continue
                charge_requests.append({
                    "order_id": order_id,
                    "exchange": order["exchange"],
                    "tradingsymbol": order["tradingsymbol"],
                    "transaction_type": order.get("transaction_type"),
                    "variety": order.get("variety", "regular"),
                    "product": order.get("product"),
                    "order_type": order.get("order_type"),
                    "quantity": quantity,
                    "average_price": round(turnover / quantity, 4),
                })

            if not charge_requests:
                return self._empty_charges()
            charge_rows = self._client.get_virtual_contract_note(charge_requests)

        totals = {
            "brokerage": 0.0,
            "transaction_tax": 0.0,
            "exchange_turnover_charge": 0.0,
            "sebi_turnover_charge": 0.0,
            "stamp_duty": 0.0,
            "gst": 0.0,
            "total": 0.0,
        }
        for row in charge_rows:
            charges = row.get("charges") or {}
            for key in ("brokerage", "transaction_tax", "exchange_turnover_charge",
                        "sebi_turnover_charge", "stamp_duty", "total"):
                totals[key] += self._number(charges.get(key))
            totals["gst"] += self._number((charges.get("gst") or {}).get("total"))

        totals = {key: round(value, 2) for key, value in totals.items()}
        return {
            "available": True,
            "estimated": True,
            "trade_count": len(trades),
            "order_count": len(charge_requests),
            "breakdown": totals,
            "total": totals["total"],
        }

    @staticmethod
    def _empty_charges() -> dict[str, Any]:
        breakdown = {
            "brokerage": 0.0, "transaction_tax": 0.0,
            "exchange_turnover_charge": 0.0, "sebi_turnover_charge": 0.0,
            "stamp_duty": 0.0, "gst": 0.0, "total": 0.0,
        }
        return {"available": True, "estimated": True, "trade_count": 0,
                "order_count": 0, "breakdown": breakdown, "total": 0.0}

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
