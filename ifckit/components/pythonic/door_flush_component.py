"""
DoorFlush Component
===================

Generative DoorFlush component - 3-sided frame door with glazing.
This is the Pythonic alternative to door_flush.json.

Creates:
- Lining: 3-sided frame with door opening + top/side glazing
- Panel: Door leaf
- Glazing: Top and side light glass

Uses reference Plane:
- Profile drawn in local XY plane
- Extrudes in local -Z direction (into wall)
"""

from __future__ import annotations

from ifckit.builders._geom import extrude_profile, profile_from_points
from ifckit.components import EvaluatedComponent, WindowComponent, component
from ifckit.geometry import Plane

# Material definitions (same structure as JSON)
ALUMINUM_FRAME = {
    "color": {"r": 0.8, "g": 0.8, "b": 0.8},
    "transparency": 0.0,
    "name": "Aluminum frame",
}

DOOR_PANEL = {"color": {"r": 0.9, "g": 0.0, "b": 0.0}, "transparency": 0.0, "name": "Door panel"}

CLEAR_GLASS = {"color": {"r": 0.9, "g": 0.95, "b": 1.0}, "transparency": 0.8, "name": "Clear glass"}


@component("door_flush_component")
class DoorFlushComponent(WindowComponent):
    """3-sided frame door with top and side glazing."""

    name = "door_flush_component"

    def build(
        self,
        ifc_file,
        plane: Plane,
        width: float,
        height: float,
        params: dict[str, float],
    ) -> list[EvaluatedComponent]:
        """Build DoorFlush geometry.

        Args:
            ifc_file: Active IFC file
            plane: Reference plane (local XY defines profile plane)
            width: Overall width (typically from occurrence)
            height: Overall height (from occurrence)
            params: Resolved parameters

        Returns:
            List of 4 EvaluatedComponents: Lining, Panel, TopGlazing, SideGlazing
        """
        # Extract parameters with defaults
        lining_thickness = params.get("lining_thickness", 50)
        lining_depth = params.get("lining_depth", 100)
        door_width = params.get("door_width", 900)
        door_height = params.get("door_height", 2100)
        door_depth = params.get("door_depth", 50)
        panel_depth = params.get("panel_depth", 10)

        # Convenience
        origin = plane.origin
        x = plane.x_axis
        y = plane.y_axis
        z = plane.z_axis

        # === 1. LINING: Individual frame segments ===
        # For simplicity, we create separate lining segments

        # Door opening origin
        # Create separate solids for each element

        components: list[EvaluatedComponent] = []

        # === LINING: Extrude frame profile with hole ===
        # Since we need the full frame, create individual lining segments
        # Bottom sill
        sill_profile = profile_from_points(ifc_file, [origin, origin + x * width], closed=False)
        sill_solid = extrude_profile(
            ifc_file,
            sill_profile,
            depth=lining_depth,
            extrude_direction=tuple(-z),
        )
        components.append(
            EvaluatedComponent(
                solid=sill_solid,
                role="Lining",
                material=ALUMINUM_FRAME,
            )
        )

        # Left side
        left_profile = profile_from_points(
            ifc_file,
            [
                origin,
                origin + y * door_height,
            ],
            closed=False,
        )
        left_solid = extrude_profile(
            ifc_file,
            left_profile,
            depth=lining_depth,
            extrude_direction=tuple(-z),
        )
        components.append(
            EvaluatedComponent(
                solid=left_solid,
                role="Lining",
                material=ALUMINUM_FRAME,
            )
        )

        # Right side
        right_origin = origin + x * (lining_thickness + door_width)
        right_profile = profile_from_points(
            ifc_file,
            [
                right_origin,
                right_origin + y * door_height,
            ],
            closed=False,
        )
        right_solid = extrude_profile(
            ifc_file,
            right_profile,
            depth=lining_depth,
            extrude_direction=tuple(-z),
        )
        components.append(
            EvaluatedComponent(
                solid=right_solid,
                role="Lining",
                material=ALUMINUM_FRAME,
            )
        )

        # Top (above door opening)
        if height > door_height:
            top_origin = origin + y * door_height
            top_profile = profile_from_points(
                ifc_file,
                [
                    top_origin,
                    top_origin + x * width,
                ],
                closed=False,
            )
            top_solid = extrude_profile(
                ifc_file,
                top_profile,
                depth=lining_depth,
                extrude_direction=tuple(-z),
            )
            components.append(
                EvaluatedComponent(
                    solid=top_solid,
                    role="Lining",
                    material=ALUMINUM_FRAME,
                )
            )

        # === DOOR PANEL ===
        panel_origin = origin + x * lining_thickness + z * (lining_depth - door_depth)
        panel_profile = profile_from_points(
            ifc_file,
            [
                panel_origin,
                panel_origin + x * door_width,
                panel_origin + x * door_width + y * door_height,
                panel_origin + y * door_height,
            ],
            closed=True,
        )
        panel_solid = extrude_profile(
            ifc_file,
            panel_profile,
            depth=door_depth,
            extrude_direction=tuple(z),  # Outward from wall
        )
        components.append(
            EvaluatedComponent(
                solid=panel_solid,
                role="Panel",
                material=DOOR_PANEL,
            )
        )

        # === TOP GLAZING ===
        # Check if there's space above door
        top_glass_height = height - door_height - lining_thickness
        if top_glass_height > 0:
            glass_origin = origin + x * lining_thickness + y * (door_height + lining_thickness)
            glass_profile = profile_from_points(
                ifc_file,
                [
                    glass_origin,
                    glass_origin + x * door_width,
                    glass_origin + x * door_width + y * top_glass_height,
                    glass_origin + y * top_glass_height,
                ],
                closed=True,
            )
            glass_solid = extrude_profile(
                ifc_file,
                glass_profile,
                depth=panel_depth,
                extrude_direction=tuple(-z),
            )
            components.append(
                EvaluatedComponent(
                    solid=glass_solid,
                    role="Glazing",
                    material=CLEAR_GLASS,
                )
            )

        # === SIDE GLAZING ===
        # Check if there's space on the side
        side_glass_space = width - door_width - lining_thickness * 2
        if side_glass_space > 0:
            side_origin = (
                origin
                + x * (lining_thickness + door_width + lining_thickness)
                + y * lining_thickness
            )
            side_profile = profile_from_points(
                ifc_file,
                [
                    side_origin,
                    side_origin + x * side_glass_space,
                    side_origin + x * side_glass_space + y * (height - lining_thickness),
                    side_origin + y * (height - lining_thickness),
                ],
                closed=True,
            )
            side_solid = extrude_profile(
                ifc_file,
                side_profile,
                depth=panel_depth,
                extrude_direction=tuple(-z),
            )
            components.append(
                EvaluatedComponent(
                    solid=side_solid,
                    role="Glazing",
                    material=CLEAR_GLASS,
                )
            )

        return components


# Auto-register when module is imported
DoorFlushComponent.register()
