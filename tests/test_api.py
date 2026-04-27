"""
tests/test_api.py
=================

Integration tests for the stateful ifckit FastAPI service.

Uses httpx's TestClient (sync) — no async machinery needed.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

# Reset the in-memory store before every test so tests are isolated
import api.state as _store_module
from api.app import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_store():
    """Wipe in-memory session store before each test."""
    _store_module._STORE.clear()
    yield
    _store_module._STORE.clear()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Session CRUD
# ---------------------------------------------------------------------------

def test_create_session_defaults():
    r = client.post("/sessions", json={})
    assert r.status_code == 201
    data = r.json()
    assert "session_id" in data
    assert data["schema"] == "IFC4"
    assert data["element_count"] == 0


def test_create_session_custom():
    r = client.post("/sessions", json={
        "project_name": "Bridge X",
        "schema": "IFC4X3",
        "site_name": "Amsterdam",
        "building_name": "Deck",
    })
    assert r.status_code == 201
    data = r.json()
    assert data["project_name"] == "Bridge X"
    assert data["schema"] == "IFC4X3"


def test_list_sessions_empty():
    r = client.get("/sessions")
    assert r.status_code == 200
    assert r.json() == []


def test_list_sessions_after_create():
    client.post("/sessions", json={})
    client.post("/sessions", json={"project_name": "Second"})
    r = client.get("/sessions")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_get_session():
    sid = client.post("/sessions", json={"project_name": "X"}).json()["session_id"]
    r = client.get(f"/sessions/{sid}")
    assert r.status_code == 200
    assert r.json()["project_name"] == "X"


def test_get_session_not_found():
    r = client.get("/sessions/does-not-exist")
    assert r.status_code == 404


def test_delete_session():
    sid = client.post("/sessions", json={}).json()["session_id"]
    r = client.delete(f"/sessions/{sid}")
    assert r.status_code == 204
    assert client.get(f"/sessions/{sid}").status_code == 404


def test_delete_session_not_found():
    r = client.delete("/sessions/ghost")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Site configuration
# ---------------------------------------------------------------------------

def test_configure_site():
    sid = client.post("/sessions", json={}).json()["session_id"]
    r = client.patch(f"/sessions/{sid}/site", json={"name": "Rotterdam", "elevation": 5.0})
    assert r.status_code == 200
    data = r.json()
    assert data["site_name"] == "Rotterdam"
    assert data["site_elevation"] == 5.0


def test_get_site_defaults():
    sid = client.post("/sessions", json={}).json()["session_id"]
    r = client.get(f"/sessions/{sid}/site")
    assert r.status_code == 200
    data = r.json()
    # Defaults should be None (library fills them in at export time)
    assert data["site_latitude"] is None
    assert data["site_location"] is None


# ---------------------------------------------------------------------------
# Elements
# ---------------------------------------------------------------------------

WALL = {
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

SLAB = {
    "type": "slab",
    "storey_name": "Ground Floor",
    "storey_elevation": 0.0,
    "footprint": [
        {"x": 0, "y": 0},
        {"x": 10, "y": 0},
        {"x": 10, "y": 8},
        {"x": 0, "y": 8},
    ],
    "thickness": 0.25,
}

BEAM = {
    "type": "beam",
    "storey_name": "First Floor",
    "storey_elevation": 3.0,
    "axis": {"start": {"x": 0, "y": 0, "z": 0}, "end": {"x": 5, "y": 0, "z": 0}},
    "profile": [
        {"x": -0.1, "y": -0.15},
        {"x":  0.1, "y": -0.15},
        {"x":  0.1, "y":  0.15},
        {"x": -0.1, "y":  0.15},
    ],
}

COLUMN = {
    "type": "column",
    "storey_name": "Ground Floor",
    "storey_elevation": 0.0,
    "axis": {"start": {"x": 5, "y": 5, "z": 0}, "end": {"x": 5, "y": 5, "z": 3}},
    "profile": [
        {"x": -0.15, "y": -0.15},
        {"x":  0.15, "y": -0.15},
        {"x":  0.15, "y":  0.15},
        {"x": -0.15, "y":  0.15},
    ],
}


def _new_session() -> str:
    return client.post("/sessions", json={}).json()["session_id"]


def test_add_wall():
    sid = _new_session()
    r = client.post(f"/sessions/{sid}/elements", json=WALL)
    assert r.status_code == 201
    data = r.json()
    assert data["element_type"] == "wall"
    assert "element_id" in data


def test_add_slab():
    sid = _new_session()
    r = client.post(f"/sessions/{sid}/elements", json=SLAB)
    assert r.status_code == 201


def test_add_beam():
    sid = _new_session()
    r = client.post(f"/sessions/{sid}/elements", json=BEAM)
    assert r.status_code == 201


def test_add_column():
    sid = _new_session()
    r = client.post(f"/sessions/{sid}/elements", json=COLUMN)
    assert r.status_code == 201


def test_list_elements():
    sid = _new_session()
    client.post(f"/sessions/{sid}/elements", json=WALL)
    client.post(f"/sessions/{sid}/elements", json=SLAB)
    r = client.get(f"/sessions/{sid}/elements")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_element_count_reflected_in_session():
    sid = _new_session()
    client.post(f"/sessions/{sid}/elements", json=WALL)
    client.post(f"/sessions/{sid}/elements", json=WALL)
    data = client.get(f"/sessions/{sid}").json()
    assert data["element_count"] == 2


def test_delete_element():
    sid = _new_session()
    eid = client.post(f"/sessions/{sid}/elements", json=WALL).json()["element_id"]
    r = client.delete(f"/sessions/{sid}/elements/{eid}")
    assert r.status_code == 204
    assert len(client.get(f"/sessions/{sid}/elements").json()) == 0


def test_delete_element_not_found():
    sid = _new_session()
    r = client.delete(f"/sessions/{sid}/elements/ghost-id")
    assert r.status_code == 404


def test_invalid_element_missing_height():
    sid = _new_session()
    bad = {**WALL}
    del bad["height"]
    r = client.post(f"/sessions/{sid}/elements", json=bad)
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

def test_export_empty_session():
    """An empty session should still produce a valid IFC STEP header."""
    sid = _new_session()
    r = client.get(f"/sessions/{sid}/ifc")
    assert r.status_code == 200
    assert b"ISO-10303-21" in r.content


def test_export_with_wall():
    sid = _new_session()
    client.post(f"/sessions/{sid}/elements", json=WALL)
    r = client.get(f"/sessions/{sid}/ifc")
    assert r.status_code == 200
    assert b"IFCWALL" in r.content


def test_export_with_multiple_element_types():
    sid = _new_session()
    client.post(f"/sessions/{sid}/elements", json=WALL)
    client.post(f"/sessions/{sid}/elements", json=SLAB)
    client.post(f"/sessions/{sid}/elements", json=BEAM)
    client.post(f"/sessions/{sid}/elements", json=COLUMN)
    r = client.get(f"/sessions/{sid}/ifc")
    assert r.status_code == 200
    body = r.content
    assert b"IFCWALL" in body
    assert b"IFCSLAB" in body
    assert b"IFCBEAM" in body
    assert b"IFCCOLUMN" in body


def test_export_after_delete_element():
    """Deleted element must not appear in the export."""
    sid = _new_session()
    eid = client.post(f"/sessions/{sid}/elements", json=WALL).json()["element_id"]
    client.post(f"/sessions/{sid}/elements", json=SLAB)
    # Delete the wall
    client.delete(f"/sessions/{sid}/elements/{eid}")
    r = client.get(f"/sessions/{sid}/ifc")
    assert r.status_code == 200
    # Slab present, wall absent
    assert b"IFCSLAB" in r.content
    assert b"IFCWALL" not in r.content


def test_export_content_disposition_header():
    sid = _new_session()
    r = client.get(f"/sessions/{sid}/ifc")
    assert "content-disposition" in r.headers
    assert ".ifc" in r.headers["content-disposition"]


def test_export_not_found():
    r = client.get("/sessions/ghost/ifc")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Swagger / OpenAPI schema
# ---------------------------------------------------------------------------

def test_openapi_schema_available():
    r = client.get("/openapi.json")
    assert r.status_code == 200
    schema = r.json()
    assert schema["info"]["title"] == "ifckit API"


def test_swagger_ui_available():
    r = client.get("/docs")
    assert r.status_code == 200
    assert b"swagger" in r.content.lower()


def test_redoc_available():
    r = client.get("/redoc")
    assert r.status_code == 200
