"""
ifckit.builders._precision
==========================

Coordinate precision rounding for IFC output.
"""

from __future__ import annotations

_PRECISION: int = 4
"""Number of decimal places for coordinate rounding."""
_MIN_COORD: float = 10 ** (-_PRECISION)


def set_precision(decimals: int) -> None:
    """Set decimal precision for IFC coordinate output."""
    global _PRECISION, _MIN_COORD
    if not isinstance(decimals, int):
        raise TypeError(f"decimals must be int, got {type(decimals).__name__}")
    if decimals < 0 or decimals > 10:
        raise ValueError(f"decimals must be 0-10, got {decimals}")
    _PRECISION = decimals
    _MIN_COORD = 10 ** (-decimals)


def get_precision() -> int:
    """Return current coordinate precision (decimal places)."""
    return _PRECISION


def round_coord(value: float) -> float:
    """Round a coordinate value to current precision."""
    return float(round(value, _PRECISION))


__all__ = [
    "set_precision",
    "get_precision",
    "round_coord",
]
