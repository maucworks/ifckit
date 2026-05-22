"""
ifckit.profiles.anchor
======================

Shared anchor-point convention used by profile types (IBeamProfile, LBeamProfile)
and opening/window geometry builders.

Anchor points describe where the local origin (0, 0) sits relative to the
profile bounding box (width × height):

    nw ── n ── ne
    │           │
    w ─── c ─── e
    │           │
    sw ── s ── se

The ``anchor_offset(anchor, width, height)`` function returns the (dx, dy)
translation that must be applied to the raw profile points so that the
origin falls at the requested anchor position.
"""

from __future__ import annotations

# Anchor → (x_fraction_of_width, y_fraction_of_height)
# (0, 0) = bottom-left corner, (1, 1) = top-right corner.
ANCHOR_OFFSETS: dict[str, tuple[float, float]] = {
    "sw": (0.0, 0.0),
    "s": (0.5, 0.0),
    "se": (1.0, 0.0),
    "w": (0.0, 0.5),
    "c": (0.5, 0.5),
    "e": (1.0, 0.5),
    "nw": (0.0, 1.0),
    "n": (0.5, 1.0),
    "ne": (1.0, 1.0),
}

VALID_ANCHORS: frozenset[str] = frozenset(ANCHOR_OFFSETS)


def anchor_offset(anchor: str, width: float, height: float) -> tuple[float, float]:
    """
    Return ``(dx, dy)`` — the shift to subtract from the bottom-left corner
    so that the origin lands at the requested anchor position.

    Example::

        anchor="sw"  → dx = 0,              dy = 0        (bottom-left)
        anchor="c"  → dx = -width/2,  dy = -height/2 (centre)
        anchor="sw" → dx = 0,         dy = 0        (bottom-left, no shift)

    Usage in a profile builder::

        dx, dy = anchor_offset(anchor, width, height)
        pts = [
            (dx,         dy),
            (dx + width, dy),
            (dx + width, dy + height),
            (dx,         dy + height),
        ]

    Args:
        anchor: One of the 9 compass keys in ``VALID_ANCHORS``.
        width:  Bounding-box width (same units as the profile).
        height: Bounding-box height (same units as the profile).

    Returns:
        ``(dx, dy)`` translation to apply to profile points.

    Raises:
        ValueError: If *anchor* is not a valid key.
    """
    if anchor not in ANCHOR_OFFSETS:
        raise ValueError(f"anchor must be one of {sorted(VALID_ANCHORS)}, got {anchor!r}")
    fx, fy = ANCHOR_OFFSETS[anchor]
    return -fx * width, -fy * height
