"""
gh_introspect2.py  —  Find exact type info for the Python 3 Script component.
Run inside Rhino 8 ScriptEditor.
"""
import clr
clr.AddReference("Grasshopper")
import Grasshopper as GH

server = GH.Instances.ComponentServer
targets = ["Python 3 Script", "Script", "IronPython 2 Script", "GhPython Script"]

for proxy in server.ObjectProxies:
    full = str(proxy.Desc.Name)
    if full not in targets:
        continue

    print(f"\n=== {full!r} ===")
    print(f"  proxy type       : {type(proxy).__module__}.{type(proxy).__name__}")
    print(f"  proxy.Desc type  : {type(proxy.Desc).__module__}.{type(proxy.Desc).__name__}")

    # Guid
    try:
        print(f"  ComponentGuid    : {proxy.Desc.ComponentGuid}")
    except Exception as e:
        print(f"  ComponentGuid    : err {e}")

    # Assembly / namespace of proxy itself
    try:
        asm = type(proxy).__module__
        print(f"  proxy module     : {asm}")
    except Exception:
        pass

    # Instantiate and get concrete type
    try:
        obj = proxy.CreateInstance()
        if obj is not None:
            ct = type(obj)
            print(f"  instance type    : {ct.__module__}.{ct.__name__}")
            print(f"  instance bases   : {[b.__name__ for b in ct.__bases__]}")
            # Check for Script/Code attribute
            for attr in ("Script", "Code", "ScriptSource", "PythonScript",
                         "LanguageSpec", "ScriptLanguage", "Params"):
                if hasattr(obj, attr):
                    val = getattr(obj, attr)
                    print(f"  has .{attr:20s}: {type(val).__name__}")
    except Exception as e:
        print(f"  CreateInstance   : err {e}")
