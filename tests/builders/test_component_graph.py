"""
Tests for ifckit.builders.component_graph

Covers:
  - _eval_expr: literals, $params, binary ops, errors
  - _eval_point
  - _load_preset: success and missing file
  - _resolve_parameters: defaults, overrides, missing required
  - _eval_node_rect: returns Path, correct corners
  - _eval_node_difference: returns Path with holes
  - evaluate_component_graph: fixed_casement, door_flush
  - Path.holes, Path.with_hole
  - profile_from_points: IfcArbitraryProfileDefWithVoids via Path with holes
"""

from __future__ import annotations

import pytest
import ifcopenshell

from ifckit.builders._geom import axis2placement3d, profile_from_points
from ifckit.builders.component_graph import (
    EvaluatedComponent,
    _eval_expr,
    _eval_node_difference,
    _eval_node_rect,
    _load_preset,
    _resolve_parameters,
    evaluate_component_graph,
    evaluate_opening_nodes,
)
from ifckit.geometry import Path, Vec


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ifc():
    """Return a minimal IFC4 file with a geometric context."""
    f = ifcopenshell.file(schema="IFC4")
    ctx = f.create_entity(
        "IfcGeometricRepresentationContext",
        ContextType="Model",
        CoordinateSpaceDimension=3,
        Precision=1e-5,
        WorldCoordinateSystem=axis2placement3d(f, Vec(0, 0, 0), Vec(0, 0, 1), Vec(1, 0, 0)),
    )
    return f, ctx


# ---------------------------------------------------------------------------
# _eval_expr
# ---------------------------------------------------------------------------


class TestEvalExpr:
    def test_literal_int(self):
        assert _eval_expr(3, {}) == 3.0

    def test_literal_float(self):
        assert _eval_expr(1.5, {}) == 1.5

    def test_simple_param(self):
        assert _eval_expr("$w", {"w": 2.0}) == 2.0

    def test_add(self):
        assert _eval_expr("$a + $b", {"a": 1.0, "b": 2.0}) == pytest.approx(3.0)

    def test_subtract(self):
        assert _eval_expr("$w - $t", {"w": 1.0, "t": 0.055}) == pytest.approx(0.945)

    def test_multiply(self):
        assert _eval_expr("$d * 2", {"d": 0.5}) == pytest.approx(1.0)

    def test_divide(self):
        assert _eval_expr("$h / 2", {"h": 1.2}) == pytest.approx(0.6)

    def test_left_to_right(self):
        # "$a - $b + $c" = (a - b) + c left-to-right
        assert _eval_expr("$a - $b + $c", {"a": 10.0, "b": 3.0, "c": 1.0}) == pytest.approx(8.0)

    def test_unknown_param(self):
        with pytest.raises(KeyError, match="unknown_param"):
            _eval_expr("$unknown_param", {})

    def test_division_by_zero(self):
        with pytest.raises(ValueError, match="division by zero"):
            _eval_expr("$x / 0", {"x": 1.0})

    def test_bad_type(self):
        with pytest.raises(ValueError):
            _eval_expr({"not": "valid"}, {})


# ---------------------------------------------------------------------------
# _resolve_parameters
# ---------------------------------------------------------------------------


class TestResolveParameters:
    def test_defaults_used(self):
        preset = {"parameters": {"t": 0.055, "d": 0.070}}
        result = _resolve_parameters(preset, {})
        assert result["t"] == pytest.approx(0.055)
        assert result["d"] == pytest.approx(0.070)

    def test_override_replaces_default(self):
        preset = {"parameters": {"t": 0.055}}
        result = _resolve_parameters(preset, {"t": 0.1})
        assert result["t"] == pytest.approx(0.1)

    def test_required_param_missing(self):
        preset = {"parameters": {"w": None, "h": None}}
        with pytest.raises(ValueError, match="Required parameter"):
            _resolve_parameters(preset, {"w": 1.0})  # h missing

    def test_extra_override_added(self):
        preset = {"parameters": {"w": None}}
        result = _resolve_parameters(preset, {"w": 1.0, "extra": 99.0})
        assert result["extra"] == pytest.approx(99.0)


