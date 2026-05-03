"""
gh_introspect7.py  —  Use RhinoCodePlatform.Projects API to create and
serialize a minimal project, revealing the .rhproj JSON format.
Run inside Rhino 8 ScriptEditor.
"""
import clr
import os

# Load the Projects assembly
clr.AddReference("RhinoCodePlatform.Projects")
import RhinoCodePlatform.Rhino3D.Projects as P

print("=== RhinoCodePlatform.Projects types ===")
types = [t for t in dir(P) if not t.startswith("_")]
for t in types:
    print(f"  {t}")

print("\n=== Try creating a project ===")
try:
    # Try to find a Create/New static method or constructor
    proj_type = None
    for t in types:
        cls = getattr(P, t, None)
        if cls and hasattr(cls, "Create"):
            print(f"  {t}.Create exists")
        if cls and "project" in t.lower():
            print(f"  Project-like type: {t}")
            proj_type = cls

    if proj_type:
        print(f"\n  Methods on {proj_type.__name__}:")
        for m in dir(proj_type):
            if not m.startswith("_"):
                print(f"    {m}")
except Exception as e:
    print(f"  err: {e}")
