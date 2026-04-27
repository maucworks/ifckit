"""
api.routes.sessions
===================

POST   /sessions            → create session
GET    /sessions            → list all sessions
GET    /sessions/{id}       → session metadata
DELETE /sessions/{id}       → destroy session
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api import state as store
from api.deps import get_session
from api.models import CreateSessionRequest, SessionResponse
from api.state import SessionState
from ifckit.schema import IfcSchema

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _to_response(s: SessionState) -> SessionResponse:
    return SessionResponse(
        session_id=s.session_id,
        project_name=s.project_name,
        ifc_schema=s.schema.value,
        site_name=s.site_name,
        building_name=s.building_name,
        element_count=s.element_count,
    )


@router.post(
    "",
    response_model=SessionResponse,
    status_code=201,
    summary="Create a new IFC session",
    description=(
        "Creates an in-memory IFC session. Returns a `session_id` UUID that "
        "must be supplied to all subsequent requests."
    ),
)
def create_session(body: CreateSessionRequest) -> SessionResponse:
    schema = IfcSchema.IFC4X3 if body.ifc_schema == "IFC4X3" else IfcSchema.IFC4
    state = store.create_session(
        project_name=body.project_name,
        author=body.author,
        schema=schema,
        site_name=body.site_name,
        building_name=body.building_name,
    )
    return _to_response(state)


@router.get(
    "",
    response_model=list[SessionResponse],
    summary="List all active sessions",
)
def list_sessions() -> list[SessionResponse]:
    return [_to_response(s) for s in store.all_sessions()]


@router.get(
    "/{session_id}",
    response_model=SessionResponse,
    summary="Get session metadata",
)
def get_session_info(state: SessionState = Depends(get_session)) -> SessionResponse:
    return _to_response(state)


@router.delete(
    "/{session_id}",
    status_code=204,
    summary="Delete a session",
    description="Destroys the session and frees all in-memory state.",
)
def delete_session(state: SessionState = Depends(get_session)) -> None:
    store.delete_session(state.session_id)
