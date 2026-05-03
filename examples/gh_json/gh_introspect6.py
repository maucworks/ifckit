"""
gh_introspect6.py  —  Inspect all default inputs/outputs on Python 3 Script,
and check for Script Source component structure.
Run inside Rhino 8 ScriptEditor.
"""
import clr
clr.AddReference("Grasshopper")
clr.AddReference("GH_IO")
import Grasshopper as GH
import GH_IO.Serialization as GHSerial

server = GH.Instances.ComponentServer

# --- Python 3 Script: list all default inputs/outputs ---
print("=== Python 3 Script default params ===")
for proxy in server.ObjectProxies:
    if str(proxy.Desc.Name) != "Python 3 Script":
        continue
    obj = proxy.CreateInstance()
    print(f"  Inputs ({obj.Params.Input.Count}):")
    for i in range(obj.Params.Input.Count):
        p = obj.Params.Input[i]
        print(f"    [{i}] Name={p.Name!r} NickName={p.NickName!r} TypeName={p.TypeName!r}")
    print(f"  Outputs ({obj.Params.Output.Count}):")
    for i in range(obj.Params.Output.Count):
        p = obj.Params.Output[i]
        print(f"    [{i}] Name={p.Name!r} NickName={p.NickName!r} TypeName={p.TypeName!r}")
    break

# --- Script Source: serialize to XML ---
print("\n=== Script Source serialized XML ===")
for proxy in server.ObjectProxies:
    if str(proxy.Desc.Name) != "Script Source":
        continue
    obj = proxy.CreateInstance()
    # list attrs
    for attr in ("Code", "Script", "ScriptSource", "Language", "LanguageSpec"):
        if hasattr(obj, attr):
            print(f"  has .{attr} = {repr(getattr(obj, attr))[:80]}")
    archive = GHSerial.GH_Archive()
    archive.AppendObject(obj, "ScriptSource")
    xml = archive.Serialize_Xml()
    print(xml[:3000])
    break
