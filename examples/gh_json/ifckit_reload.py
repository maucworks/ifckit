"""
ifckit_reload.py  —  Path setup + full ifckit module reload for GH nodes
=========================================================================

Usage in every GH Script node (two lines, after the module docstring):

    import ifckit_reload  # noqa: F401  (sets sys.path, reloads all of ifckit)
    from ifckit_reload import ifckit, rk  # optional convenience re-exports

The module is idempotent: importing it multiple times is safe.
Set the environment variable IFCKIT_PATH to override the default project root.
"""

from __future__ import annotations

import importlib
import os
import sys

# ---------------------------------------------------------------------------
# 1. Ensure the project root is on sys.path
# ---------------------------------------------------------------------------

_DEFAULT_ROOT = r'/Users/Mauc/L140-py-ifckit'
_root = os.environ.get('IFCKIT_PATH', _DEFAULT_ROOT)
if _root not in sys.path:
    sys.path.insert(0, _root)

# Also ensure this directory (gh_json/) is on the path so that GH nodes
# can find ifckit_reload itself when running from a different CWD.
_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

# ---------------------------------------------------------------------------
# 2. Import all ifckit submodules (required before reloading)
# ---------------------------------------------------------------------------

import ifckit                           # noqa: E402
import ifckit.schema                    # noqa: E402
import ifckit.geometry                  # noqa: E402
import ifckit.elements                  # noqa: E402
import ifckit.profiles                  # noqa: E402
import ifckit.profiles.base             # noqa: E402
import ifckit.profiles.shapes           # noqa: E402
import ifckit.profiles.i_beam           # noqa: E402
import ifckit.profiles.l_beam           # noqa: E402
import ifckit.profiles.steel            # noqa: E402
import ifckit.builders                  # noqa: E402
import ifckit.builders._geom            # noqa: E402
import ifckit.builders.base             # noqa: E402
import ifckit.builders.extruded         # noqa: E402
import ifckit.builders.wall             # noqa: E402
import ifckit.builders.slab             # noqa: E402
import ifckit.builders.space            # noqa: E402
import ifckit.builders.beam_factory     # noqa: E402
import ifckit.builders.revolved_beam    # noqa: E402
import ifckit.builders.bridge           # noqa: E402
import ifckit.rhinokit                  # noqa: E402
import ifckit.rhino_import              # noqa: E402
import ifckit.model                     # noqa: E402
import ifckit.validator                 # noqa: E402
import ifckit.json_build                # noqa: E402

# ---------------------------------------------------------------------------
# 3. Reload in dependency order (leaves first, root last)
# ---------------------------------------------------------------------------

importlib.reload(ifckit.schema)
importlib.reload(ifckit.geometry)
importlib.reload(ifckit.elements)
importlib.reload(ifckit.profiles.base)
importlib.reload(ifckit.profiles.shapes)
importlib.reload(ifckit.profiles.i_beam)
importlib.reload(ifckit.profiles.l_beam)
importlib.reload(ifckit.profiles.steel)
importlib.reload(ifckit.profiles)
importlib.reload(ifckit.builders._geom)
importlib.reload(ifckit.builders.base)
importlib.reload(ifckit.builders.extruded)
importlib.reload(ifckit.builders.wall)
importlib.reload(ifckit.builders.slab)
importlib.reload(ifckit.builders.space)
importlib.reload(ifckit.builders.beam_factory)
importlib.reload(ifckit.builders.revolved_beam)
importlib.reload(ifckit.builders.bridge)
importlib.reload(ifckit.builders)
importlib.reload(ifckit.rhinokit)
importlib.reload(ifckit.rhino_import)
importlib.reload(ifckit.model)
importlib.reload(ifckit.validator)
importlib.reload(ifckit.json_build)
importlib.reload(ifckit)

# ---------------------------------------------------------------------------
# 4. Convenience re-exports (optional — import from here to avoid re-typing)
# ---------------------------------------------------------------------------

import ifckit.rhinokit as rk            # noqa: E402  (re-exported)
