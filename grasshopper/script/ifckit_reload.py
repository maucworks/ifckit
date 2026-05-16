"""
ifckit_reload.py  —  Thin shim: delegates to ifckit.reload.reload_all()
=======================================================================

Import this at the top of every Grasshopper Script node body:

    import ifckit_reload  # noqa: F401

This ensures sys.path is set and all ifckit submodules are reloaded from
disk before the node's own imports run.

The real logic lives in ifckit.reload.reload_all().
"""

import os
import sys

# ruff: noqa: E402  — sys.path manipulation must happen before ifckit import

# Make sure the project root is findable before we import ifckit at all.
_default_root = r'/Users/Mauc/L140-py-ifckit'
_root = os.environ.get('IFCKIT_PATH', _default_root)
if _root not in sys.path:
    sys.path.insert(0, _root)

from ifckit.reload import reload_all

reload_all(_root)
