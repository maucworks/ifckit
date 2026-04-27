"""
api.routes.elements
===================

POST   /sessions/{id}/elements           → add element, returns element_id
GET    /sessions/{id}/elements           → list all elements
DELETE /sessions/{id}/elements/{eid}     → remove element by id
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_session
from api.models import (
    AddElementRequest,
    AddElementResponse,
    BeamInput,
    ColumnInput,
    ElementSummary,
    LineInput,
    SlabInput,
    Vec3,
    WallInput,
)
from api.state import PendingRecord, SessionState
from ifckit import (
    Line,
    Plane,
    PendingBeam,
    PendingColumn,
    PendingSlab,
    PendingWall,
    Vec,
    validate,
)

router = APIRouter(prefix="/sessions", tags=["elements"])


# ---------------------------------------------------------------------------
# Conversion helpers
# ---------------------------------------------------------------------------

def _vec(v: Vec3) -> Vec:
    return Vec(v.x, v.y, v.z)


def _footprint(pts: list[Vec3]) -> list[Vec]:
    return [_vec(p) for p in pts]


def _line(li: LineInput) -> Line:
    return Line(_vec(li.start), _vec(li.end))


def _build_pending(body: AddElementRequest):  # type: ignore[valid-type]
    if isinstance(body, WallInput):
        return PendingWall(
            footprint=_footprint(body.footprint),
            plane=Plane.world_xy(),
            height=body.height,
            name=body.name,
        )
    if isinstance(body, SlabInput):
        return PendingSlab(
            footprint=_footprint(body.footprint),
            plane=Plane.world_xy(),
            thickness=body.thickness,
            name=body.name,
        )
    if isinstance(body, BeamInput):
        return PendingBeam(
            axis=_line(body.axis),
            profile=_footprint(body.profile),
            name=body.name,
        )
    if isinstance(body, ColumnInput):
        return PendingColumn(
            axis=_line(body.axis),
            profile=_footprint(body.profile),
            name=body.name,
        )
    raise ValueError(f"Unknown element type: {type(body)}")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post(
    "/{session_id}/elements",
    response_model=AddElementResponse,
    status_code=201,
    summary="Add an element to the session",
    description=(
        "Validates and stores a pending element. The element is not written to IFC "
        "until `GET /sessions/{id}/ifc` is called. Supported types: "
        "`wall`, `slab`, `beam`, `column`."
    ),
)
def add_element(
    body: AddElementRequest,  # type: ignore[valid-type]
    state: SessionState = Depends(get_session),
) -> AddElementResponse:
    pending = _build_pending(body)
    result = validate(pending)
    if not result.ok:
        raise HTTPException(status_code=422, detail=result.errors)

    eid = str(uuid.uuid4())
    state.elements[eid] = PendingRecord(
        element_id=eid,
        element_type=body.type,
        storey_name=body.storey_name,
        storey_elevation=body.storey_elevation,
        name=body.name,
        pending=pending,
    )
    return AddElementResponse(
        element_id=eid,
        element_type=body.type,
        storey_name=body.storey_name,
    )


@router.get(
    "/{session_id}/elements",
    response_model=list[ElementSummary],
    summary="List all elements in the session",
)
def list_elements(state: SessionState = Depends(get_session)) -> list[ElementSummary]:
    return [
        ElementSummary(
            element_id=rec.element_id,
            element_type=rec.element_type,
            storey_name=rec.storey_name,
            storey_elevation=rec.storey_elevation,
            name=rec.name,
        )
        for rec in state.elements.values()
    ]


@router.delete(
    "/{session_id}/elements/{element_id}",
    status_code=204,
    summary="Remove an element from the session",
    description="Removes the element from the pending list. The next export will not include it.",
)
def delete_element(
    element_id: str,
    state: SessionState = Depends(get_session),
) -> None:
    if element_id not in state.elements:
        raise HTTPException(status_code=404, detail=f"Element '{element_id}' not found")
    del state.elements[element_id]
