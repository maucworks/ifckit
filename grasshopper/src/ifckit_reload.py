"""
ifckit_reload.py  —  Thin shim: delegates to ifckit.reload.reload_all()
=======================================================================

Import this at the top of every Grasshopper Script node body:

    import ifckit_reload  # noqa: F401

This ensures all ifckit submodules are reloaded from disk before the
node's own imports run.  Set the IFCKIT_PATH environment variable to
the project root if ifckit is not installed as a package.

The real logic lives in ifckit.reload.reload_all().
"""

import os
import sys

# ruff: noqa: E402  — sys.path manipulation must happen before ifckit import
_root = os.environ.get("IFCKIT_PATH")
if _root and _root not in sys.path:
    sys.path.insert(0, _root)

from ifckit.reload import reload_all

reload_all(_root)
