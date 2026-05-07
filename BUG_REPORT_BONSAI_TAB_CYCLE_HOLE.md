**Bug: IfcArbitraryProfileDefWithVoids hole disappears after TAB cycling**

**Version**
Tested with Bonsai latest (May 2025)

**Steps to reproduce**
1. Load IFC file containing IfcArbitraryProfileDefWithVoids profile
2. Observe window/door with visible hole (correct on initial load)
3. Press TAB to cycle through subobjects (select the lining/lining component)
4. Hole disappears, replaced by solid bounding box

**Expected behavior**
Hole remains visible after TAB cycling. The IfcArbitraryProfileDefWithVoids profile contains both outer curve and inner curves (voids) which should be preserved during representation rebuild.

**Actual behavior**
After TAB cycling, the representation rebuilds but the hole is no longer cut. The void inner curves are lost or not applied to the extrusion. A bounding box appears instead of the actual geometry.

**Test file**
Attached: hello_wall.ifc contains window components using IfcArbitraryProfileDefWithVoids for the lining profile with a hole.

**Notes**
- Initial render is correct. Bug triggers only on representation rebuild during subobject cycling.
- The sub-subobject (the profile definition) displays correctly when inspected separately.
- Issue occurs with the extruded geometry, not the profile definition itself.