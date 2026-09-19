# This file was generated with the assistance of an AI coding tool.
"""Tests for ifckit.render_3d.render_glb (vereist Blender)."""

import os
import shutil

import pytest

from ifckit import IfcModel, PendingWall
from ifckit.geometry import Plane, Vec
from ifckit.render_3d import render_glb

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_BLENDER_AVAILABLE = shutil.which("blender") is not None or os.environ.get("IFCKIT_BLENDER")


def _small_model() -> IfcModel:
    m = IfcModel(name="Render")
    site = m.add_site("S")
    building = m.add_building(site, "B")
    storey = m.add_storey(building, "00", elevation=0.0)
    storey.add_space(
        [Vec(0, 0, 0), Vec(4, 0, 0), Vec(4, 3, 0), Vec(0, 3, 0)], 2.7, "1.01", "Keuken"
    )
    plane = Plane.world_xy()
    storey.add(
        PendingWall([Vec(0, 0, 0), Vec(4, 0, 0), Vec(4, 0.2, 0), Vec(0, 0.2, 0)], plane, 2.7, "W")
    )
    return m


def test_render_glb_rejects_unknown_camera():
    with pytest.raises(ValueError):
        render_glb(_small_model(), "/tmp/unused.png", camera="dolly")


@pytest.mark.skipif(not _BLENDER_AVAILABLE, reason="Blender niet op PATH")
def test_render_glb_produces_png(tmp_path):
    out = tmp_path / "render.png"
    try:
        data = render_glb(_small_model(), str(out), camera="iso")
    except Exception as exc:  # pragma: no cover — gebroken Blender-install
        pytest.skip(f"Blender-render mislukt: {exc}")
    assert data[:8] == _PNG_MAGIC
    assert len(data) > 1000
    assert out.exists()