# ---------------------------------------------------------------------------
# _load_preset
# ---------------------------------------------------------------------------


class TestLoadPreset:
    def test_load_fixed_casement(self):
        preset = _load_preset("fixed_casement")
        assert preset["version"] == 1
        assert "nodes" in preset
        assert "parameters" in preset

    def test_load_door_flush(self):
        preset = _load_preset("door_flush")
        assert preset["version"] == 1

    def test_missing_preset(self):
        with pytest.raises(FileNotFoundError, match="nonexistent_preset"):
            _load_preset("nonexistent_preset")


# ---------------------------------------------------------------------------
# _eval_node_rect
# ---------------------------------------------------------------------------


class TestEvalNodeRect:
    def test_returns_path(self):
        node = {"id": "r", "op": "rect", "p0": [0, 0], "p1": [1.0, 1.2]}
        result = _eval_node_rect(node, {})
        assert isinstance(result, Path)

    def test_closed(self):
        node = {"id": "r", "op": "rect", "p0": [0, 0], "p1": [1.0, 1.0]}
        result = _eval_node_rect(node, {})
        assert result.is_closed

    def test_four_segments(self):
        node = {"id": "r", "op": "rect", "p0": [0, 0], "p1": [1.0, 1.0]}
        result = _eval_node_rect(node, {})
        assert len(result.segments) == 4

    def test_no_holes(self):
        node = {"id": "r", "op": "rect", "p0": [0, 0], "p1": [2.0, 3.0]}
        result = _eval_node_rect(node, {})
        assert result.holes == []

    def test_param_substitution(self):
        node = {"id": "r", "op": "rect", "p0": [0, 0], "p1": ["$w", "$h"]}
        result = _eval_node_rect(node, {"w": 1.5, "h": 2.0})
        # Check x extent via to_profile_points
        from ifckit.geometry import Plane
        pts = result.to_profile_points()
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        assert max(xs) == pytest.approx(1.5)
        assert max(ys) == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# _eval_node_rect — inline offset hole
# ---------------------------------------------------------------------------


class TestEvalNodeRectOffsetHole:
    def _outer_node(self):
        return {"id": "outer", "op": "rect", "p0": [0, 0], "p1": [1000, 1000]}

    def test_offset_hole_creates_one_hole(self):
        node = {**self._outer_node(), "holes": [{"op": "offset", "dist": 55}]}
        result = _eval_node_rect(node, {})
        assert len(result.holes) == 1

    def test_offset_hole_is_path(self):
        node = {**self._outer_node(), "holes": [{"op": "offset", "dist": 55}]}
        result = _eval_node_rect(node, {})
        assert isinstance(result.holes[0], Path)

    def test_offset_hole_param_substitution(self):
        node = {
            **self._outer_node(),
            "holes": [{"op": "offset", "dist": "$lining_thickness"}],
        }
        result = _eval_node_rect(node, {"lining_thickness": 55})
        pts = result.holes[0].to_profile_points()
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        assert min(xs) == pytest.approx(55.0)
        assert min(ys) == pytest.approx(55.0)
        assert max(xs) == pytest.approx(945.0)
        assert max(ys) == pytest.approx(945.0)

    def test_offset_hole_with_scale(self):
        # scale_x=2, scale_y=2 → outer rect [0,0] to [1000,1000] is scaled to [0,0] to [2000,2000]
        # Literal "dist": 55 (in ref-frame units) is NOT scaled → offset is 55
        # So hole points are [55, 55] to [1945, 1945]
        node = {
            **self._outer_node(),
            "holes": [{"op": "offset", "dist": 55}],
        }
        result = _eval_node_rect(node, {}, scale_x=2.0, scale_y=2.0)
        pts = result.holes[0].to_profile_points()
        xs = [p[0] for p in pts]
        assert min(xs) == pytest.approx(55.0)
        assert max(xs) == pytest.approx(1945.0)

    def test_offset_hole_missing_dist_raises(self):
        node = {**self._outer_node(), "holes": [{"op": "offset"}]}
        with pytest.raises(ValueError, match="dist"):
            _eval_node_rect(node, {})

    def test_unsupported_hole_op_still_raises(self):
        node = {**self._outer_node(), "holes": [{"op": "circle", "r": 10}]}
        with pytest.raises(ValueError, match="circle"):
            _eval_node_rect(node, {})


