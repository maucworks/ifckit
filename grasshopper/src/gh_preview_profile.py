"""
gh_preview_profile.py  —  GH Script component: "ifckit Preview Profile"
=========================================================================

@component  nickname:"ifckit Preview Profile"
@group "Profiles"
@input  json_in          : str  item — Profile JSON (json_out from ifckit Profile node)
@output out              : str  item — Status message
@output profile_curve    : geometry item — Closed profile curve in WorldXY around origin
"""

from __future__ import annotations

import json
import traceback

# ---------------------------------------------------------------------------
# Reload (picks up live code changes without restarting Rhino)
# ---------------------------------------------------------------------------
try:
    import os, sys
    _root = os.environ.get("IFCKIT_PATH", r"/Users/Mauc/L140-py-ifckit")
    if _root not in sys.path:
        sys.path.insert(0, _root)
    import ifckit.rhinokit as _rk
    _rk.reload_all(_root)
except Exception:
    pass

# ---------------------------------------------------------------------------
# Reload (picks up live code changes without restarting Rhino)
# ---------------------------------------------------------------------------
try:
    import os, sys, importlib
    _root = os.environ.get("IFCKIT_PATH", r"/Users/Mauc/L140-py-ifckit")
    if _root not in sys.path:
        sys.path.insert(0, _root)
    import ifckit.rhinokit as _rk
    _rk.reload_all(_root)
except Exception:
    pass

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
profile_curve = None
out = ""

try:
    if not json_in:
        raise ValueError("json_in is empty")

    d = json.loads(json_in)

    from ifckit.profiles.base import Profile
    from ifckit.rhinokit import profile_to_rhino_curve

    profile = Profile.dispatch_from_dict(d)
    profile_curve = profile_to_rhino_curve(profile)
    out = f"OK: {profile.__class__.__name__}"

except Exception as exc:
    out = f"ERROR: {exc}\n{traceback.format_exc()}"
