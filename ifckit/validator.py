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
from typing import Callable, Dict, List, Type

from ifckit.elements.base import PendingElement
from ifckit.elements.bridge import (
    AlignmentSegment,
    PendingAlignment,
    PendingBridge,
    PendingBridgePart,
)
from ifckit.elements.building import PendingSlab, PendingWall
from ifckit.elements.opening import PendingDoor, PendingOpening, PendingWindow
from ifckit.elements.registry import ElementRegistry
from ifckit.elements.space import PendingSpace
from ifckit.elements.structural import (
    PendingBeam,
    PendingColumn,
    PendingRevolvedBeam,
    PendingTaperedExtrusion,
)
from ifckit.elements.wall_graph import PendingWallGraph
from ifckit.geometry import Vec

# ---------------------------------------------------------------------------
# Validator registry with auto-registration
# ---------------------------------------------------------------------------


class ValidatorRegistry:
    """Registry for element validators with decorator-based auto-registration."""

    _validators: Dict[Type[PendingElement], Callable[..., ValidationResult]] = {}
    # Secondary mapping by element_type string to validator callable. This
    # helps when modules are reloaded and class objects differ between
    # importers — matching by element_type string remains stable.
    _validators_by_type: Dict[str, Callable[..., ValidationResult]] = {}

    @classmethod
    def register(
        cls,
        element_cls: Type[PendingElement],
    ) -> Callable[[Callable[..., ValidationResult]], Callable[..., ValidationResult]]:
        """Decorator to register a validator for a PendingElement subclass."""

        def decorator(func: Callable[..., ValidationResult]) -> Callable[..., ValidationResult]:
            cls._validators[element_cls] = func
            # Also register by element_type string when available
            elem_type = getattr(element_cls, "element_type", None)
            if elem_type:
                cls._validators_by_type[elem_type] = func
            return func

        return decorator

    @classmethod
    def get(cls, element_cls: Type[PendingElement]) -> Callable[..., ValidationResult]:
        """Get validator for an element class."""
        # Exact match
        if element_cls in cls._validators:
            return cls._validators[element_cls]

        # Fallback 1: match by element_type attribute (robust across reloads)
        elem_type = getattr(element_cls, "element_type", None)
        if elem_type is not None:
            if elem_type in cls._validators_by_type:
                return cls._validators_by_type[elem_type]
            # older registrations may not have populated the by_type map,
            # fall back to scanning registered classes
            for reg_cls, validator in cls._validators.items():
                if getattr(reg_cls, "element_type", None) == elem_type:
                    return validator

        # Fallback 2: match by class name (handles duplicate class objects from reloads)
        for reg_cls, validator in cls._validators.items():
            if reg_cls.__name__ == element_cls.__name__:
                return validator

        raise TypeError(f"No validator registered for {element_cls.__name__}")

    @classmethod
    def has(cls, element_cls: Type[PendingElement]) -> bool:
        """Check if validator exists for element class."""
        if element_cls in cls._validators:
            return True
        elem_type = getattr(element_cls, "element_type", None)
        if elem_type is not None:
            if elem_type in cls._validators_by_type:
                return True
            for reg_cls in cls._validators:
                if getattr(reg_cls, "element_type", None) == elem_type:
                    return True
        for reg_cls in cls._validators:
            if reg_cls.__name__ == element_cls.__name__:
                return True
        return False

    @classmethod
    def items(cls):
        """Iterate (element_cls, validator_fn) pairs — use instead of _validators.items()."""
        return cls._validators.items()


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


@register_validator(PendingSpace)
def _validate_space(s: PendingSpace) -> ValidationResult:
    errors: List[str] = []
    warnings: List[str] = []

    if len(s.footprint) < 3:
        errors.append(
            f"PendingSpace '{s.name}': footprint must have at least 3 points, "
            f"got {len(s.footprint)}"
        )
    else:
        area = abs(_profile_area_2d(s.footprint))
        if area < _MIN_LENGTH**2:
            errors.append(f"PendingSpace '{s.name}': footprint area is effectively zero")

    if s.height <= 0.0:
        errors.append(f"PendingSpace '{s.name}': height must be > 0, got {s.height}")
    elif s.height < _WARN_SHORT:
        warnings.append(f"PendingSpace '{s.name}': height is very small ({s.height:.4f} m)")

    return ValidationResult(ok=len(errors) == 0, errors=errors, warnings=warnings)


def _validate_extruded_element(elem, label: str) -> tuple:
    """Shared checks for beam/column: axis length + profile area."""
    errors: List[str] = []
    warnings: List[str] = []

    axis_len = elem.axis.length
    if axis_len < _MIN_LENGTH:
        errors.append(f"{label} '{elem.name}': axis length must be > 0, got {axis_len:.6f}")
    elif axis_len < _WARN_SHORT:
        warnings.append(f"{label} '{elem.name}': axis is very short ({axis_len:.4f} m)")

    if len(elem.profile) < 3:
        errors.append(
            f"{label} '{elem.name}': profile must have at least 3 points, got {len(elem.profile)}"
        )
    else:
        area = abs(_profile_area_2d(elem.profile))
        if area < _MIN_LENGTH**2:
            errors.append(f"{label} '{elem.name}': profile area is effectively zero")

    return errors, warnings


@register_validator(PendingBeam)
def _validate_beam(b: PendingBeam) -> ValidationResult:
    errors, warnings = _validate_extruded_element(b, "PendingBeam")
    return ValidationResult(ok=len(errors) == 0, errors=errors, warnings=warnings)


@register_validator(PendingColumn)
def _validate_column(c: PendingColumn) -> ValidationResult:
    errors, warnings = _validate_extruded_element(c, "PendingColumn")
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


# ---------------------------------------------------------------------------
# Opening / door / window validators
# ---------------------------------------------------------------------------


