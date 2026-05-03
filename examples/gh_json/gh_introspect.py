"""
gh_introspect.py  —  Run inside Rhino 8 ScriptEditor to find the correct
type name for the new Python 3 Script component.
"""
import clr
clr.AddReference("Grasshopper")
import Grasshopper as GH

server = GH.Instances.ComponentServer
print("=== Searching for Python/Script components ===")
for proxy in server.ObjectProxies:
    name = str(proxy.Desc.Name).lower()
    full = str(proxy.Desc.Name)
    lib  = str(proxy.Desc.LibraryGuid) if hasattr(proxy.Desc, "LibraryGuid") else ""
    if any(k in name for k in ("python", "script", "cpython", "ironpython")):
        t = ""
        try:
            obj = proxy.CreateInstance()
            t = type(obj).__module__ + "." + type(obj).__name__ if obj else "(null)"
        except Exception as e:
            t = f"(err: {e})"
        print(f"  Name={full!r:40s}  Type={t}")
