"""
api.models
==========

Pydantic request / response schemas for the ifckit stateful API.
"""

from __future__ import annotations

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Geometry primitives
# ---------------------------------------------------------------------------

class Vec3(BaseModel):
    x: float
    y: float
    z: float = 0.0

    model_config = ConfigDict(
        json_schema_extra={"example": {"x": 0.0, "y": 0.0, "z": 0.0}}
    )


class LineInput(BaseModel):
    start: Vec3
    end: Vec3


# ---------------------------------------------------------------------------
# Session
# ---------------------------------------------------------------------------

class CreateSessionRequest(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "project_name": "My Project",
                "author": "Alice",
                "schema": "IFC4",
                "site_name": "Hofplein",
                "building_name": "Main Building",
            }
        },
    )

    project_name: str = Field("IFC Project", description="IfcProject name")
    author: str = Field("ifckit-api", description="Author stored in IfcOwnerHistory")
    ifc_schema: Literal["IFC4", "IFC4X3"] = Field(
        "IFC4", alias="schema", description="IFC schema version"
    )
    site_name: str = Field("Site", description="IfcSite name")
    building_name: str = Field("Building", description="IfcBuilding name")


class SessionResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    session_id: str
    project_name: str
    ifc_schema: str = Field(..., alias="schema", serialization_alias="schema")
    site_name: str
    building_name: str
    element_count: int


# ---------------------------------------------------------------------------
# Site
# ---------------------------------------------------------------------------

class SiteResponse(BaseModel):
    """Response body for GET and POST /sessions/{id}/site."""
    session_id: str
    site_name: str
    site_description: Optional[str] = None
    site_latitude: Optional[tuple[float, float, float]] = None
    site_longitude: Optional[tuple[float, float, float]] = None
    site_elevation: Optional[float] = None
    site_location: Optional[tuple[float, float, float]] = None


class AddSiteRequest(BaseModel):
    """
    Override site properties.  Omitting any field keeps the library default
    (Hofplein, Rotterdam RD coordinates).
    """
    name: Optional[str] = None
    description: Optional[str] = None
    latitude: Optional[tuple[float, float, float]] = Field(
        None, description="(degrees, minutes, seconds) — default: Hofplein 51°55'21\""
    )
    longitude: Optional[tuple[float, float, float]] = Field(
        None, description="(degrees, minutes, seconds) — default: Hofplein 4°28'60\""
    )
    elevation: Optional[float] = Field(None, description="Elevation in metres")
    location: Optional[tuple[float, float, float]] = Field(
        None, description="RD Cartesian origin (x, y, z) in metres"
    )


# ---------------------------------------------------------------------------
# Elements — discriminated union by `type`
# ---------------------------------------------------------------------------

class WallInput(BaseModel):
    type: Literal["wall"] = "wall"
    storey_name: str = Field("Ground Floor", description="Target storey name")
    storey_elevation: float = Field(0.0, description="Storey elevation in metres")
    name: str = ""
    footprint: list[Vec3] = Field(..., min_length=3, description="Closed polygon, min 3 pts")
    height: float = Field(..., gt=0, description="Wall height in metres")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "wall",
                "storey_name": "Ground Floor",
                "storey_elevation": 0.0,
                "name": "South Wall",
                "footprint": [
                    {"x": 0, "y": 0},
                    {"x": 10, "y": 0},
                    {"x": 10, "y": 0.3},
                    {"x": 0, "y": 0.3},
                ],
                "height": 3.0,
            }
        }
    )


class SlabInput(BaseModel):
    type: Literal["slab"] = "slab"
    storey_name: str = Field("Ground Floor")
    storey_elevation: float = 0.0
    name: str = ""
    footprint: list[Vec3] = Field(..., min_length=3)
    thickness: float = Field(..., gt=0)


class BeamInput(BaseModel):
    type: Literal["beam"] = "beam"
    storey_name: str = Field("Ground Floor")
    storey_elevation: float = 0.0
    name: str = ""
    axis: LineInput
    profile: list[Vec3] = Field(..., min_length=3)


class ColumnInput(BaseModel):
    type: Literal["column"] = "column"
    storey_name: str = Field("Ground Floor")
    storey_elevation: float = 0.0
    name: str = ""
    axis: LineInput
    profile: list[Vec3] = Field(..., min_length=3)


AddElementRequest = Annotated[
    Union[WallInput, SlabInput, BeamInput, ColumnInput],
    Field(discriminator="type"),
]


class AddElementResponse(BaseModel):
    element_id: str
    element_type: str
    storey_name: str


class ElementSummary(BaseModel):
    element_id: str
    element_type: str
    storey_name: str
    storey_elevation: float
    name: str
