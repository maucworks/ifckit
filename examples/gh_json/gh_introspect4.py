"""
gh_introspect4.py  —  Serialize a Python 3 Script component to XML and inspect
the structure, so we know what key to inject code under.
Run inside Rhino 8 ScriptEditor.
"""
import clr
clr.AddReference("Grasshopper")
clr.AddReference("GH_IO")
import Grasshopper as GH
import GH_IO.Serialization as GHSerial

server = GH.Instances.ComponentServer

for proxy in server.ObjectProxies:
    if str(proxy.Desc.Name) != "Python 3 Script":
        continue

    obj = proxy.CreateInstance()

    # Serialize via GH_Archive using AppendObject pattern
    archive = GHSerial.GH_Archive()
    archive.AppendObject(obj, "Component")
    xml = archive.Serialize_Xml()
    print("=== Serialized XML (Python 3 Script) ===")
    print(xml[:6000])
    break
