"""
ifckit.paper
============

ISO 216 A-series paper sizes and related helpers.

No Rhino dependency — safe to import anywhere.

Usage::

    from ifckit.paper import iso_a_size_mm, ISO_A_SIZES_MM

    w, h = iso_a_size_mm(1)                  # A1 portrait → (594.0, 841.0)
    w, h = iso_a_size_mm(1, landscape=True)  # A1 landscape → (841.0, 594.0)
"""

from __future__ import annotations

from typing import Tuple

# ISO 216 A-series sizes in mm, portrait (width × height), A0–A10.
ISO_A_SIZES_MM: dict[int, Tuple[float, float]] = {
    0:  ( 841.0, 1189.0),
    1:  ( 594.0,  841.0),
    2:  ( 420.0,  594.0),
    3:  ( 297.0,  420.0),
    4:  ( 210.0,  297.0),
    5:  ( 148.0,  210.0),
    6:  ( 105.0,  148.0),
    7:  (  74.0,  105.0),
    8:  (  52.0,   74.0),
    9:  (  37.0,   52.0),
    10: (  26.0,   37.0),
}


def iso_a_size_mm(
    size: int,
    landscape: bool = False,
) -> Tuple[float, float]:
    """Return ISO A paper dimensions in millimetres.

    Args:
        size:      A-series number (0–10).
        landscape: If ``True``, return (width, height) in landscape
                   orientation (wider than tall).

    Returns:
        ``(width_mm, height_mm)`` tuple.

    Raises:
        ValueError: if *size* is not in range 0–10.
    """
    if size not in ISO_A_SIZES_MM:
        raise ValueError(f"ISO A size must be 0–10, got {size!r}")
    w, h = ISO_A_SIZES_MM[size]
    return (h, w) if landscape else (w, h)
