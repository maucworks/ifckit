"""
gh_builder.py  —  Build ifckit-components.gh with Python 3 Script nodes
========================================================================

Run this inside Rhino 8 with Grasshopper open (a blank canvas is fine).

The script:
  1. Gets the active Grasshopper document (or creates one).
  2. Adds one "Python 3 Script" component per ifckit node.
  3. Configures inputs/outputs on each component.
  4. Sets the Python code on each component via the live editor API.
  5. Saves the document as ifckit-components.gh next to this script.

After running:
  - Open ifckit-components.gh in Grasshopper to verify.
  - ScriptEditor → File → Create Project → Add Components →
    select ifckit-components.gh → Build → install .gha.

Usage
-----
  Rhino 8 ScriptEditor → open this file → Run
  (Grasshopper must be open with at least a blank canvas)
"""

from __future__ import annotations
import os, sys, ast, time

import clr
clr.AddReference("Grasshopper")
clr.AddReference("GH_IO")
import Grasshopper as GH
import GH_IO.Serialization as GHSerial
import System.Drawing as SD
import System

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_OUT_GH   = os.path.join(_THIS_DIR, "ifckit-components.gh")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RELOAD_BOOTSTRAP = f"""\
import sys as _sys
_gh_json_dir = r'{_THIS_DIR}'
if _gh_json_dir not in _sys.path:
    _sys.path.insert(0, _gh_json_dir)
del _sys, _gh_json_dir

"""


