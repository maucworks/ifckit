"""
gh_introspect5.py  —  Dump the .rhproj file format by creating a minimal
project programmatically and serializing it, if possible.
Also find TypeHintID GUIDs for common parameter types.
Run inside Rhino 8 ScriptEditor.
"""
import clr
clr.AddReference("Grasshopper")
clr.AddReference("GH_IO")
import Grasshopper as GH
import GH_IO.Serialization as GHSerial
import os, glob

# --- 1. Find any .rhproj files on disk ---
print("=== Searching for .rhproj files ===")
search_paths = [
    os.path.expanduser("~/Documents"),
    os.path.expanduser("~/Desktop"),
    os.path.expanduser("~/.rhinocode"),
    "/Users/Mauc",
]
found = []
for base in search_paths:
    for root, dirs, files in os.walk(base):
        for f in files:
            if f.endswith(".rhproj"):
                found.append(os.path.join(root, f))
        # Don't recurse too deep
        depth = root.replace(base, "").count(os.sep)
        if depth >= 4:
            dirs[:] = []

if found:
    for p in found[:3]:
        print(f"\n--- {p} ---")
        try:
            with open(p) as f:
                print(f.read()[:3000])
        except Exception as e:
            print(f"  err: {e}")
else:
    print("  None found")

# --- 2. TypeHintID GUIDs: create typed params and serialize them ---
print("\n=== TypeHintID GUIDs for common types ===")
import Grasshopper.Kernel.Parameters as GHP
import Grasshopper.Kernel.Parameters.Hints as GHHints

hint_map = {}
for attr in dir(GHHints):
    if attr.startswith("_"):
        continue
    try:
        cls = getattr(GHHints, attr)
        obj = cls()
        if hasattr(obj, "HintID"):
            hint_map[attr] = str(obj.HintID)
            print(f"  {attr:40s} {obj.HintID}")
    except Exception:
        pass

# --- 3. Find GUIDs for the Script Input param proxies ---
print("\n=== Script param proxy GUIDs ===")
server = GH.Instances.ComponentServer
for proxy in server.ObjectProxies:
    name = str(proxy.Desc.Name)
    if "Script" in name and ("Input" in name or "Output" in name or "Parameter" in name):
        try:
            obj = proxy.CreateInstance()
            archive = GHSerial.GH_Archive()
            archive.AppendObject(obj, "P")
            xml = archive.Serialize_Xml()
            guid_lines = [l.strip() for l in xml.splitlines() if "guid" in l.lower() or "Guid" in l]
            print(f"  {name}: {guid_lines[:3]}")
        except Exception as e:
            print(f"  {name}: err {e}")