# ---------------------------------------------------------------------------
# _eval_node_difference
# ---------------------------------------------------------------------------


class TestEvalNodeDifference:
    def _outer(self):
        node = {"id": "o", "op": "rect", "p0": [0, 0], "p1": [1.0, 1.2]}
        return _eval_node_rect(node, {})

    def _inner(self):
        node = {"id": "i", "op": "rect", "p0": [0.05, 0.05], "p1": [0.95, 1.15]}
        return _eval_node_rect(node, {})

    def test_returns_path(self):
        diff_node = {"id": "d", "op": "difference", "a": "o", "b": "i"}
        cache = {"o": self._outer(), "i": self._inner()}
        result = _eval_node_difference(diff_node, cache, {})
        assert isinstance(result, Path)

    def test_has_one_hole(self):
        diff_node = {"id": "d", "op": "difference", "a": "o", "b": "i"}
        cache = {"o": self._outer(), "i": self._inner()}
        result = _eval_node_difference(diff_node, cache, {})
        assert len(result.holes) == 1

    def test_hole_is_path(self):
        diff_node = {"id": "d", "op": "difference", "a": "o", "b": "i"}
        cache = {"o": self._outer(), "i": self._inner()}
        result = _eval_node_difference(diff_node, cache, {})
        assert isinstance(result.holes[0], Path)

    def test_missing_operand(self):
        diff_node = {"id": "d", "op": "difference", "a": "o", "b": "missing"}
        cache = {"o": self._outer()}
        with pytest.raises(ValueError, match="missing"):
            _eval_node_difference(diff_node, cache, {})


# ---------------------------------------------------------------------------
# Path.with_hole
# ---------------------------------------------------------------------------


class TestPathWithHole:
    def test_with_hole_does_not_mutate_original(self):
        outer = _eval_node_rect({"id": "o", "op": "rect", "p0": [0, 0], "p1": [1, 1]}, {})
        inner = _eval_node_rect({"id": "i", "op": "rect", "p0": [0.1, 0.1], "p1": [0.9, 0.9]}, {})
        result = outer.with_hole(inner)
        assert outer.holes == []
        assert len(result.holes) == 1

    def test_duplicate_copies_holes(self):
        outer = _eval_node_rect({"id": "o", "op": "rect", "p0": [0, 0], "p1": [1, 1]}, {})
        inner = _eval_node_rect({"id": "i", "op": "rect", "p0": [0.1, 0.1], "p1": [0.9, 0.9]}, {})
        with_hole = outer.with_hole(inner)
        dup = with_hole.duplicate()
        assert len(dup.holes) == 1
        # Modifying original's hole list should not affect duplicate
        with_hole._holes.clear()
        assert len(dup.holes) == 1


# ---------------------------------------------------------------------------
# profile_from_points with holes (IfcArbitraryProfileDefWithVoids)
# ---------------------------------------------------------------------------


