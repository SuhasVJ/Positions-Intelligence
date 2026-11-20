"""Deterministic, metadata-first classification for Kite positions.

Classification deliberately does not infer an asset type from a trading symbol
alone. Missing instrument-master metadata produces UNKNOWN rather than a guess.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

INDEX_UNDERLYINGS = {
    "NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY",
    "SENSEX", "BANKEX", "NIFTYNXT50",
}
OPTION_TYPES = {"CE", "PE"}


def _clean(value: Any) -> str:
    return str(value or "").strip().upper()


def classify_position(position: dict[str, Any],
                      instrument: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return normalized asset class and direction using Kite instrument metadata."""
    instrument = instrument or {}
    exchange = _clean(instrument.get("exchange") or position.get("exchange"))
    instrument_type = _clean(instrument.get("instrument_type"))
    underlying = _clean(instrument.get("name"))
    segment = _clean(instrument.get("segment"))
    option_type = instrument_type if instrument_type in OPTION_TYPES else None

    if instrument_type == "EQ" and exchange in {"NSE", "BSE"}:
        asset_type = "EQUITY"
    elif option_type:
        if exchange == "CDS":
            asset_type = "CURRENCY_OPTION"
        elif exchange == "MCX" or segment.startswith("MCX"):
            asset_type = "COMMODITY_OPTION"
        elif underlying in INDEX_UNDERLYINGS:
            asset_type = "INDEX_OPTION"
        elif exchange in {"NFO", "BFO"}:
            asset_type = "STOCK_OPTION"
        else:
            asset_type = "UNKNOWN"
    elif instrument_type == "FUT":
        if exchange == "CDS":
            asset_type = "CURRENCY_FUTURE"
        elif exchange == "MCX" or segment.startswith("MCX"):
            asset_type = "COMMODITY_FUTURE"
        elif underlying in INDEX_UNDERLYINGS:
            asset_type = "INDEX_FUTURE"
        elif exchange in {"NFO", "BFO"}:
            asset_type = "STOCK_FUTURE"
        else:
            asset_type = "UNKNOWN"
    else:
        asset_type = "UNKNOWN"

    quantity = _to_int(position.get("quantity"))
    direction = "LONG" if quantity > 0 else "SHORT" if quantity < 0 else "FLAT"
    has_metadata = bool(instrument_type and exchange)
    confidence = 1.0 if asset_type != "UNKNOWN" and has_metadata else 0.0

    return {
        "asset_type": asset_type,
        "direction": direction,
        "underlying": underlying or None,
        "instrument_type": instrument_type or None,
        "option_type": option_type,
        "expiry": _to_iso_or_none(instrument.get("expiry")),
        "strike": _to_float_or_none(instrument.get("strike")),
        "lot_size": _to_int_or_none(instrument.get("lot_size")),
        "classification_status": "CLASSIFIED" if confidence else "UNKNOWN",
        "classification_confidence": confidence,
        "classification_source": "KITE_INSTRUMENT_MASTER" if confidence else "INSUFFICIENT_METADATA",
    }


def _to_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _to_int_or_none(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _to_float_or_none(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _to_iso_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)
