"""
gh_introspect8.py  —  Serialize a Python 3 Script component that has code
set via the live editor, to find the exact XML key for code storage.

Steps:
1. Run this script AFTER you have double-clicked a Python 3 Script component
   and typed some code in it (e.g. "a = x + 1").
2. The script finds the first Python 3 Script component on the active canvas
   and dumps its full serialized XML.

Run inside Rhino 8 ScriptEditor with Grasshopper open.
"""
import clr
clr.AddReference("Grasshopper")
clr.AddReference("GH_IO")
import Grasshopper as GH
import GH_IO.Serialization as GHSerial

doc = GH.Instances.ActiveCanvas.Document
if doc is None:
    print("ERROR: no active GH document")
else:
    found = None
    for obj in doc.Objects:
        if "Python 3" in str(obj.Name) or "Py3" in str(obj.NickName):
            found = obj
            break

    if found is None:
        print("No Python 3 Script component found on canvas.")
        print("Drop one, type some code in it, then re-run this script.")
    else:
        print(f"Found: {found.Name!r} / {found.NickName!r}")
        archive = GHSerial.GH_Archive()
        archive.AppendObject(found, "Component")
        xml = archive.Serialize_Xml()
        print("=== Full XML ===")
        print(xml)
