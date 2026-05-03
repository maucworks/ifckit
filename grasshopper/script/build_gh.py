"""
build_gh.py  —  Build ifckit-components.gh from grasshopper/src/*.py
=====================================================================

Run this inside Rhino 8 with Grasshopper open on a blank canvas:
    ScriptEditor → open this file → Run

For each *.py file in grasshopper/src/ the builder:
  1. Parses @component / @input / @output annotations from the docstring.
  2. Creates a "Python 3 Script" GH component via the GH proxy API.
  3. Injects typed params + script code entirely via XML surgery.
  4. Saves ifckit-components.gh in grasshopper/ and reopens it.

Annotation syntax (inside the module docstring)
------------------------------------------------
@component  nickname:"My Node"  tooltip:"Optional tooltip"
@group      "My Group"
@input   param_name : type  access — Description text
@output  param_name : type  access — Description text

Types   : str | float | bool | int | curve | point | plane | generic
Access  : item (default) | list | tree

Implementation approach — XML surgery
--------------------------------------
The Rhino 8 "Python 3 Script" component exposes its internal Script param
system (TypeHint, Access) through a `RhinoCodePlatform.GH` interface that is
inaccessible from IronPython/pythonnet because all types are generic
(`ScriptParamCTX\`1`) and cannot be resolved by name.

The working solution serialises a freshly-created component to XML via
`GH_Archive.Serialize_Xml()`, directly edits the XML string to replace the
`<chunk name="ParameterData">` block and inject a `<chunk name="Script">`
block, then deserialises back with `GH_Archive.Deserialize_Xml()` +
`ExtractObject()`.

Key XML facts discovered from a live fresh-component dump:
  - Each input/output is a <chunk name="InputParam" index="N"> with 12 items.
  - TypeHint is stored as `<item name="TypeHintID" type_name="gh_guid">`.
  - Access (item/list/tree) is `<item name="ScriptParamAccess" type_name="gh_int32">` (0/1/2).
  - The param type GUID in InputId/OutputId is 08908df5-fa14-4982-9ab2-1aa0927566aa.
  - Outputs must NOT include a TypeHintID item — GH Script raises a type-
    conversion error ("failed from string to object") if any hint GUID is
    present on an output param. Outputs use a 10-item chunk (no TypeHintID,
    no ShowTypeHints).
  - Language is identified by a nested `<chunk name="LanguageSpec">` with
    `<item name="Taxon">*.*.python</item>` and `<item name="Version">3.*</item>`.

TypeHintID values (confirmed from live GH instances):
  str    → 9e93878a-f9c5-4f0a-8a70-584bf09f24bb
  float  → 19ff81a2-dc4f-4035-8de9-26224c561321
  bool   → d60527f5-b5af-4ef6-8970-5f96fe412559
  int    → 48d01794-d3d8-4aef-990e-127168822244
  curve  → 9ba89ec2-5315-435f-a621-b66c5fa2f301
  point  → e1937b56-b1da-4c12-8bd8-e34ee81746ef
  plane  → 3897522d-58e9-4d60-b38c-978ddacfedd8
  generic → 00000000-0000-0000-0000-000000000000
"""

from __future__ import annotations
import ast
import base64
import glob
import os
import re
import time
import traceback
import uuid

import clr
clr.AddReference("Grasshopper")
clr.AddReference("GH_IO")

import Grasshopper as GH
import GH_IO.Serialization as GHSerial
import System.Drawing as SD

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_GH_DIR     = os.path.dirname(_SCRIPT_DIR)
_SRC_DIR    = os.path.join(_GH_DIR, "src")
_OUT_GH     = os.path.join(_GH_DIR, "ifckit-components.gh")

# ---------------------------------------------------------------------------
# Known GUIDs (confirmed from live Rhino session)
# ---------------------------------------------------------------------------

# TypeHintID values for ScriptParam — from HintID on each hint class
_HINT_ID = {
    "str":     "9e93878a-f9c5-4f0a-8a70-584bf09f24bb",  # GH_StringHint_CS
    "float":   "19ff81a2-dc4f-4035-8de9-26224c561321",  # GH_DoubleHint_CS
    "bool":    "d60527f5-b5af-4ef6-8970-5f96fe412559",  # GH_BooleanHint_CS
    "int":     "48d01794-d3d8-4aef-990e-127168822244",  # GH_IntegerHint_CS
    "curve":   "9ba89ec2-5315-435f-a621-b66c5fa2f301",  # GH_CurveHint
    "point":   "e1937b56-b1da-4c12-8bd8-e34ee81746ef",  # GH_Point3dHint
    "plane":   "3897522d-58e9-4d60-b38c-978ddacfedd8",  # GH_PlaneHint
    "generic": "00000000-0000-0000-0000-000000000000",  # GH_NullHint / no hint
}

