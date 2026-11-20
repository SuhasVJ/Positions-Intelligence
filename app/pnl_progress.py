"""Open-position P&L progress based on the live unrealised component.

Total position P&L can include realised losses/profits from earlier partial
exits. Those booked amounts must not be divided by the remaining open
quantity's value basis.
"""
from __future__ import annotations

from typing import Any


def add_pnl_progress(position: dict[str, Any]) -> dict[str, Any]:
    """Attach an open-exposure progress scale to a Kite position in-place."""
    quantity = float(position.get("quantity") or 0)
    average_price = float(position.get("average_price") or 0)
    unrealised = position.get("unrealised")
    value_basis = abs(quantity * average_price)

    # Progress is for the currently open leg only. Total P&L (realised +
    # unrealised) remains untouched and continues to be shown in the table.
    progress_amount = float(unrealised) if unrealised is not None else None
    multiple = (
        progress_amount / value_basis
        if value_basis > 0 and quantity != 0 and progress_amount is not None
        else None
    )
    progress_limit = 1.0 if multiple is not None and multiple < 0 else 2.0
    progress_percent = (
        min(abs(multiple) / progress_limit, 1.0) * 100
        if multiple is not None else 0.0
    )
    direction = (
        "PROFIT" if progress_amount is not None and progress_amount > 0
        else "LOSS" if progress_amount is not None and progress_amount < 0
        else "FLAT"
    )

    position.update({
        "position_value_basis": round(value_basis, 2),
        "pnl_progress_amount": round(progress_amount, 2) if progress_amount is not None else None,
        "pnl_progress_basis": "OPEN_UNREALISED_PNL",
        "pnl_multiple": round(multiple, 4) if multiple is not None else None,
        "pnl_progress_percent": round(progress_percent, 2),
        "pnl_progress_direction": direction if multiple is not None else "UNAVAILABLE",
    })
    return position
