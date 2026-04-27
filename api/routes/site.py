"""
api.routes.site
===============

PATCH /sessions/{id}/site  → update site configuration (partial update)
GET   /sessions/{id}/site  → show current site config
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.deps import get_session
from api.models import AddSiteRequest, SiteResponse
from api.state import SessionState

router = APIRouter(prefix="/sessions", tags=["site"])


def _site_response(state: SessionState) -> SiteResponse:
    return SiteResponse(
        session_id=state.session_id,
        site_name=state.site_name,
        site_description=state.site_description,
        site_latitude=state.site_latitude,
        site_longitude=state.site_longitude,
        site_elevation=state.site_elevation,
        site_location=state.site_location,
    )


@router.patch(
    "/{session_id}/site",
    response_model=SiteResponse,
    status_code=200,
    summary="Configure the site (partial update)",
    description=(
        "Updates site properties on the session. Omit any field to keep the current "
        "value. Defaults to Hofplein, Rotterdam when a field was never set. "
        "Can be called multiple times; last call wins per field."
    ),
)
def configure_site(
    body: AddSiteRequest,
    state: SessionState = Depends(get_session),
) -> SiteResponse:
    if body.name is not None:
        state.site_name = body.name
    if body.description is not None:
        state.site_description = body.description
    if body.latitude is not None:
        state.site_latitude = body.latitude
    if body.longitude is not None:
        state.site_longitude = body.longitude
    if body.elevation is not None:
        state.site_elevation = body.elevation
    if body.location is not None:
        state.site_location = body.location
    return _site_response(state)


@router.get(
    "/{session_id}/site",
    response_model=SiteResponse,
    summary="Get current site configuration",
)
def get_site(state: SessionState = Depends(get_session)) -> SiteResponse:
    return _site_response(state)