# ComponentId for Param_ScriptVariable (the GH param type used by Script components)
_SCRIPT_PARAM_ID = "08908df5-fa14-4982-9ab2-1aa0927566aa"

# ComponentId for the standard output param (the "out" text output)
_OUT_PARAM_ID = "3ede854e-c753-40eb-84cb-b48008f14fd4"

# ScriptParamAccess values
_ACCESS = {"item": 0, "list": 1, "tree": 2}


# ---------------------------------------------------------------------------
# Annotation parser
# ---------------------------------------------------------------------------

_COMPONENT_RE = re.compile(
    r'@component\s+'
    r'nickname\s*:\s*"([^"]+)"'
    r'(?:\s+tooltip\s*:\s*"([^"]+)")?'
)
_GROUP_RE = re.compile(r'@group\s+"([^"]+)"')
_PARAM_RE = re.compile(
    r'@(input|output)\s+'
    r'(\w+)'
    r'\s*:\s*'
    r'(\w+)'
    r'\s+'
    r'(\w+)'
    r'(?:\s+[—-]\s*(.+))?'
)


def parse_annotations(src: str):
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None, [], []
    if not (tree.body
            and isinstance(tree.body[0], ast.Expr)
            and isinstance(tree.body[0].value, ast.Constant)):
        return None, [], []
    docstring = tree.body[0].value.value
    comp_match = _COMPONENT_RE.search(docstring)
    if not comp_match:
        return None, [], []
    group_match = _GROUP_RE.search(docstring)
    comp = {
        "nickname": comp_match.group(1),
        "group":    group_match.group(1) if group_match else "ifckit",
        "tooltip":  comp_match.group(2) or "",
    }
    inputs, outputs = [], []
    for m in _PARAM_RE.finditer(docstring):
        direction, name, ptype, access, desc = m.groups()
        entry = {
            "name":   name,
            "type":   ptype.lower(),
            "access": access.lower(),
            "desc":   (desc or "").strip(),
        }
        (inputs if direction == "input" else outputs).append(entry)
    return comp, inputs, outputs


# ---------------------------------------------------------------------------
# Source code helpers
# ---------------------------------------------------------------------------

def _read_body(filepath: str) -> str:
    """Return the script body with the module docstring converted to a comment block."""
    with open(filepath, "r", encoding="utf-8") as f:
        src = f.read()
    try:
        tree = ast.parse(src)
        if (tree.body
                and isinstance(tree.body[0], ast.Expr)
                and isinstance(tree.body[0].value, ast.Constant)):
            docstring  = tree.body[0].value.value
            end_line   = tree.body[0].end_lineno
            lines      = src.splitlines(keepends=True)
            body       = "".join(lines[end_line:]).lstrip("\n")
            comment    = "\n".join(f"# {l}" if l.strip() else "#" for l in docstring.splitlines())
            return comment + "\n\n" + body
    except Exception:
        pass
    return src


# ---------------------------------------------------------------------------
# XML builders
# ---------------------------------------------------------------------------

