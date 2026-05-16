"""
ifckit.reload
=============

Live code reload for ifckit submodules.

Call ``reload_all()`` at the top of a Grasshopper Script node or Blender
Text Editor script to pick up source changes without restarting the host::

    from ifckit.reload import reload_all

    reload_all()  # reload all ifckit modules

    # or with a custom project root:
    reload_all("/path/to/ifckit")
"""

from __future__ import annotations

import importlib
import os
import sys
from typing import Optional


def reload_all(project_root: Optional[str] = None) -> None:
    """
    Ensure *project_root* is on ``sys.path`` and reload all ifckit submodules
    in dependency order (leaves first, root last).

    Parameters
    ----------
    project_root : str, optional
        Absolute path to the project root (the directory that contains the
        ``ifckit`` package).  Reads the ``IFCKIT_PATH`` environment variable
        first; falls back to ``/Users/Mauc/L140-py-ifckit`` if neither is set.
    """
    _default = None
    root = project_root or os.environ.get("IFCKIT_PATH", _default)
    if root and root not in sys.path:
        sys.path.insert(0, root)

    _RELOAD_ORDER = [
        "ifckit.schema",
        "ifckit.geometry",
        "ifckit.elements",
        "ifckit.elements.opening",
        "ifckit.profiles.base",
        "ifckit.profiles.shapes",
        "ifckit.profiles.i_beam",
        "ifckit.profiles.l_beam",
        "ifckit.profiles.steel",
        "ifckit.profiles",
        "ifckit.builders._geom",
        "ifckit.builders.base",
        "ifckit.builders.extruded",
        "ifckit.builders.opening",
        "ifckit.builders.wall",
        "ifckit.builders.slab",
        "ifckit.builders.space",
        "ifckit.builders.beam_factory",
        "ifckit.builders.revolved_beam",
        "ifckit.builders.door_window",
        "ifckit.builders.bridge",
        "ifckit.builders.tapered",
        "ifckit.builders",
        "ifckit.bonsaikit",
        "ifckit.model",
        "ifckit.validator",
        "ifckit.json_build",
        "ifckit",
    ]

    for mod_name in _RELOAD_ORDER:
        mod = sys.modules.get(mod_name)
        if mod is not None:
            try:
                importlib.reload(mod)
            except ImportError:
                pass
        else:
            try:
                importlib.import_module(mod_name)
            except ImportError:
                pass
