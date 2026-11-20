"""Position P&L progress relative to the position's price-value basis.

This is a comparison scale, not broker margin or required capital.
"""
from __future__ import annotations

from typing import Any


def add_pnl_progress(position: dict[str, Any]) -> dict[str, Any]:
    """Attach a bounded +/-2x progress scale to a Kite position in-place."""
    quantity = float(position.get("quantity") or 0)
    average_price = float(position.get("average_price") or 0)
    pnl = float(position.get("pnl") or 0)
    value_basis = abs(quantity * average_price)

    multiple = pnl / value_basis if value_basis > 0 and quantity != 0 else None
    # Requested asymmetric scale: max loss is -1x basis; +1x and +2x profit map to 50% and 100%.
    progress_limit = 1.0 if multiple is not None and multiple < 0 else 2.0
    progress_percent = min(abs(multiple) / progress_limit, 1.0) * 100 if multiple is not None else 0.0
    direction = "PROFIT" if pnl > 0 else "LOSS" if pnl < 0 else "FLAT"

    position.update({
        "position_value_basis": round(value_basis, 2),
        "pnl_multiple": round(multiple, 4) if multiple is not None else None,
        "pnl_progress_percent": round(progress_percent, 2),
        "pnl_progress_direction": direction if multiple is not None else "UNAVAILABLE",
    })
    return position
