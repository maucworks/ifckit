"""
ifckit.validator
===============

Structural validation of PendingElement objects before they are passed
to builders.  No ifcopenshell calls — pure Python geometry checks.

Usage::

    from ifckit.validator import validate, register_validator

    @register_validator(MyPendingElement)
    def _validate_my_element(pending: "MyPendingElement") -> ValidationResult:
        # validation logic
        ...

    result = validate(pending_wall)
    if not result.ok:
        for err in result.errors:
            print("ERROR:", err)
    for warn in result.warnings:
        print("WARNING:", warn)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Type

from ifckit.elements.base import PendingElement
from ifckit.elements.bridge import (
    AlignmentSegment,
    PendingAlignment,
    PendingBridge,
    PendingBridgePart,
)
from ifckit.elements.building import PendingSlab, PendingWall
from ifckit.elements.structural import PendingBeam, PendingColumn, PendingRevolvedBeam
from ifckit.elements.swept import PendingSweptBeam
from ifckit.geometry import Vec


# ---------------------------------------------------------------------------
# Validator registry with auto-registration
# ---------------------------------------------------------------------------


class ValidatorRegistry:
    """Registry for element validators with decorator-based auto-registration."""

    _validators: Dict[Type[PendingElement], Callable[..., ValidationResult]] = {}

    @classmethod
    def register(
        cls,
        element_cls: Type[PendingElement],
    ) -> Callable[[Callable[..., ValidationResult]], Callable[..., ValidationResult]]:
        """Decorator to register a validator for a PendingElement subclass."""
        def decorator(func: Callable[..., ValidationResult]) -> Callable[..., ValidationResult]:
            cls._validators[element_cls] = func
            return func
        return decorator

    @classmethod
    def get(cls, element_cls: Type[PendingElement]) -> Callable[..., ValidationResult]:
        """Get validator for an element class."""
        if element_cls not in cls._validators:
            raise TypeError(f"No validator registered for {element_cls.__name__}")
        return cls._validators[element_cls]

    @classmethod
    def has(cls, element_cls: Type[PendingElement]) -> bool:
        """Check if validator exists for element class."""
        return element_cls in cls._validators


register_validator = ValidatorRegistry.register

# Tolerances
_MIN_LENGTH = 1e-6  # minimum meaningful length (metres)
_MIN_ANGLE = 1e-9  # minimum meaningful angle (radians)
_WARN_SHORT = 0.01  # warn if axis < 1 cm or profile side < 1 cm
_ENDPOINT_TOL = 1e-4  # max gap between consecutive segment endpoints


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    """Outcome of a validate() call."""

    ok: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def __bool__(self) -> bool:  # allow `if validate(x):`
        return self.ok


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _profile_area_2d(pts: list) -> float:
    """Shoelace formula — signed area in XY plane."""
    n = len(pts)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += pts[i].x * pts[j].y - pts[j].x * pts[i].y
    return area / 2.0


def _footprint_perimeter(pts: list) -> float:
    n = len(pts)
    return sum((pts[(i + 1) % n] - pts[i]).length() for i in range(n))


def _seg_end(seg: AlignmentSegment) -> Vec:
    """3-D end point of an alignment segment."""
    return seg.geometry.end


# ---------------------------------------------------------------------------
# Per-type validators
# ---------------------------------------------------------------------------


@register_validator(PendingWall)
def _validate_wall(w: PendingWall) -> ValidationResult:
    errors: List[str] = []
    warnings: List[str] = []

    # footprint: need at least 3 points
    if len(w.footprint) < 3:
        errors.append(
            f"PendingWall '{w.name}': footprint must have at least 3 points, got {len(w.footprint)}"
        )
    else:
        area = abs(_profile_area_2d(w.footprint))
        if area < _MIN_LENGTH**2:
            errors.append(f"PendingWall '{w.name}': footprint area is effectively zero")
        perim = _footprint_perimeter(w.footprint)
        if perim < _WARN_SHORT:
            warnings.append(
                f"PendingWall '{w.name}': footprint perimeter is very small ({perim:.4f} m)"
            )

    # height
    if w.height <= 0.0:
        errors.append(f"PendingWall '{w.name}': height must be > 0, got {w.height}")
    elif w.height < _WARN_SHORT:
        warnings.append(f"PendingWall '{w.name}': height is very small ({w.height:.4f} m)")

    return ValidationResult(ok=len(errors) == 0, errors=errors, warnings=warnings)


@register_validator(PendingSlab)
def _validate_slab(s: PendingSlab) -> ValidationResult:
    errors: List[str] = []
    warnings: List[str] = []

    if len(s.footprint) < 3:
        errors.append(
            f"PendingSlab '{s.name}': footprint must have at least 3 points, got {len(s.footprint)}"
        )
    else:
        area = abs(_profile_area_2d(s.footprint))
        if area < _MIN_LENGTH**2:
            errors.append(f"PendingSlab '{s.name}': footprint area is effectively zero")

    if s.thickness <= 0.0:
        errors.append(f"PendingSlab '{s.name}': thickness must be > 0, got {s.thickness}")
    elif s.thickness < _WARN_SHORT:
        warnings.append(f"PendingSlab '{s.name}': thickness is very small ({s.thickness:.4f} m)")

    return ValidationResult(ok=len(errors) == 0, errors=errors, warnings=warnings)


@register_validator(PendingBeam)
def _validate_beam(b: PendingBeam) -> ValidationResult:
    errors: List[str] = []
    warnings: List[str] = []

    axis_len = b.axis.length
    if axis_len < _MIN_LENGTH:
        errors.append(f"PendingBeam '{b.name}': axis length must be > 0, got {axis_len:.6f}")
    elif axis_len < _WARN_SHORT:
        warnings.append(f"PendingBeam '{b.name}': axis is very short ({axis_len:.4f} m)")

    if len(b.profile) < 3:
        errors.append(
            f"PendingBeam '{b.name}': profile must have at least 3 points, got {len(b.profile)}"
        )
    else:
        area = abs(_profile_area_2d(b.profile))
        if area < _MIN_LENGTH**2:
            errors.append(f"PendingBeam '{b.name}': profile area is effectively zero")

    return ValidationResult(ok=len(errors) == 0, errors=errors, warnings=warnings)


@register_validator(PendingColumn)
def _validate_column(c: PendingColumn) -> ValidationResult:
    errors: List[str] = []
    warnings: List[str] = []

    axis_len = c.axis.length
    if axis_len < _MIN_LENGTH:
        errors.append(f"PendingColumn '{c.name}': axis length must be > 0, got {axis_len:.6f}")
    elif axis_len < _WARN_SHORT:
        warnings.append(f"PendingColumn '{c.name}': axis is very short ({axis_len:.4f} m)")

    if len(c.profile) < 3:
        errors.append(
            f"PendingColumn '{c.name}': profile must have at least 3 points, got {len(c.profile)}"
        )
    else:
        area = abs(_profile_area_2d(c.profile))
        if area < _MIN_LENGTH**2:
            errors.append(f"PendingColumn '{c.name}': profile area is effectively zero")

    return ValidationResult(ok=len(errors) == 0, errors=errors, warnings=warnings)


@register_validator(PendingRevolvedBeam)
def _validate_revolved_beam(rb: PendingRevolvedBeam) -> ValidationResult:
    errors: List[str] = []
    warnings: List[str] = []

    if abs(rb.arc.angle) < _MIN_ANGLE:
        errors.append(f"PendingRevolvedBeam '{rb.name}': arc angle must be non-zero")

    if len(rb.profile) < 3:
        errors.append(
            f"PendingRevolvedBeam '{rb.name}': profile must have at least 3 points, "
            f"got {len(rb.profile)}"
        )
    else:
        area = abs(_profile_area_2d(rb.profile))
        if area < _MIN_LENGTH**2:
            errors.append(f"PendingRevolvedBeam '{rb.name}': profile area is effectively zero")

    arc_len = abs(rb.arc.angle) * rb.arc.radius
    if 0 < arc_len < _WARN_SHORT:
        warnings.append(
            f"PendingRevolvedBeam '{rb.name}': arc length is very small ({arc_len:.4f} m)"
        )

    return ValidationResult(ok=len(errors) == 0, errors=errors, warnings=warnings)


@register_validator(PendingAlignment)
def _validate_alignment(a: PendingAlignment) -> ValidationResult:
    errors: List[str] = []
    warnings: List[str] = []

    if len(a.segments) == 0:
        errors.append(f"PendingAlignment '{a.name}': must have at least one segment")
        return ValidationResult(ok=False, errors=errors, warnings=warnings)

    # Each segment must have positive length; warn if very short
    for i, seg in enumerate(a.segments):
        if seg.length < _MIN_LENGTH:
            errors.append(f"PendingAlignment '{a.name}': segment {i} has zero or negative length")
        elif seg.length < _WARN_SHORT:
            warnings.append(
                f"PendingAlignment '{a.name}': segment {i} is very short ({seg.length:.4f} m)"
            )

    # Consecutive segments must share endpoints (G0 continuity)
    for i in range(len(a.segments) - 1):
        end_i = _seg_end(a.segments[i])
        start_next = a.segments[i + 1].geometry.start
        gap = (end_i - start_next).length()
        if gap > _ENDPOINT_TOL:
            errors.append(
                f"PendingAlignment '{a.name}': gap between segment {i} end and "
                f"segment {i + 1} start is {gap:.6f} m (max {_ENDPOINT_TOL} m)"
            )

    return ValidationResult(ok=len(errors) == 0, errors=errors, warnings=warnings)


@register_validator(PendingBridgePart)
def _validate_bridge_part(bp: PendingBridgePart) -> ValidationResult:
    errors: List[str] = []
    warnings: List[str] = []

    # Recursively validate contained elements
    for i, elem in enumerate(bp.elements):
        child = validate(elem)
        for e in child.errors:
            errors.append(f"PendingBridgePart '{bp.name}' element {i}: {e}")
        for w in child.warnings:
            warnings.append(f"PendingBridgePart '{bp.name}' element {i}: {w}")

    if bp.alignment is not None:
        child = _validate_alignment(bp.alignment)
        for e in child.errors:
            errors.append(f"PendingBridgePart '{bp.name}' alignment: {e}")
        for w in child.warnings:
            warnings.append(f"PendingBridgePart '{bp.name}' alignment: {w}")

    return ValidationResult(ok=len(errors) == 0, errors=errors, warnings=warnings)


@register_validator(PendingBridge)
def _validate_bridge(b: PendingBridge) -> ValidationResult:
    errors: List[str] = []
    warnings: List[str] = []

    if len(b.parts) == 0:
        errors.append(f"PendingBridge '{b.name}': must have at least one part")

    for i, part in enumerate(b.parts):
        child = _validate_bridge_part(part)
        for e in child.errors:
            errors.append(f"PendingBridge '{b.name}' part {i}: {e}")
        for w in child.warnings:
            warnings.append(f"PendingBridge '{b.name}' part {i}: {w}")

    if b.alignment is not None:
        child = _validate_alignment(b.alignment)
        for e in child.errors:
            errors.append(f"PendingBridge '{b.name}' alignment: {e}")
        for w in child.warnings:
            warnings.append(f"PendingBridge '{b.name}' alignment: {w}")

    return ValidationResult(ok=len(errors) == 0, errors=errors, warnings=warnings)


@register_validator(PendingSweptBeam)
def _validate_swept_beam(sb: PendingSweptBeam) -> ValidationResult:
    errors: List[str] = []
    warnings: List[str] = []

    # Path length — Line, Arc, and Path all expose .length as a property
    path = sb.path
    path_len = path.length

    if path_len < _MIN_LENGTH:
        errors.append(f"PendingSweptBeam '{sb.name}': path length must be > 0, got {path_len:.6f}")
    elif path_len < _WARN_SHORT:
        warnings.append(f"PendingSweptBeam '{sb.name}': path is very short ({path_len:.4f} m)")

    # Profile
    if len(sb.profile) < 3:
        errors.append(
            f"PendingSweptBeam '{sb.name}': profile must have at least 3 points, "
            f"got {len(sb.profile)}"
        )
    else:
        area = abs(_profile_area_2d(sb.profile))
        if area < _MIN_LENGTH**2:
            errors.append(f"PendingSweptBeam '{sb.name}': profile area is effectively zero")

    return ValidationResult(ok=len(errors) == 0, errors=errors, warnings=warnings)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate(pending: PendingElement) -> ValidationResult:
    """
    Validate a PendingElement and return a ValidationResult.

    Args:
        pending:  Any PendingElement subclass instance.

    Returns:
        ValidationResult with ``ok=True`` if no errors were found.
        Warnings are informational; they do not set ``ok=False``.

    Raises:
        TypeError: If the type is not recognised by any validator.
    """
    validator = ValidatorRegistry.get(type(pending))
    return validator(pending)