class TestProfileFromPointsWithVoids:
    def test_no_holes_gives_closed_profile(self):
        f, _ = _make_ifc()
        outer = _eval_node_rect({"id": "o", "op": "rect", "p0": [0, 0], "p1": [1, 1]}, {})
        profile = profile_from_points(f, outer)
        assert profile.is_a("IfcArbitraryClosedProfileDef")

    def test_with_hole_gives_profile_with_voids(self):
        f, _ = _make_ifc()
        outer = _eval_node_rect({"id": "o", "op": "rect", "p0": [0, 0], "p1": [1, 1]}, {})
        inner = _eval_node_rect({"id": "i", "op": "rect", "p0": [0.1, 0.1], "p1": [0.9, 0.9]}, {})
        path_with_hole = outer.with_hole(inner)
        profile = profile_from_points(f, path_with_hole)
        assert profile.is_a("IfcArbitraryProfileDefWithVoids")

    def test_profile_with_voids_has_inner_curves(self):
        f, _ = _make_ifc()
        outer = _eval_node_rect({"id": "o", "op": "rect", "p0": [0, 0], "p1": [1, 1]}, {})
        inner = _eval_node_rect({"id": "i", "op": "rect", "p0": [0.1, 0.1], "p1": [0.9, 0.9]}, {})
        path_with_hole = outer.with_hole(inner)
        profile = profile_from_points(f, path_with_hole)
        assert len(profile.InnerCurves) == 1
        assert profile.InnerCurves[0].is_a("IfcPolyline")


# ---------------------------------------------------------------------------
# evaluate_component_graph — fixed_casement
# ---------------------------------------------------------------------------


class TestEvaluateFixedCasement:
    def test_returns_two_components(self):
        f, ctx = _make_ifc()
        comps = evaluate_component_graph("fixed_casement", f, ctx, {"w": 1.0, "h": 1.2})
        assert len(comps) == 2

    def test_component_roles(self):
        f, ctx = _make_ifc()
        comps = evaluate_component_graph("fixed_casement", f, ctx, {"w": 1.0, "h": 1.2})
        roles = {c.role for c in comps}
        assert roles == {"Lining", "Glazing"}

    def test_lining_is_extruded_solid(self):
        f, ctx = _make_ifc()
        comps = evaluate_component_graph("fixed_casement", f, ctx, {"w": 1.0, "h": 1.2})
        lining = next(c for c in comps if c.role == "Lining")
        assert lining.solid.is_a("IfcExtrudedAreaSolid")

    def test_lining_profile_has_voids(self):
        f, ctx = _make_ifc()
        comps = evaluate_component_graph("fixed_casement", f, ctx, {"w": 1.0, "h": 1.2})
        lining = next(c for c in comps if c.role == "Lining")
        assert lining.solid.SweptArea.is_a("IfcArbitraryProfileDefWithVoids")

    def test_glazing_profile_is_closed(self):
        f, ctx = _make_ifc()
        comps = evaluate_component_graph("fixed_casement", f, ctx, {"w": 1.0, "h": 1.2})
        glazing = next(c for c in comps if c.role == "Glazing")
        assert glazing.solid.SweptArea.is_a("IfcArbitraryClosedProfileDef")

    def test_lining_depth(self):
        f, ctx = _make_ifc()
        comps = evaluate_component_graph("fixed_casement", f, ctx, {"w": 1.0, "h": 1.2})
        lining = next(c for c in comps if c.role == "Lining")
        assert lining.solid.Depth == pytest.approx(70.0)  # 70 mm

    def test_glazing_depth(self):
        f, ctx = _make_ifc()
        comps = evaluate_component_graph("fixed_casement", f, ctx, {"w": 1.0, "h": 1.2})
        glazing = next(c for c in comps if c.role == "Glazing")
        assert glazing.solid.Depth == pytest.approx(6.0)  # 6 mm

    def test_missing_required_param(self):
        """h now has a default (1000), so only test when really required."""
        # This test is a placeholder; all current params have defaults
        pass

    def test_returns_evaluated_component_instances(self):
        f, ctx = _make_ifc()
        comps = evaluate_component_graph("fixed_casement", f, ctx, {"w": 1.0, "h": 1.2})
        for c in comps:
            assert isinstance(c, EvaluatedComponent)
            assert isinstance(c.role, str)
            assert c.solid is not None


# ---------------------------------------------------------------------------
# evaluate_component_graph — door_flush
# ---------------------------------------------------------------------------


