"""
api.state
=========

In-memory session store.  A ``SessionState`` holds all the data needed to
(re)build an IFC model on demand.  The IFC file itself is *not* kept alive
between requests — it is rebuilt from the stored ``Pending*`` objects every
time ``GET /sessions/{id}/ifc`` is called (Option A: rebuild-on-export).

This means ``DELETE /sessions/{id}/elements/{eid}`` is a pure dict pop with
no ifcopenshell involvement, and exports are always consistent.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Optional, Union

from ifckit import PendingBeam, PendingColumn, PendingSlab, PendingWall
from ifckit.schema import IfcSchema

AnyPending = Union[PendingWall, PendingSlab, PendingBeam, PendingColumn]


# ---------------------------------------------------------------------------
# Per-element record
# ---------------------------------------------------------------------------

@dataclass
class PendingRecord:
    """One pending element plus routing metadata."""
    element_id: str
    element_type: str          # "wall" | "slab" | "beam" | "column"
    storey_name: str
    storey_elevation: float
    name: str                  # cached from pending.name for easy listing
    pending: AnyPending


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

@dataclass
class SessionState:
    """All mutable state for one IFC session."""

    session_id: str

    # IfcModel constructor kwargs
    project_name: str = "IFC Project"
    author: str = "ifckit-api"
    schema: IfcSchema = IfcSchema.IFC4

    # add_site kwargs (None → use library defaults = Hofplein Rotterdam)
    site_name: str = "Site"
    site_description: Optional[str] = None
    site_latitude: Optional[tuple[float, float, float]] = None
    site_longitude: Optional[tuple[float, float, float]] = None
    site_elevation: Optional[float] = None
    site_location: Optional[tuple[float, float, float]] = None

    building_name: str = "Building"

    # Ordered list of pending elements
    elements: dict[str, PendingRecord] = field(default_factory=dict)
    @property
    def element_count(self) -> int:
        return len(self.elements)


# ---------------------------------------------------------------------------
# Global store
# ---------------------------------------------------------------------------

_STORE: dict[str, SessionState] = {}


def create_session(**kwargs) -> SessionState:  # type: ignore[no-untyped-def]
    sid = str(uuid.uuid4())
    state = SessionState(session_id=sid, **kwargs)
    _STORE[sid] = state
    return state


def get_session(session_id: str) -> Optional[SessionState]:
    return _STORE.get(session_id)


def delete_session(session_id: str) -> None:
    _STORE.pop(session_id, None)


def all_sessions() -> list[SessionState]:
    return list(_STORE.values())
