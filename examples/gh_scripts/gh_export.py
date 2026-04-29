"""
gh_export.py  —  GH Script component: "Export IFC"
====================================================

Paste the contents of this file into a Grasshopper Python 3 Script
component (Rhino 8+).  This component is the END of the execution chain.

Execution chain
---------------
    [Init done] --> [AddWall done] --> [AddBeam done] --> [Export trigger]

Wire the ``done`` output of the last element component to the ``trigger``
input here.  This guarantees all elements are in the model before export.

Component inputs
----------------
trigger     : bool — Wire from previous component's ``done`` output.
output_path : str  — Absolute path for the output IFC file, e.g.
                     "/Users/sander/output/model.ifc"
run         : bool — Boolean Toggle.  Set True to actually write the file.
                     When False the component reports how many elements are
                     in the model without writing anything.

Component outputs
-----------------
out : str — Status message (element count, file path, or error).

Workflow
--------
1. Set run=False while adjusting geometry.
2. When ready: set run=True → file is written.
3. To rebuild from scratch: flip run=False, reset Init (reset=True),
   then set run=True again.
"""

import scriptcontext as sc

done = False
out = ""

if not trigger:
    out = "Waiting for trigger."
elif "ifckit_model" not in sc.sticky:
    out = "ERROR: no model in sc.sticky — run Init first (reset=True)."
elif not output_path:
    out = "ERROR: output_path is empty."
elif not run:
    out = f"Model ready. Set run=True to export to:\n  {output_path}"
else:
    try:
        model = sc.sticky["ifckit_model"]
        model.export(output_path)
        done = True
        out = f"Exported to:\n  {output_path}"
    except Exception as exc:
        out = f"EXPORT FAILED: {exc}"