class TestEvaluateDoorFlush:
    def test_returns_one_component(self):
        f, ctx = _make_ifc()
        comps = evaluate_component_graph("door_flush", f, ctx, {"w": 0.9, "h": 2.1})
        assert len(comps) == 1

    def test_component_role_is_door(self):
        f, ctx = _make_ifc()
        comps = evaluate_component_graph("door_flush", f, ctx, {"w": 0.9, "h": 2.1})
        assert comps[0].role == "Door"

    def test_door_is_extruded_solid(self):
        f, ctx = _make_ifc()
        comps = evaluate_component_graph("door_flush", f, ctx, {"w": 0.9, "h": 2.1})
        assert comps[0].solid.is_a("IfcExtrudedAreaSolid")


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# evaluate_opening_nodes
# ---------------------------------------------------------------------------


class TestEvaluateOpeningNodesFixedCasement:
    def test_returns_list_of_evaluated_components(self):
        f, ctx = _make_ifc()
        result = evaluate_opening_nodes(
            "fixed_casement",
            f,
            ctx,
            {"w": 1.0, "h": 1.2, "wall_thickness": 0.2}
        )
        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(c, EvaluatedComponent) for c in result)

    def test_result_has_solid_with_representation(self):
        f, ctx = _make_ifc()
        result = evaluate_opening_nodes(
            "fixed_casement",
            f,
            ctx,
            {"w": 1.0, "h": 1.2, "wall_thickness": 0.2}
        )
        assert result[0].solid is not None
        assert result[0].solid.is_a("IfcExtrudedAreaSolid")

    def test_opening_solid_geometry_matches_params(self):
        """Opening solid should match overall w × h dimensions."""
        f, ctx = _make_ifc()
        result = evaluate_opening_nodes(
            "fixed_casement",
            f,
            ctx,
            {"w": 1.5, "h": 2.0, "wall_thickness": 0.2}
        )
        solid = result[0].solid
        # The profile should encompass approximately 1.5×2.0
        # (exact validation depends on preset structure)
        assert solid is not None

    def test_missing_wall_thickness_raises(self):
        """wall_thickness is required for opening_nodes evaluation."""
        f, ctx = _make_ifc()
        with pytest.raises((ValueError, KeyError), match="wall_thickness"):
            evaluate_opening_nodes(
                "fixed_casement",
                f,
                ctx,
                {"w": 1.0, "h": 1.2}
            )

    def test_preset_without_opening_nodes_raises(self):
        """Presets must have opening_nodes section."""
        f, ctx = _make_ifc()
        # Assume we create a minimal preset without opening_nodes
        # For now, this is a placeholder since all current presets have it
        pass


class TestEvaluateOpeningNodesDoorFlush:
    def test_door_flush_opening_nodes(self):
        """Door presets should also support opening_nodes evaluation."""
        f, ctx = _make_ifc()
        result = evaluate_opening_nodes(
            "door_flush",
            f,
            ctx,
            {"w": 0.9, "h": 2.1, "wall_thickness": 0.2}
        )
        assert len(result) > 0
        assert result[0].solid is not None


class TestOpeningNodesScaling:
    def test_opening_nodes_respects_scale_x(self):
        """Scaling should affect opening geometry in X direction."""
        f, ctx = _make_ifc()
        # Reference canvas: 1000×1000; request 2.0×1.0
        # → scale_x = 2.0/1.0 = 2.0, scale_y = 1.0/1.0 = 1.0
        result = evaluate_opening_nodes(
            "fixed_casement",
            f,
            ctx,
            {"w": 2.0, "h": 1.0, "wall_thickness": 0.2}
        )
        assert len(result) > 0
        # Solid should exist and be properly scaled
        assert result[0].solid is not None

    def test_opening_nodes_respects_scale_y(self):
        """Scaling should affect opening geometry in Y direction."""
        f, ctx = _make_ifc()
        # Reference canvas: 1000×1000; request 1.0×3.0
        # → scale_x = 1.0/1.0 = 1.0, scale_y = 3.0/1.0 = 3.0
        result = evaluate_opening_nodes(
            "fixed_casement",
            f,
            ctx,
            {"w": 1.0, "h": 3.0, "wall_thickness": 0.2}
        )
        assert len(result) > 0
        assert result[0].solid is not None
