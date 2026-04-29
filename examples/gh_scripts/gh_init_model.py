"""
gh_init_model.py  —  GH Script component: "Init IFC Model"
===========================================================

Paste the contents of this file into a Grasshopper Python 3 Script
component (Rhino 8+).

Execution chain
---------------
This component is the START of a forced-order chain:

    [Init] --done--> [AddWall trigger]
                     [AddWall done] --> [AddBeam trigger]
                                        [AddBeam done] --> [Export trigger]

Wire the ``done`` output of this component to the ``trigger`` input of the
first element component.  This guarantees that Init always completes before
any element is added, preventing stale-storey bugs after a model reset.

Component inputs
----------------
reset        : bool — Boolean Toggle.  Set True to (re-)initialise the
                      model.  Set back to False when done.
project_name : str  — IFC project name  (default "GH Project")
author       : str  — Author string stored in IFC header (default "GH")
use_mm       : bool — True  → LengthUnit.MILLIMETRE  (IFC convention)
                      False → LengthUnit.METRE

Component outputs
-----------------
done : bool — True when the model is ready in sc.sticky.
              Wire this to the ``trigger`` input of the next component.
out  : str  — Status message for a GH panel.
"""

import sys
import scriptcontext as sc

from ifckit import IfcModel, IfcSchema, LengthUnit

_project_name = project_name if project_name else "GH Project"
_author = author if author else "GH"
_unit = LengthUnit.MILLIMETRE if use_mm else LengthUnit.METRE

if reset:
    model = IfcModel(name=_project_name, schema=IfcSchema.IFC4, author=_author, unit=_unit)
    site = model.add_site("Site")
    bldg = site.add_building("Building")
    storey = bldg.add_storey("Ground Floor", elevation=0.0)

    sc.sticky["ifckit_model"] = model
    sc.sticky["ifckit_storey"] = storey

    done = True
    out = f"IfcModel '{_project_name}' initialised ({_unit.name})."
else:
    if "ifckit_model" in sc.sticky:
        done = True
        out = f"Model '{sc.sticky['ifckit_model'].name}' ready."
    else:
        done = False
        out = "No model. Set reset=True to initialise."
