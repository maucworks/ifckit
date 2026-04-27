"""
api.app
=======

FastAPI application factory for the ifckit stateful API.

Run::

    uvicorn api.app:app --reload
    # Swagger UI → http://127.0.0.1:8000/docs
    # ReDoc      → http://127.0.0.1:8000/redoc
    # OpenAPI    → http://127.0.0.1:8000/openapi.json
"""

from __future__ import annotations

import os

from fastapi import FastAPI

from api.routes import elements, export, sessions, site

# ---------------------------------------------------------------------------
# Tag metadata — shown in Swagger UI as section headers
# ---------------------------------------------------------------------------

TAGS = [
    {
        "name": "sessions",
        "description": (
            "Create and manage IFC sessions. Each session holds an independent "
            "in-memory IFC model. Use `POST /sessions` to get a `session_id`."
        ),
    },
    {
        "name": "site",
        "description": (
            "Configure the IfcSite for a session. Defaults to Hofplein, Rotterdam "
            "(RD coordinates 103647, 434819). All fields are optional."
        ),
    },
    {
        "name": "elements",
        "description": (
            "Add, list, and delete pending IFC elements (walls, slabs, beams, columns). "
            "Elements are validated on POST but written to IFC only on export."
        ),
    },
    {
        "name": "export",
        "description": (
            "Build the IFC model from all pending elements and download the `.ifc` file. "
            "The model is rebuilt from scratch on every call."
        ),
    },
    {
        "name": "system",
        "description": "Health check and service metadata.",
    },
]

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ifckit API",
    description=(
        "**Stateful REST API for building IFC models.**\n\n"
        "Workflow:\n"
        "1. `POST /sessions` — create a session, receive `session_id`\n"
        "2. *(optional)* `PATCH /sessions/{id}/site` — override site coordinates\n"
        "3. `POST /sessions/{id}/elements` — add walls, slabs, beams, columns\n"
        "4. `GET /sessions/{id}/ifc` — download the assembled `.ifc` file\n"
        "5. `DELETE /sessions/{id}` — free memory when done\n\n"
        "IFC schema: **IFC4** (default) or **IFC4X3** (infrastructure).\n"
        "Default site location: Hofplein, Rotterdam (RD 103647, 434819).\n\n"
        "> **Note:** uses in-memory state. A single process only — "
        "do not run with `--workers > 1`."
    ),
    version="0.1.0",
    openapi_tags=TAGS,
    license_info={"name": "MIT"},
)

# ---------------------------------------------------------------------------
# ARCH-1 guard: fail fast when accidentally started with multiple workers.
# WEB_CONCURRENCY is set by gunicorn/uvicorn when workers > 1.
# ---------------------------------------------------------------------------
_workers = int(os.environ.get("WEB_CONCURRENCY", "1"))
if _workers > 1:
    raise RuntimeError(
        f"ifckit API uses in-memory session state and cannot run with "
        f"WEB_CONCURRENCY={_workers}. Use a single worker or switch to Redis."
    )

app.include_router(sessions.router)
app.include_router(site.router)
app.include_router(elements.router)
app.include_router(export.router)


@app.get("/health", tags=["system"], summary="Health check")
def health() -> dict:
    """Returns `{"status": "ok"}` — use to verify the service is running."""
    return {"status": "ok", "library": "ifckit", "api_version": "0.1.0"}
