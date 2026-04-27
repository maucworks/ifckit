"""
fastapi_adapter.py
==================

Shows how to expose ifckit as a FastAPI HTTP endpoint.

A client POSTs a JSON building description and receives a plain-text IFC
file in the response body.  No file is written to disk — ``to_string()``
produces the STEP payload in memory.

Install extras::

    pip install fastapi uvicorn[standard]

Run::

    uvicorn examples.fastapi_adapter:app --reload
    # → http://127.0.0.1:8000

Then POST a building::

    curl -X POST http://127.0.0.1:8000/building \\
         -H "Content-Type: application/json" \\
         -d @examples/sample_building_request.json \\
         --output building.ifc

Or use the auto-generated docs at http://127.0.0.1:8000/docs
"""

from __future__ import annotations

from typing import List, Optional

# FastAPI / Pydantic — only needed at runtime, not for ifckit itself
try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import PlainTextResponse
    from pydantic import BaseModel, Field
    _FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover
    _FASTAPI_AVAILABLE = False
    # Define stubs so the rest of the module is importable without FastAPI
    class BaseModel:  # type: ignore
        pass
    def Field(*a, **kw):  # type: ignore
        return None

from ifckit import (
    IfcModel, IfcSchema,
    PendingWall, PendingSlab, PendingBeam, PendingColumn,
    Vec, Plane, Line,
    validate,
)
from ifckit.builders import default_registry
from ifckit.builders._geom import get_body_context


# ---------------------------------------------------------------------------
# Request / response models  (Pydantic)
# ---------------------------------------------------------------------------

class Vec3Input(BaseModel):
    x: float
    y: float
    z: float = 0.0


class WallInput(BaseModel):
    name: str = ""
    footprint: List[Vec3Input] = Field(
        ...,
        description="Closed footprint polygon — min 3 points, XY plane",
        min_length=3,
    )
    height: float = Field(..., gt=0, description="Wall height in metres")


class SlabInput(BaseModel):
    name: str = ""
    footprint: List[Vec3Input] = Field(..., min_length=3)
    thickness: float = Field(..., gt=0)


class LineInput(BaseModel):
    start: Vec3Input
    end: Vec3Input


class BeamInput(BaseModel):
    name: str = ""
    axis: LineInput
    profile: List[Vec3Input] = Field(..., min_length=3)


class ColumnInput(BaseModel):
    name: str = ""
    axis: LineInput
    profile: List[Vec3Input] = Field(..., min_length=3)


class StoreyInput(BaseModel):
    name: str
    elevation: float = 0.0
    walls: List[WallInput] = []
    slabs: List[SlabInput] = []
    beams: List[BeamInput] = []
    columns: List[ColumnInput] = []


class BuildingInput(BaseModel):
    project_name: str = "IFC Project"
    author: str = "ifckit-fastapi"
    site_name: str = "Site"
    building_name: str = "Building"
    storeys: List[StoreyInput] = []


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------

def _vec(v: Vec3Input) -> Vec:
    return Vec(v.x, v.y, v.z)


def _line(li: LineInput) -> Line:
    return Line(_vec(li.start), _vec(li.end))


def _footprint(pts: List[Vec3Input]) -> List[Vec]:
    return [_vec(p) for p in pts]


# ---------------------------------------------------------------------------
# Builder helper
# ---------------------------------------------------------------------------

def _build_storey(
    model: IfcModel,
    storey_handle,
    storey_input: StoreyInput,
    reg,
    ctx,
) -> None:
    for w in storey_input.walls:
        pw = PendingWall(
            footprint=_footprint(w.footprint),
            plane=Plane.world_xy(),
            height=w.height,
            name=w.name,
        )
        result = validate(pw)
        if not result.ok:
            raise HTTPException(status_code=422, detail=result.errors)
        reg.get("basic_wall").build(model.ifc_file, pw, storey_handle.entity, ctx)

    for s in storey_input.slabs:
        ps = PendingSlab(
            footprint=_footprint(s.footprint),
            plane=Plane.world_xy(),
            thickness=s.thickness,
            name=s.name,
        )
        result = validate(ps)
        if not result.ok:
            raise HTTPException(status_code=422, detail=result.errors)
        reg.get("basic_slab").build(model.ifc_file, ps, storey_handle.entity, ctx)

    for b in storey_input.beams:
        pb = PendingBeam(
            axis=_line(b.axis),
            profile=_footprint(b.profile),
            name=b.name,
        )
        result = validate(pb)
        if not result.ok:
            raise HTTPException(status_code=422, detail=result.errors)
        reg.get("basic_beam").build(model.ifc_file, pb, storey_handle.entity, ctx)

    for c in storey_input.columns:
        pc = PendingColumn(
            axis=_line(c.axis),
            profile=_footprint(c.profile),
            name=c.name,
        )
        result = validate(pc)
        if not result.ok:
            raise HTTPException(status_code=422, detail=result.errors)
        reg.get("basic_column").build(model.ifc_file, pc, storey_handle.entity, ctx)


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

if _FASTAPI_AVAILABLE:
    app = FastAPI(
        title="ifckit API",
        description="Convert a JSON building description to an IFC4 file.",
        version="0.1.0",
    )

    @app.post(
        "/building",
        response_class=PlainTextResponse,
        summary="Generate an IFC4 building",
        response_description="STEP-encoded IFC file content (text/plain)",
    )
    def generate_building(body: BuildingInput) -> str:
        """
        Accepts a building description as JSON and returns a complete
        IFC4 STEP file as plain text.

        The response body can be saved directly as a ``.ifc`` file.
        """
        model = IfcModel(
            name=body.project_name,
            schema=IfcSchema.IFC4,
            author=body.author,
        )
        site = model.add_site(body.site_name)
        building = model.add_building(site, body.building_name)

        reg = default_registry()
        ctx = get_body_context(model.ifc_file)

        for storey_input in body.storeys:
            storey = model.add_storey(
                building,
                name=storey_input.name,
                elevation=storey_input.elevation,
            )
            _build_storey(model, storey, storey_input, reg, ctx)

        return model.to_string()

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "library": "ifckit", "schema": "IFC4"}


# ---------------------------------------------------------------------------
# Sample request body (for documentation / curl testing)
# ---------------------------------------------------------------------------

SAMPLE_REQUEST = {
    "project_name": "FastAPI Demo Building",
    "author": "API user",
    "site_name": "Plot A",
    "building_name": "Demo Office",
    "storeys": [
        {
            "name": "Ground Floor",
            "elevation": 0.0,
            "walls": [
                {
                    "name": "South Wall",
                    "footprint": [
                        {"x": 0, "y": 0},
                        {"x": 10, "y": 0},
                        {"x": 10, "y": 0.3},
                        {"x": 0, "y": 0.3},
                    ],
                    "height": 3.0,
                }
            ],
            "slabs": [
                {
                    "name": "Ground Slab",
                    "footprint": [
                        {"x": 0, "y": 0},
                        {"x": 10, "y": 0},
                        {"x": 10, "y": 8},
                        {"x": 0, "y": 8},
                    ],
                    "thickness": 0.25,
                }
            ],
        }
    ],
}