def _read_body(filename: str) -> str:
    """Read a .py file, stripping the leading module docstring, then prepend
    a bootstrap that puts the gh_json directory on sys.path so that
    'import ifckit_reload' works regardless of the node's CWD."""
    path = os.path.join(_THIS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        src = f.read()
    try:
        tree = ast.parse(src)
        if (tree.body
                and isinstance(tree.body[0], ast.Expr)
                and isinstance(tree.body[0].value, ast.Constant)):
            end_line = tree.body[0].end_lineno
            lines = src.splitlines(keepends=True)
            body = "".join(lines[end_line:]).lstrip("\n")
            return _RELOAD_BOOTSTRAP + body
    except Exception:
        pass
    return _RELOAD_BOOTSTRAP + src


def _get_or_open_gh_doc():
    """Return the active GH document, opening Grasshopper if needed."""
    # Try active canvas first
    try:
        canvas = GH.Instances.ActiveCanvas
        if canvas is not None and canvas.Document is not None:
            return canvas.Document
    except Exception:
        pass

    # Open a new blank document
    try:
        GH.Instances.DocumentEditor.NewDocument(True)
        time.sleep(0.5)
        canvas = GH.Instances.ActiveCanvas
        if canvas is not None and canvas.Document is not None:
            return canvas.Document
    except Exception as e:
        print(f"  Could not open GH document: {e}")

    return None


def _find_proxy(name: str):
    """Find a component proxy by exact Name."""
    server = GH.Instances.ComponentServer
    for proxy in server.ObjectProxies:
        if str(proxy.Desc.Name) == name:
            return proxy
    return None


# ---------------------------------------------------------------------------
# Type / access constants
# ---------------------------------------------------------------------------

_STR   = "str"
_FLOAT = "float"
_BOOL  = "bool"
_CURVE = "curve"
_POINT = "point"
_GEN   = "generic"
_ITEM  = "item"
_LIST  = "list"

# TypeHintID GUIDs (from Rhino 8 GH source / empirical)
# These match the TypeHint GUIDs stored in component XML
_HINT_GUID = {
    _STR:   System.Guid("37261734-eec7-4f50-b6a8-b8d1f3c4396b"),  # GH_StringHint_CS
    _FLOAT: System.Guid("39fbc626-7a01-46ab-a18e-ec1c0c41685b"),  # GH_DoubleHint_CS
    _BOOL:  System.Guid("d60527f5-b5af-4ef6-8970-5f96fe412429"),  # GH_BooleanHint_CS
    _CURVE: System.Guid("6a184b65-baa3-42d1-a548-3915b401de53"),  # no-conversion (generic)
    _POINT: System.Guid("6a184b65-baa3-42d1-a548-3915b401de53"),  # no-conversion
    _GEN:   System.Guid("6a184b65-baa3-42d1-a548-3915b401de53"),  # no-conversion
}

# InputId / OutputId GUIDs (from XML introspection)
_SCRIPT_INPUT_GUID  = System.Guid("08908df5-fa14-4982-9ab2-1aa0927566aa")
_SCRIPT_OUTPUT_TEXT = System.Guid("3ede854e-c753-40eb-84cb-b48008f14fd4")  # text/out param
_SCRIPT_OUTPUT_GEN  = System.Guid("08908df5-fa14-4982-9ab2-1aa0927566aa")  # generic

def _output_guid_for_type(type_hint: str) -> System.Guid:
    if type_hint == _STR:
        return _SCRIPT_OUTPUT_TEXT
    return _SCRIPT_OUTPUT_GEN


# ---------------------------------------------------------------------------
# Component definitions
# ---------------------------------------------------------------------------

COMPONENTS = [
    {
        "nickname": "ifckit Profile",
        "tooltip":  "Create any ifckit profile (I, L, rect, circle, hollow_circle, steel). Outputs Profile.to_dict() JSON.",
        "panel":    "Profiles",
        "inputs": [
            ("profile_type",     _STR,   _ITEM, "Profile type: 'I','L','rect','circle','hollow_circle','steel'"),
            ("height",           _FLOAT, _ITEM, "Height or leg A (m)"),
            ("width",            _FLOAT, _ITEM, "Width or leg B (m)"),
            ("web_thickness",    _FLOAT, _ITEM, "Web thickness (m) — I-beam only"),
            ("flange_thickness", _FLOAT, _ITEM, "Flange/leg thickness (m)"),
            ("radius",           _FLOAT, _ITEM, "Radius (m) — circle/hollow_circle"),
            ("wall_thickness",   _FLOAT, _ITEM, "Wall thickness (m) — hollow_circle"),
            ("steel_name",       _STR,   _ITEM, "Steel section name, e.g. 'HEA200'"),
            ("unit",             _STR,   _ITEM, "Unit for steel dims: 'm' (default) or 'mm'"),
            ("name",             _STR,   _ITEM, "Optional profile label"),
        ],
        "outputs": [
            ("out",      _STR, _ITEM, "Status message"),
            ("json_out", _STR, _ITEM, "Profile JSON (Profile.to_dict() format)"),
        ],
        "source": "gh_profile.py",
    },
    {
        "nickname": "ifckit Beam",
        "tooltip":  "Create an IFC extruded beam from a line curve and a profile JSON.",
        "panel":    "Elements",
        "inputs": [
            ("line_curve",   _CURVE, _ITEM, "LineCurve defining the beam axis"),
            ("profile_pts",  _POINT, _LIST, "Cross-section polygon as Point3d list (fallback)"),
            ("profile_json", _STR,   _ITEM, "Profile JSON from ifckit Profile node"),
            ("name",         _STR,   _ITEM, "Optional element name"),
        ],
        "outputs": [
            ("out",      _STR, _ITEM, "Status message"),
            ("json_out", _GEN, _LIST, "List of element JSON strings"),
        ],
        "source": "gh_create_beam.py",
    },
    {
        "nickname": "ifckit Beam (Any Path)",
        "tooltip":  "Create an IFC beam from a line or arc curve. Auto-detects path type.",
        "panel":    "Elements",
        "inputs": [
            ("path_curve",   _CURVE, _ITEM, "LineCurve or ArcCurve defining the beam path"),
            ("profile_pts",  _POINT, _LIST, "Cross-section polygon as Point3d list (fallback)"),
            ("profile_json", _STR,   _ITEM, "Profile JSON from ifckit Profile node"),
            ("name",         _STR,   _ITEM, "Optional element name"),
        ],
        "outputs": [
            ("out",       _STR, _ITEM, "Status message"),
            ("path_type", _STR, _ITEM, "Detected path type"),
            ("json_out",  _GEN, _LIST, "List of element JSON strings"),
        ],
        "source": "gh_create_beam_any.py",
    },
    {
        "nickname": "ifckit Wall",
        "tooltip":  "Create an IFC wall from a base curve and height.",
        "panel":    "Elements",
        "inputs": [
            ("base_curve", _CURVE, _ITEM, "Base line curve of the wall"),
            ("height",     _FLOAT, _ITEM, "Wall height (m)"),
            ("thickness",  _FLOAT, _ITEM, "Wall thickness (m)"),
            ("name",       _STR,   _ITEM, "Optional element name"),
        ],
        "outputs": [
            ("out",      _STR, _ITEM, "Status message"),
            ("json_out", _GEN, _LIST, "List of element JSON strings"),
        ],
        "source": "gh_create_wall.py",
    },
    {
        "nickname": "ifckit Spaces",
        "tooltip":  "Create IFC spaces from boundary curves.",
        "panel":    "Elements",
        "inputs": [
            ("boundary_curves", _CURVE, _LIST, "Closed boundary curves"),
            ("height",          _FLOAT, _ITEM, "Space height (m)"),
            ("name",            _STR,   _ITEM, "Optional space name"),
        ],
        "outputs": [
            ("out",      _STR, _ITEM, "Status message"),
            ("json_out", _GEN, _LIST, "List of space JSON strings"),
        ],
        "source": "gh_spaces.py",
    },
    {
        "nickname": "ifckit Build JSON",
        "tooltip":  "Assemble element JSON strings into a storey/model JSON.",
        "panel":    "Export",
        "inputs": [
            ("element_jsons", _STR,   _LIST, "List of element JSON strings"),
            ("storey_name",   _STR,   _ITEM, "Storey name"),
            ("elevation",     _FLOAT, _ITEM, "Storey elevation (m)"),
        ],
        "outputs": [
            ("out",        _STR, _ITEM, "Status message"),
            ("model_json", _STR, _ITEM, "Full model JSON string"),
        ],
        "source": "gh_build_json.py",
    },
    {
        "nickname": "ifckit Export IFC",
        "tooltip":  "Export model JSON to an IFC file.",
        "panel":    "Export",
        "inputs": [
            ("model_json", _STR,  _ITEM, "Model JSON string from ifckit Build JSON"),
            ("filepath",   _STR,  _ITEM, "Output .ifc file path"),
            ("run",        _BOOL, _ITEM, "Set True to trigger export"),
        ],
        "outputs": [
            ("out", _STR, _ITEM, "Status / export path"),
        ],
        "source": "gh_export_json.py",
    },
    {
        "nickname": "ifckit Drawing",
        "tooltip":  "Generate section-plane drawing curves from an IFC file.",
        "panel":    "Drawing",
        "inputs": [
            ("ifc_path",     _STR,  _ITEM, "Path to .ifc file"),
            ("plane",        _GEN,  _ITEM, "Cutting plane (Rhino Plane)"),
            ("drawing_name", _STR,  _ITEM, "Drawing name"),
            ("run",          _BOOL, _ITEM, "Set True to trigger"),
        ],
        "outputs": [
            ("out", _STR, _ITEM, "Status message"),
        ],
        "source": "gh_drawing.py",
    },
    {
        "nickname": "ifckit SVG Curves",
        "tooltip":  "Import SVG curves onto Rhino layers.",
        "panel":    "Drawing",
        "inputs": [
            ("svg_path",   _STR,  _ITEM, "Path to .svg file"),
            ("dest_plane", _GEN,  _ITEM, "Destination plane (optional)"),
            ("run",        _BOOL, _ITEM, "Set True to trigger"),
        ],
        "outputs": [
            ("out", _STR, _ITEM, "Status message"),
        ],
        "source": "gh_svg_curves.py",
    },
]


# ---------------------------------------------------------------------------
# Core: add one component to a live GH document
# ---------------------------------------------------------------------------

def _add_component(doc, comp_def: dict, x: float, y: float):
    proxy = _find_proxy("Python 3 Script")
    if proxy is None:
        print("  ERR: 'Python 3 Script' proxy not found")
        return None

    comp = proxy.CreateInstance()
    if comp is None:
        print("  ERR: CreateInstance returned None")
        return None

    # Basic metadata
    comp.NickName   = comp_def["nickname"]
    comp.Name       = comp_def["nickname"]
    comp.Description = comp_def.get("tooltip", "")

    # Add to document FIRST so it is fully initialised
    comp.Attributes.Pivot = SD.PointF(x, y)
    doc.AddObject(comp, False)

    # --- Reconfigure inputs ---
    params = comp.Params
    # Remove default x, y inputs
    while params.Input.Count > 0:
        params.UnregisterInputParameter(params.Input[0], False)
    # Remove default a output (keep 'out' — actually remove all then re-add)
    while params.Output.Count > 0:
        params.UnregisterOutputParameter(params.Output[0], False)

    for (pname, ptype, paccess, pdesc) in comp_def["inputs"]:
        p = _make_input_param(pname, ptype, paccess, pdesc)
        params.RegisterInputParam(p)

    for (pname, ptype, paccess, pdesc) in comp_def["outputs"]:
        p = _make_output_param(pname, ptype, pdesc)
        params.RegisterOutputParam(p)

    params.OnParametersChanged()

    # --- Set code ---
    code = _read_body(comp_def["source"])
    _set_code(comp, code)

    return comp


def _make_input_param(name, type_hint, access, desc):
    """Create a typed Script input parameter."""
    import Grasshopper.Kernel.Parameters as GHP

    # For Script components, inputs are always the generic Script param type
    # We set TypeHintID via the XML round-trip below
    # Use Param_GenericObject as the container; type coercion is via TypeHintID
    p = GHP.Param_GenericObject()
    p.Name     = name
    p.NickName = name
    p.Description = desc
    p.Optional = True
    acc_map = {
        _ITEM: GH.Kernel.GH_ParamAccess.item,
        _LIST: GH.Kernel.GH_ParamAccess.list,
    }
    p.Access = acc_map.get(access, GH.Kernel.GH_ParamAccess.item)
    return p


def _make_output_param(name, type_hint, desc):
    import Grasshopper.Kernel.Parameters as GHP
    if type_hint == _STR:
        p = GHP.Param_String()
    else:
        p = GHP.Param_GenericObject()
    p.Name     = name
    p.NickName = name
    p.Description = desc
    p.Optional = True
    return p


def _find_chunk_end(xml: str, chunk_start: int) -> int:
    """
    Given the position of a '<chunk ' opening tag, return the index
    just past its matching '</chunk>' closing tag (handles nesting).
    Note: '<chunks ' (plural) is a different tag and must NOT be counted.
    """
    depth = 0
    pos = chunk_start
    while pos < len(xml):
        # find next opening <chunk  (singular, with space or >) — not <chunks
        o = -1
        search = pos
        while True:
            idx = xml.find("<chunk", search)
            if idx == -1:
                break
            # must be followed by space or > (not 's')
            next_ch = xml[idx + 6] if idx + 6 < len(xml) else ""
            if next_ch in (" ", ">", "\n", "\r", "\t"):
                o = idx
                break
            search = idx + 1

        c = xml.find("</chunk>", pos)

        if o == -1 and c == -1:
            break
        if o != -1 and (c == -1 or o < c):
            depth += 1
            pos = o + 1
        else:
            depth -= 1
            end = c + len("</chunk>")
            pos = c + 1
            if depth == 0:
                return end
    return -1


def _set_code(comp, code: str):
    """
    Set Python code on a live Python 3 Script component via XML round-trip.
    The Script chunk stores code as base64 in <item name="Text">.
    """
    import base64

    archive_out = GHSerial.GH_Archive()
    archive_out.AppendObject(comp, "Comp")
    xml = archive_out.Serialize_Xml()

    encoded = base64.b64encode(code.encode("utf-8")).decode("ascii")

    script_chunk = (
        '<chunk name="Script">'
        '<items count="2">'
        f'<item name="Text" type_name="gh_string" type_code="10">{encoded}</item>'
        f'<item name="Title" type_name="gh_string" type_code="10">{comp.NickName}</item>'
        '</items>'
        '<chunks count="1">'
        '<chunk name="LanguageSpec">'
        '<items count="2">'
        '<item name="Taxon" type_name="gh_string" type_code="10">*.*.python</item>'
        '<item name="Version" type_name="gh_string" type_code="10">3.*</item>'
        '</items>'
        '</chunk>'
        '</chunks>'
        '</chunk>'
    )

    # Locate the <chunk name="Comp"> block
    comp_tag = '<chunk name="Comp">'
    comp_start = xml.find(comp_tag)
    if comp_start == -1:
        print(f"  WARN: <chunk name='Comp'> not found in XML for {comp.NickName}")
        return False
    comp_end = _find_chunk_end(xml, comp_start)
    if comp_end == -1:
        print(f"  WARN: could not find end of Comp chunk for {comp.NickName}")
        return False

    comp_xml = xml[comp_start:comp_end]  # just the Comp chunk content

    if '<chunk name="Script">' in comp_xml:
        # Replace existing Script chunk inside Comp
        sc_start = comp_xml.index('<chunk name="Script">')
        sc_end   = _find_chunk_end(comp_xml, sc_start)
        comp_xml = comp_xml[:sc_start] + script_chunk + comp_xml[sc_end:]
    else:
        # Insert before the closing </chunk> of the Comp block
        # The Comp chunk ends with </chunks>\n</chunk> — insert before final </chunk>
        insert_at = comp_xml.rfind("</chunks>")
        if insert_at == -1:
            # No nested chunks yet — wrap in a chunks block
            inner_close = comp_xml.rfind("</chunk>")
            comp_xml = (
                comp_xml[:inner_close]
                + '<chunks count="1">' + script_chunk + '</chunks>'
                + comp_xml[inner_close:]
            )
        else:
            comp_xml = (
                comp_xml[:insert_at + len("</chunks>")]
                # bump the chunks count attribute on the parent — skip for now,
                # GH_IO recomputes counts on read
                + script_chunk
                + comp_xml[insert_at + len("</chunks>"):]
            )

    xml = xml[:comp_start] + comp_xml + xml[comp_end:]

    archive_in = GHSerial.GH_Archive()
    ok = archive_in.Deserialize_Xml(xml)
    if not ok:
        print(f"  WARN: Deserialize_Xml failed for {comp.NickName}")
        return False
    ok2 = archive_in.ExtractObject(comp, "Comp")
    if not ok2:
        print(f"  WARN: ExtractObject failed for {comp.NickName}")
        return False
    return True


def _reopen(path: str):
    """Close the current GH document and reopen the saved file."""
    try:
        editor = GH.Instances.DocumentEditor
        if editor is None:
            return
        # Open the saved file — GH will prompt to close the current doc;
        # use the OpenDocument API to bypass the prompt
        io = GH.Instances.DocumentIO
        new_doc = io.LoadDocument(path)
        if new_doc is None:
            print("  WARN: LoadDocument returned None — open manually")
            return
        editor.NewDocument(False)   # close current without saving
        time.sleep(0.2)
        GH.Instances.ActiveCanvas.Document = new_doc
        new_doc.NewSolution(False)
        print(f"  Reopened: {path}")
    except Exception as e:
        print(f"  WARN: auto-reopen failed ({e}) — open {path} manually")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build():
    doc = _get_or_open_gh_doc()
    if doc is None:
        print("ERROR: No active Grasshopper document. Open Grasshopper first.")
        return

    print(f"Using GH document: {doc.DisplayName or '(untitled)'}")

    col_spacing = 500
    row_spacing = 320
    x_base = 100
    y_base = 100

    panels = {}
    for cd in COMPONENTS:
        panels.setdefault(cd["panel"], []).append(cd)

    col = 0
    placed = 0
    for panel_name, comps in panels.items():
        for row, cd in enumerate(comps):
            x = x_base + col * col_spacing
            y = y_base + row * row_spacing
            comp = _add_component(doc, cd, float(x), float(y))
            if comp:
                print(f"  OK  {cd['nickname']}")
                placed += 1
            else:
                print(f"  FAIL {cd['nickname']}")
        col += 1

    # Save
    doc.ExpireSolution()
    archive = GHSerial.GH_Archive()
    archive.AppendObject(doc, "Definition")
    ok = archive.WriteToFile(_OUT_GH, True, False)

    print(f"\n{'='*50}")
    print(f"Placed {placed}/{len(COMPONENTS)} components")
    if ok:
        print(f"Saved: {_OUT_GH}")
        # Reopen the saved file so the live canvas reflects the injected code
        _reopen(_OUT_GH)
        print(f"\nNext: ScriptEditor → File → Create Project")
        print(f"      → Add Components → {_OUT_GH} → Build")
    else:
        print(f"ERROR: could not save to {_OUT_GH}")
    print(f"{'='*50}")


if __name__ == "__main__" or True:
    try:
        build()
    except Exception:
        import traceback
        print(f"FATAL:\n{traceback.format_exc()}")