def _param_chunk(entry: dict, index: int, kind: str) -> str:
    """Build a <chunk name="InputParam"> or <chunk name="OutputParam"> XML fragment.

    Outputs omit TypeHintID and ShowTypeHints — GH Script components do not
    support type hints on outputs and will raise a type-conversion error if a
    hint GUID is present there.
    """
    is_output = kind == "OutputParam"
    hint_id   = _HINT_ID.get(entry["type"], _HINT_ID["generic"])
    access    = _ACCESS.get(entry["access"], 0)
    guid      = str(uuid.uuid4())
    name      = entry["name"]
    desc      = entry["desc"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    if is_output:
        return f'''        <chunk name="{kind}" index="{index}">
          <items count="10">
            <item name="AllowTreeAccess" type_name="gh_bool" type_code="1">true</item>
            <item name="Description" type_name="gh_string" type_code="10">{desc}</item>
            <item name="InstanceGuid" type_name="gh_guid" type_code="9">{guid}</item>
            <item name="Name" type_name="gh_string" type_code="10">{name}</item>
            <item name="NickName" type_name="gh_string" type_code="10">{name}</item>
            <item name="Optional" type_name="gh_bool" type_code="1">true</item>
            <item name="ScriptParamAccess" type_name="gh_int32" type_code="3">{access}</item>
            <item name="ScriptParameterVersion" type_name="gh_int32" type_code="3">2</item>
            <item name="SourceCount" type_name="gh_int32" type_code="3">0</item>
            <item name="ToolTip" type_name="gh_string" type_code="10"></item>
          </items>
        </chunk>'''

    return f'''        <chunk name="{kind}" index="{index}">
          <items count="12">
            <item name="AllowTreeAccess" type_name="gh_bool" type_code="1">true</item>
            <item name="Description" type_name="gh_string" type_code="10">{desc}</item>
            <item name="InstanceGuid" type_name="gh_guid" type_code="9">{guid}</item>
            <item name="Name" type_name="gh_string" type_code="10">{name}</item>
            <item name="NickName" type_name="gh_string" type_code="10">{name}</item>
            <item name="Optional" type_name="gh_bool" type_code="1">true</item>
            <item name="ScriptParamAccess" type_name="gh_int32" type_code="3">{access}</item>
            <item name="ScriptParameterVersion" type_name="gh_int32" type_code="3">2</item>
            <item name="ShowTypeHints" type_name="gh_bool" type_code="1">true</item>
            <item name="SourceCount" type_name="gh_int32" type_code="3">0</item>
            <item name="ToolTip" type_name="gh_string" type_code="10"></item>
            <item name="TypeHintID" type_name="gh_guid" type_code="9">{hint_id}</item>
          </items>
        </chunk>'''


def _parameter_data_chunk(inputs: list, outputs: list) -> str:
    """Build the <chunk name="ParameterData"> block."""
    n_in  = len(inputs)
    n_out = len(outputs)
    total_chunks = n_in + n_out
    total_items  = 2 + n_in + 2 + n_out  # InputCount + n InputId + OutputCount + n OutputId

    items = []
    items.append(f'<item name="InputCount" type_name="gh_int32" type_code="3">{n_in}</item>')
    for i in range(n_in):
        items.append(f'<item name="InputId" index="{i}" type_name="gh_guid" type_code="9">{_SCRIPT_PARAM_ID}</item>')
    items.append(f'<item name="OutputCount" type_name="gh_int32" type_code="3">{n_out}</item>')
    for i in range(n_out):
        items.append(f'<item name="OutputId" index="{i}" type_name="gh_guid" type_code="9">{_SCRIPT_PARAM_ID}</item>')

    items_xml = "\n            ".join(items)

    chunks = []
    for i, entry in enumerate(inputs):
        chunks.append(_param_chunk(entry, i, "InputParam"))
    for i, entry in enumerate(outputs):
        chunks.append(_param_chunk(entry, i, "OutputParam"))
    chunks_xml = "\n".join(chunks)

    return f'''      <chunk name="ParameterData">
          <items count="{total_items}">
            {items_xml}
          </items>
          <chunks count="{total_chunks}">
{chunks_xml}
          </chunks>
        </chunk>'''


def _script_chunk(code: str, nickname: str) -> str:
    """Build the <chunk name="Script"> block with base64-encoded code."""
    encoded = base64.b64encode(code.encode("utf-8")).decode("ascii")
    return f'''      <chunk name="Script">
          <items count="2">
            <item name="Text" type_name="gh_string" type_code="10">{encoded}</item>
            <item name="Title" type_name="gh_string" type_code="10">{nickname}</item>
          </items>
          <chunks count="1">
            <chunk name="LanguageSpec">
              <items count="2">
                <item name="Taxon" type_name="gh_string" type_code="10">*.*.python</item>
                <item name="Version" type_name="gh_string" type_code="10">3.*</item>
              </items>
            </chunk>
          </chunks>
        </chunk>'''


# ---------------------------------------------------------------------------
# XML round-trip: inject ParameterData + Script into component XML
# ---------------------------------------------------------------------------

def _find_chunk_end(xml: str, start: int) -> int:
    depth = 0
    pos   = start
    while pos < len(xml):
        o, c = -1, xml.find("</chunk>", pos)
        search = pos
        while True:
            idx = xml.find("<chunk", search)
            if idx == -1:
                break
            nc = xml[idx + 6] if idx + 6 < len(xml) else ""
            if nc in (" ", ">", "\n", "\r", "\t"):
                o = idx
                break
            search = idx + 1
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


def _inject_xml(comp, inputs: list, outputs: list, code: str, nickname: str) -> bool:
    """Serialize comp, replace ParameterData + inject Script chunk, deserialize back."""
    archive_out = GHSerial.GH_Archive()
    archive_out.AppendObject(comp, "Comp")
    xml = archive_out.Serialize_Xml()

    param_data_xml = _parameter_data_chunk(inputs, outputs)
    script_xml     = _script_chunk(code, nickname)

    # Locate <chunk name="Comp">
    comp_tag   = '<chunk name="Comp">'
    comp_start = xml.find(comp_tag)
    if comp_start == -1:
        print("    ERR: <chunk name='Comp'> not found")
        return False
    comp_end = _find_chunk_end(xml, comp_start)
    comp_xml = xml[comp_start:comp_end]

    # Replace <chunk name="ParameterData"> with our version
    pd_tag   = '<chunk name="ParameterData">'
    pd_start = comp_xml.find(pd_tag)
    if pd_start != -1:
        pd_end   = _find_chunk_end(comp_xml, pd_start)
        comp_xml = comp_xml[:pd_start] + param_data_xml + comp_xml[pd_end:]
    else:
        # Insert before closing </chunks> of comp
        close = comp_xml.rfind("</chunks>")
        comp_xml = comp_xml[:close] + param_data_xml + "\n" + comp_xml[close:]

    # Replace or insert <chunk name="Script">
    sc_tag   = '<chunk name="Script">'
    sc_start = comp_xml.find(sc_tag)
    if sc_start != -1:
        sc_end   = _find_chunk_end(comp_xml, sc_start)
        comp_xml = comp_xml[:sc_start] + script_xml + comp_xml[sc_end:]
    else:
        close    = comp_xml.rfind("</chunks>")
        comp_xml = comp_xml[:close] + script_xml + "\n" + comp_xml[close:]

    # Also fix the chunks count attribute in the Comp chunk's <chunks> tag
    # (count changes from 2 to 3 when Script is added)
    comp_xml = re.sub(r'(<chunks count=")(\d+)(">\s*<chunk name="Attributes">)',
                      lambda m: f'{m.group(1)}{int(m.group(2)) + (0 if sc_start != -1 else 1)}{m.group(3)}',
                      comp_xml, count=1)

    xml = xml[:comp_start] + comp_xml + xml[comp_end:]

    archive_in = GHSerial.GH_Archive()
    if not archive_in.Deserialize_Xml(xml):
        print("    ERR: Deserialize_Xml failed")
        return False
    if not archive_in.ExtractObject(comp, "Comp"):
        print("    ERR: ExtractObject failed")
        return False
    return True


# ---------------------------------------------------------------------------
# GH helpers
# ---------------------------------------------------------------------------

def _get_or_open_gh_doc():
    try:
        canvas = GH.Instances.ActiveCanvas
        if canvas is not None and canvas.Document is not None:
            return canvas.Document
    except Exception:
        pass
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
    for proxy in GH.Instances.ComponentServer.ObjectProxies:
        if str(proxy.Desc.Name) == name:
            return proxy
    return None


def _reopen(path: str):
    errors = []
    try:
        io = GH.GH_DocumentIO()
        io.Open(path)
        new_doc = io.Document
        if new_doc is None:
            raise RuntimeError("Document is None after Open()")
        GH.Instances.DocumentEditor.SetActiveDocument(new_doc, True)
        new_doc.NewSolution(False)
        print(f"  Reopened: {path}")
        return
    except Exception as e:
        errors.append(f"GH_DocumentIO: {e}")
    try:
        GH.Instances.DocumentEditor.ScriptAccess_OpenDocument(path)
        print(f"  Reopened: {path}")
        return
    except Exception as e:
        errors.append(f"ScriptAccess_OpenDocument: {e}")
    print(f"  WARN: auto-reopen failed — open {path} manually")
    for err in errors:
        print(f"    {err}")


# ---------------------------------------------------------------------------
# Add one component
# ---------------------------------------------------------------------------

def _add_component(doc, filepath: str, x: float, y: float):
    with open(filepath, "r", encoding="utf-8") as f:
        src = f.read()

    comp_meta, inputs, outputs = parse_annotations(src)
    if comp_meta is None:
        print(f"  SKIP {os.path.basename(filepath)} — no @component annotation")
        return None

    proxy = _find_proxy("Python 3 Script")
    if proxy is None:
        print("  ERR: 'Python 3 Script' proxy not found")
        return None

    comp = proxy.CreateInstance()
    if comp is None:
        print("  ERR: CreateInstance returned None")
        return None

    comp.NickName    = comp_meta["nickname"]
    comp.Name        = comp_meta["nickname"]
    comp.Description = comp_meta["tooltip"]
    comp.Attributes.Pivot = SD.PointF(x, y)
    doc.AddObject(comp, False)

    code   = _read_body(filepath)
    set_ok = _inject_xml(comp, inputs, outputs, code, comp_meta["nickname"])

    if set_ok:
        print(f"    {len(inputs)} in / {len(outputs)} out  ({len(code)} chars code)")
    else:
        print(f"    ERR: XML injection failed")

    return comp, comp_meta["group"]


# ---------------------------------------------------------------------------
# Panel colours  (ARGB — alpha=180 for a semi-transparent fill)
# ---------------------------------------------------------------------------

_PANEL_COLOURS = {
    "Elements": SD.Color.FromArgb(180, 152, 210, 140),  # green
    "Export":   SD.Color.FromArgb(180, 210, 163, 100),  # orange
    "Drawing":  SD.Color.FromArgb(180, 100, 175, 210),  # blue
    "Profiles": SD.Color.FromArgb(180, 185, 140, 210),  # purple
    "Import":   SD.Color.FromArgb(180, 210, 210, 110),  # yellow
}
_PANEL_COLOUR_DEFAULT = SD.Color.FromArgb(180, 180, 180, 180)  # grey


def _add_group(doc, panel_name: str, comp_list: list):
    """Add a GH_Group around all components in comp_list. Returns the group."""
    import Grasshopper.Kernel.Special as GHS
    group = GHS.GH_Group()
    group.NickName = panel_name
    colour = _PANEL_COLOURS.get(panel_name, _PANEL_COLOUR_DEFAULT)
    group.Colour = colour
    for comp in comp_list:
        group.AddObject(comp.InstanceGuid)
    doc.AddObject(group, False)
    return group


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build():
    doc = _get_or_open_gh_doc()
    if doc is None:
        print("ERROR: No active Grasshopper document.")
        return

    print(f"Using GH document: {doc.DisplayName or '(untitled)'}")
    print(f"Source dir: {_SRC_DIR}")

    src_files = sorted(glob.glob(os.path.join(_SRC_DIR, "gh_*.py")))
    if not src_files:
        print(f"ERROR: no gh_*.py files in {_SRC_DIR}")
        return

    # Group by panel
    panels: dict[str, list] = {}
    for fp in src_files:
        with open(fp) as f:
            src = f.read()
        comp_meta, _, _ = parse_annotations(src)
        panel = comp_meta["group"] if comp_meta else "_unknown"
        panels.setdefault(panel, []).append(fp)

    col_spacing = 250
    row_spacing = 160
    x_base, y_base = 100, 100

    placed = 0
    panel_comps: dict[str, list] = {}
    for col, (panel_name, files) in enumerate(panels.items()):
        panel_comps[panel_name] = []
        for row, fp in enumerate(files):
            x = x_base + col * col_spacing
            y = y_base + row * row_spacing
            print(f"\n  {os.path.basename(fp)}")
            try:
                result = _add_component(doc, fp, float(x), float(y))
            except Exception:
                traceback.print_exc()
                result = None
            if result:
                comp, panel = result
                panel_comps[panel_name].append(comp)
                print(f"  OK  {comp.NickName}  [{panel}]")
                placed += 1
            else:
                print(f"  FAIL")

    # Add colour-coded groups; collect their GUIDs for the supergroup
    group_guids = []
    for panel_name, comps in panel_comps.items():
        if comps:
            try:
                group = _add_group(doc, panel_name, comps)
                group_guids.append(group.InstanceGuid)
                print(f"  Group: {panel_name} ({len(comps)} components)")
            except Exception:
                traceback.print_exc()

    # Supergroup wrapping all panel groups
    if group_guids:
        try:
            import Grasshopper.Kernel.Special as GHS
            supergroup = GHS.GH_Group()
            supergroup.NickName = "ifckit"
            supergroup.Colour = SD.Color.FromArgb(60, 100, 100, 100)
            for guid in group_guids:
                supergroup.AddObject(guid)
            doc.AddObject(supergroup, False)
            print(f"  Supergroup: ifckit ({len(group_guids)} groups)")
        except Exception:
            traceback.print_exc()

    archive = GHSerial.GH_Archive()
    archive.AppendObject(doc, "Definition")
    ok = archive.WriteToFile(_OUT_GH, True, False)

    print(f"\n{'='*50}")
    print(f"Placed {placed}/{len(src_files)} components")
    if ok:
        print(f"Saved: {_OUT_GH}")
        _reopen(_OUT_GH)
    else:
        print(f"ERROR: could not save to {_OUT_GH}")
    print(f"{'='*50}")


if __name__ == "__main__" or True:
    try:
        build()
    except Exception:
        print(f"FATAL:\n{traceback.format_exc()}")
