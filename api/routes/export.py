"""
api.routes.export
=================

GET /sessions/{id}/ifc  → build the IFC from all pending elements, stream as download
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from api.deps import get_session
from api.state import SessionState
from ifckit import IfcModel
from ifckit.builders import default_registry
from ifckit.builders._geom import get_body_context
from ifckit.model import StoreyHandle

router = APIRouter(prefix="/sessions", tags=["export"])


@router.get(
    "/{session_id}/ifc",
    summary="Export session as IFC file",
    description=(
        "Builds the IFC model from all pending elements and returns the STEP-encoded "
        "`.ifc` file. The model is rebuilt from scratch on every call, so deleting "
        "elements before export is always reflected correctly."
    ),
    response_class=Response,
    responses={
        200: {
            "content": {"application/x-step": {}},
            "description": "STEP-encoded IFC file",
        }
    },
)
def export_ifc(state: SessionState = Depends(get_session)) -> Response:
    # Build a fresh IfcModel from scratch
    model = IfcModel(
        name=state.project_name,
        schema=state.schema,
        author=state.author,
    )

    # Add site — pass only explicitly set kwargs so library defaults stay active
    site_kwargs: dict = {"name": state.site_name}
    if state.site_description is not None:
        site_kwargs["description"] = state.site_description
    if state.site_latitude is not None:
        site_kwargs["latitude"] = state.site_latitude
    if state.site_longitude is not None:
        site_kwargs["longitude"] = state.site_longitude
    if state.site_elevation is not None:
        site_kwargs["elevation"] = state.site_elevation
    if state.site_location is not None:
        site_kwargs["location"] = state.site_location

    site = model.add_site(**site_kwargs)
    building = model.add_building(site, state.building_name)

    reg = default_registry()
    ctx = get_body_context(model.ifc_file)

    # Group elements by (storey_name, storey_elevation) to avoid duplicate storeys
    storey_map: dict[tuple[str, float], StoreyHandle] = {}

    _BUILDER_KEY: dict[str, str] = {
        "wall": "basic_wall",
        "slab": "basic_slab",
        "beam": "basic_beam",
        "column": "basic_column",
    }

    for rec in state.elements.values():
        key = (rec.storey_name, rec.storey_elevation)
        if key not in storey_map:
            storey_map[key] = model.add_storey(
                building,
                name=rec.storey_name,
                elevation=rec.storey_elevation,
            )
        storey_handle = storey_map[key]

        builder_key = _BUILDER_KEY.get(rec.element_type)
        if builder_key is None:
            raise ValueError(
                f"No builder registered for element_type '{rec.element_type}'. "
                "Supported: wall, slab, beam, column."
            )
        reg.get(builder_key).build(
            model.ifc_file, rec.pending, storey_handle.entity, ctx
        )

    ifc_bytes = model.to_string().encode("utf-8")
    filename = f"{state.project_name.replace(' ', '_')}.ifc"

    return Response(
        content=ifc_bytes,
        media_type="application/x-step",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
