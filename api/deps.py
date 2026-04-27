"""
api.deps
========

FastAPI dependencies shared across routes.
"""

from __future__ import annotations

from fastapi import HTTPException, Path

from api.state import SessionState, get_session as _get


def get_session(
    session_id: str = Path(..., description="Session UUID"),
) -> SessionState:
    state = _get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return state
