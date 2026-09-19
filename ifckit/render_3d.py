# This file was generated with the assistance of an AI coding tool.
"""ifckit.render_3d — headless 3D-rendering via Blender.

``render_glb`` exporteert een model naar een tijdelijke ``.glb`` en rendert het
met ``blender -b`` naar een PNG. Vereist Blender op ``PATH``.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

_CAMERAS = ("iso", "front", "top")

_BLENDER_SCRIPT = r"""
import sys

import bpy
import mathutils


def _scene_bounds():
    mins = mathutils.Vector((1e18, 1e18, 1e18))
    maxs = mathutils.Vector((-1e18, -1e18, -1e18))
    found = False
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        found = True
        for corner in obj.bound_box:
            world = obj.matrix_world @ mathutils.Vector(corner)
            mins.x = min(mins.x, world.x)
            mins.y = min(mins.y, world.y)
            mins.z = min(mins.z, world.z)
            maxs.x = max(maxs.x, world.x)
            maxs.y = max(maxs.y, world.y)
            maxs.z = max(maxs.z, world.z)
    return (mins, maxs) if found else (None, None)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    glb_path, out_png, camera = argv

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=glb_path)

    mins, maxs = _scene_bounds()
    if mins is None:
        raise RuntimeError("geen mesh-geometrie gevonden in " + glb_path)
    center = (mins + maxs) / 2.0
    diag = (maxs - mins).length

    bpy.ops.object.camera_add()
    cam = bpy.context.object
    bpy.context.scene.camera = cam
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = max(diag, 1e-3) * 1.6

    dist = diag * 2.0
    if camera == "top":
        cam.location = center + mathutils.Vector((0.0, 0.0, dist))
    elif camera == "front":
        cam.location = center + mathutils.Vector((0.0, -dist, 0.0))
    else:  # iso
        cam.location = center + mathutils.Vector((dist, -dist, dist))

    # camera direct op het midden richten (zonder constraint)
    rot = (center - cam.location).to_track_quat("-Z", "Y")
    cam.rotation_euler = rot.to_euler()

    # verlichting: een zon zodat EEVEE nooit zwart rendert
    bpy.ops.object.light_add(type="SUN")
    sun = bpy.context.object
    sun.data.energy = 10.0
    sun.rotation_euler = (0.7, 0.0, 1.0)

    scene = bpy.context.scene
    scene.render.resolution_x = 1024
    scene.render.resolution_y = 1024
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = out_png
    bpy.ops.render.render(write_still=True)


main()
"""


def _blender_exe() -> str:
    """Return het Blender-executable, of geef een duidelijke fout.

    De omgevingsvariabele ``IFCKIT_BLENDER`` heeft voorrang; anders wordt
    ``blender`` op ``PATH`` gebruikt.
    """
    import os

    env = os.environ.get("IFCKIT_BLENDER")
    if env:
        return env
    exe = shutil.which("blender")
    if exe is None:
        raise RuntimeError(
            "ifckit.render_3d vereist Blender op PATH. Installeer Blender: https://www.blender.org/"
        )
    # Blender lost zijn gebundelde Python/resources op via argv[0]; via een
    # symlink (bv. ~/.local/mybin/blender) gaat dat mis. Los symlinks op.
    return os.path.realpath(exe)


def render_glb(model, out_png: str, camera: str = "iso") -> bytes:
    """Render een model naar PNG via headless Blender.

    Args:
        model: Een ``IfcModel``.
        out_png: Pad waar de PNG wordt geschreven.
        camera: ``"iso"`` | ``"front"`` | ``"top"``.

    Returns:
        De PNG-bytes van het resultaat.
    """
    if camera not in _CAMERAS:
        raise ValueError(f"onbekende camera {camera!r}; verwacht een van {_CAMERAS}")

    out = Path(out_png)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        glb = Path(tmp) / "model.glb"
        model.export(str(glb))
        script = Path(tmp) / "render.py"
        script.write_text(_BLENDER_SCRIPT, encoding="utf-8")
        subprocess.run(
            [
                _blender_exe(),
                "-b",
                "--factory-startup",
                "--python",
                str(script),
                "--",
                str(glb),
                str(out),
                camera,
            ],
            check=True,
            capture_output=True,
        )
    return out.read_bytes()
