"""
gh_introspect3.py  —  Deep-dive into Python 3 Script component params and code storage.
Run inside Rhino 8 ScriptEditor.
"""
import clr
clr.AddReference("Grasshopper")
import Grasshopper as GH

server = GH.Instances.ComponentServer

for proxy in server.ObjectProxies:
    if str(proxy.Desc.Name) != "Python 3 Script":
        continue

    obj = proxy.CreateInstance()
    params = obj.Params

    print("=== Python 3 Script — all attributes ===")
    all_attrs = [a for a in dir(obj) if not a.startswith("__")]
    for a in all_attrs:
        try:
            val = getattr(obj, a)
            if callable(val):
                print(f"  method: {a}")
            else:
                print(f"  attr  : {a} = {repr(val)[:80]}")
        except Exception as e:
            print(f"  attr  : {a} => err: {e}")

    print("\n=== Params methods ===")
    for a in dir(params):
        if not a.startswith("__"):
            print(f"  {a}")

    print("\n=== Params.Input[0] attrs (if any) ===")
    try:
        if params.Input.Count > 0:
            p = params.Input[0]
            for a in dir(p):
                if not a.startswith("__"):
                    try:
                        print(f"  {a} = {repr(getattr(p, a))[:60]}")
                    except Exception:
                        print(f"  {a}")
    except Exception as e:
        print(f"  err: {e}")
    break