@register_validator(PendingOpening)
def _validate_opening(o: PendingOpening) -> ValidationResult:
    errors: List[str] = []
    warnings: List[str] = []

    # Dimensions already enforced by constructor, but re-validate defensively.
    if o.width <= 0:
        errors.append(f"width must be positive, got {o.width}")
    if o.height <= 0:
        errors.append(f"height must be positive, got {o.height}")

    # Warn on unusual dimensions (< 10 cm or > 10 m).
    if o.width < 0.1:
        warnings.append(f"opening width {o.width:.3f} m is unusually narrow (< 0.1 m)")
    if o.height < 0.1:
        warnings.append(f"opening height {o.height:.3f} m is unusually short (< 0.1 m)")
    if o.width > 10.0:
        warnings.append(f"opening width {o.width:.3f} m is unusually wide (> 10 m)")
    if o.height > 10.0:
        warnings.append(f"opening height {o.height:.3f} m is unusually tall (> 10 m)")

    return ValidationResult(ok=len(errors) == 0, errors=errors, warnings=warnings)


@register_validator(PendingDoor)
def _validate_door(d: PendingDoor) -> ValidationResult:
    errors: List[str] = []
    warnings: List[str] = []

    if d.overall_width <= 0:
        errors.append(f"overall_width must be positive, got {d.overall_width}")
    if d.overall_height <= 0:
        errors.append(f"overall_height must be positive, got {d.overall_height}")

    if d.overall_width < 0.3:
        warnings.append(f"door width {d.overall_width:.3f} m is unusually narrow (< 0.3 m)")
    if d.overall_height < 1.5:
        warnings.append(f"door height {d.overall_height:.3f} m is unusually short (< 1.5 m)")

    return ValidationResult(ok=len(errors) == 0, errors=errors, warnings=warnings)


@register_validator(PendingWindow)
def _validate_window(w: PendingWindow) -> ValidationResult:
    errors: List[str] = []
    warnings: List[str] = []

    if w.overall_width <= 0:
        errors.append(f"overall_width must be positive, got {w.overall_width}")
    if w.overall_height <= 0:
        errors.append(f"overall_height must be positive, got {w.overall_height}")

    if w.overall_width < 0.1:
        warnings.append(f"window width {w.overall_width:.3f} m is unusually narrow (< 0.1 m)")
    if w.overall_height < 0.1:
        warnings.append(f"window height {w.overall_height:.3f} m is unusually short (< 0.1 m)")

    return ValidationResult(ok=len(errors) == 0, errors=errors, warnings=warnings)


@register_validator(PendingWallGraph)
def _validate_wall_graph(wg: PendingWallGraph) -> ValidationResult:
    errors: List[str] = []
    warnings: List[str] = []
    if len(wg.vertices) < 2:
        errors.append(f"wall_graph '{wg.name}': need at least 2 vertices, got {len(wg.vertices)}")
    if not wg.edges:
        errors.append(f"wall_graph '{wg.name}': no edges defined")
    if wg.thickness <= 0:
        errors.append(f"wall_graph '{wg.name}': thickness must be > 0, got {wg.thickness}")
    if wg.height <= 0:
        errors.append(f"wall_graph '{wg.name}': height must be > 0, got {wg.height}")
    return ValidationResult(ok=len(errors) == 0, errors=errors, warnings=warnings)


@register_validator(PendingTaperedExtrusion)
def _validate_tapered(t: PendingTaperedExtrusion) -> ValidationResult:
    errors: List[str] = []
    warnings: List[str] = []

    if len(t.start_profile) < 3:
        errors.append(
            f"PendingTaperedExtrusion '{t.name}': start_profile must have at least 3 points, "
            f"got {len(t.start_profile)}"
        )

    if len(t.start_profile) != len(t.end_profile):
        errors.append(
            f"PendingTaperedExtrusion '{t.name}': start_profile ({len(t.start_profile)} pts) "
            f"and end_profile ({len(t.end_profile)} pts) must have equal point count"
        )

    area = abs(_profile_area_2d(t.start_profile))
    if area < _MIN_LENGTH**2:
        errors.append(f"PendingTaperedExtrusion '{t.name}': start profile area is effectively zero")

    if t.height <= 0.0:
        errors.append(f"PendingTaperedExtrusion '{t.name}': height must be > 0, got {t.height}")
    elif t.height < _WARN_SHORT:
        warnings.append(
            f"PendingTaperedExtrusion '{t.name}': height is very small ({t.height:.4f} m)"
        )

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
    try:
        validator = ValidatorRegistry.get(type(pending))
        return validator(pending)
    except TypeError:
        # Best-effort fallback: try to match by element_type or class name.
        pending_cls = type(pending)
        elem_type = getattr(pending_cls, "element_type", None)

        # Try matching by element_type via ElementRegistry to get the canonical class
        if elem_type is not None:
            try:
                canonical = ElementRegistry.get(elem_type)
                # If we can get a validator for the canonical class, use it
                if ValidatorRegistry.has(canonical):
                    validator = ValidatorRegistry.get(canonical)
                    return validator(pending)
            except KeyError:
                # element type not in ElementRegistry — fall through to scanning
                pass

        for reg_cls, validator in ValidatorRegistry.items():
            if elem_type is not None and getattr(reg_cls, "element_type", None) == elem_type:
                return validator(pending)
            if reg_cls.__name__ == pending_cls.__name__:
                return validator(pending)

        # Nothing found — provide helpful error listing registered validators
        registered = [
            f"{c.__name__} (type={getattr(c, 'element_type', None)!r})"
            for c, _ in ValidatorRegistry.items()
        ]
        raise TypeError(
            f"No validator registered for {pending_cls.__name__}. Available: {registered}"
        )
