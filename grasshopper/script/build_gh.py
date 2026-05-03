"""
build_gh.py  —  Build ifckit-components.gh from grasshopper/src/*.py
=====================================================================

Run this inside Rhino 8 with Grasshopper open on a blank canvas:
    ScriptEditor → open this file → Run

For each *.py file in grasshopper/src/ the builder:
  1. Parses @component / @input / @output annotations from the docstring.
  2. Creates a "Python 3 Script" GH component with the declared params.
  3. Injects the file's code (minus the docstring) via XML round-trip.
  4. Saves ifckit-components.gh in grasshopper/ and reopens it.

Annotation syntax (inside the module docstring)
------------------------------------------------
@component  nickname:"My Node"  panel:"My Panel"  tooltip:"Optional tooltip"
@input   param_name : type  access — Description text
@output  param_name : type  access — Description text

Types   : str | float | bool | int | curve | point | plane | generic
Access  : item (default) | list
"""

from __future__ import annotations
import ast
import glob
import os
import re
import sys
import time

import clr
clr.AddReference("Grasshopper")
clr.AddReference("GH_IO")
import Grasshopper as GH
import GH_IO.Serialization as GHSerial
import System
import System.Drawing as SD

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))          # grasshopper/script/
_GH_DIR     = os.path.dirname(_SCRIPT_DIR)                        # grasshopper/
_SRC_DIR    = os.path.join(_GH_DIR, "src")                        # grasshopper/src/
_OUT_GH     = os.path.join(_GH_DIR, "ifckit-components.gh")

# ---------------------------------------------------------------------------
# Annotation parser
# ---------------------------------------------------------------------------

_TYPE_MAP = {
    "str":     "str",
    "float":   "float",
    "bool":    "bool",
    "int":     "int",
    "curve":   "curve",
    "point":   "point",
    "plane":   "generic",
    "generic": "generic",
}

_ACCESS_MAP = {
    "item": "item",
    "list": "list",
}

_COMPONENT_RE = re.compile(
    r'@component\s+'
    r'nickname\s*:\s*"([^"]+)"'
    r'(?:\s+panel\s*:\s*"([^"]+)")?'
    r'(?:\s+tooltip\s*:\s*"([^"]+)")?'
)

_PARAM_RE = re.compile(
    r'@(input|output)\s+'
    r'(\w+)'           # param name
    r'\s*:\s*'
    r'(\w+)'           # type
    r'\s+'
    r'(\w+)'           # access
    r'(?:\s+—\s*(.+))?'  # optional description after em-dash
)


def parse_annotations(src: str):
    """
    Extract @component, @input, @output lines from the module docstring.

    Returns:
        comp  : dict with keys nickname, panel, tooltip
        inputs : list of dicts {name, type, access, desc}
        outputs: list of dicts {name, type, access, desc}
    Returns None if no @component line found.
    """
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

    comp = {
        "nickname": comp_match.group(1),
        "panel":    comp_match.group(2) or "ifckit",
        "tooltip":  comp_match.group(3) or "",
    }

    inputs, outputs = [], []
    for m in _PARAM_RE.finditer(docstring):
        direction, name, ptype, access, desc = m.groups()
        entry = {
            "name":   name,
            "type":   _TYPE_MAP.get(ptype.lower(), "generic"),
            "access": _ACCESS_MAP.get(access.lower(), "item"),
            "desc":   (desc or "").strip(),
        }
        (inputs if direction == "input" else outputs).append(entry)

    return comp, inputs, outputs


# ---------------------------------------------------------------------------
# Type-hint GUIDs  (from Rhino 8 empirical introspection)
# ---------------------------------------------------------------------------

_HINT_GUID = {
    "str":     System.Guid("37261734-eec7-4f50-b6a8-b8d1f3c4396b"),
    "float":   System.Guid("39fbc626-7a01-46ab-a18e-ec1c0c41685b"),
    "bool":    System.Guid("d60527f5-b5af-4ef6-8970-5f96fe412429"),
    "int":     System.Guid("39fbc626-7a01-46ab-a18e-ec1c0c41685b"),  # use double hint
    "curve":   System.Guid("6a184b65-baa3-42d1-a548-3915b401de53"),
    "point":   System.Guid("6a184b65-baa3-42d1-a548-3915b401de53"),
    "generic": System.Guid("6a184b65-baa3-42d1-a548-3915b401de53"),
}

_OUT_TEXT_GUID = System.Guid("3ede854e-c753-40eb-84cb-b48008f14fd4")
_OUT_GEN_GUID  = System.Guid("08908df5-fa14-4982-9ab2-1aa0927566aa")


# ---------------------------------------------------------------------------
# GH document helpers
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
    server = GH.Instances.ComponentServer
    for proxy in server.ObjectProxies:
        if str(proxy.Desc.Name) == name:
            return proxy
    return None


# ---------------------------------------------------------------------------
# Param factories
# ---------------------------------------------------------------------------

def _make_input_param(entry: dict):
    import Grasshopper.Kernel.Parameters as GHP
    p = GHP.Param_GenericObject()
    p.Name        = entry["name"]
    p.NickName    = entry["name"]
    p.Description = entry["desc"]
    p.Optional    = True
    p.Access = (GH.Kernel.GH_ParamAccess.list
                if entry["access"] == "list"
                else GH.Kernel.GH_ParamAccess.item)
    return p


def _make_output_param(entry: dict):
    import Grasshopper.Kernel.Parameters as GHP
    p = GHP.Param_GenericObject()
    p.Name        = entry["name"]
    p.NickName    = entry["name"]
    p.Description = entry["desc"]
    p.Optional    = True
    return p


# ---------------------------------------------------------------------------
# XML chunk helpers
# ---------------------------------------------------------------------------

def _find_chunk_end(xml: str, chunk_start: int) -> int:
    """Return index just past the closing </chunk> matching the one at chunk_start."""
    depth = 0
    pos = chunk_start
    while pos < len(xml):
        # find next <chunk  (singular) — NOT <chunks
        o = -1
        search = pos
        while True:
            idx = xml.find("<chunk", search)
            if idx == -1:
                break
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


def _set_code(comp, code: str) -> bool:
    """Inject Python code into a Python 3 Script component via XML round-trip."""
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

    comp_tag = '<chunk name="Comp">'
    comp_start = xml.find(comp_tag)
    if comp_start == -1:
        print(f"  WARN: <chunk name='Comp'> not found for {comp.NickName}")
        return False
    comp_end = _find_chunk_end(xml, comp_start)
    if comp_end == -1:
        print(f"  WARN: could not find end of Comp chunk for {comp.NickName}")
        return False

    comp_xml = xml[comp_start:comp_end]

    if '<chunk name="Script">' in comp_xml:
        sc_start = comp_xml.index('<chunk name="Script">')
        sc_end   = _find_chunk_end(comp_xml, sc_start)
        comp_xml = comp_xml[:sc_start] + script_chunk + comp_xml[sc_end:]
    else:
        insert_at = comp_xml.rfind("</chunks>")
        if insert_at == -1:
            inner_close = comp_xml.rfind("</chunk>")
            comp_xml = (comp_xml[:inner_close]
                        + '<chunks count="1">' + script_chunk + '</chunks>'
                        + comp_xml[inner_close:])
        else:
            comp_xml = (comp_xml[:insert_at + len("</chunks>")]
                        + script_chunk
                        + comp_xml[insert_at + len("</chunks>"):])

    xml = xml[:comp_start] + comp_xml + xml[comp_end:]

    archive_in = GHSerial.GH_Archive()
    if not archive_in.Deserialize_Xml(xml):
        print(f"  WARN: Deserialize_Xml failed for {comp.NickName}")
        return False
    if not archive_in.ExtractObject(comp, "Comp"):
        print(f"  WARN: ExtractObject failed for {comp.NickName}")
        return False
    return True


# ---------------------------------------------------------------------------
# Bootstrap prepended to every injected node body
# ---------------------------------------------------------------------------

_BOOTSTRAP = f"""\
import sys as _sys
_src_dir = r'{_SRC_DIR}'
if _src_dir not in _sys.path:
    _sys.path.insert(0, _src_dir)
del _sys, _src_dir

"""


def _read_body(filepath: str) -> str:
    """Read a src file, strip its docstring, prepend the bootstrap."""
    with open(filepath, "r", encoding="utf-8") as f:
        src = f.read()
    try:
        tree = ast.parse(src)
        if (tree.body
                and isinstance(tree.body[0], ast.Expr)
                and isinstance(tree.body[0].value, ast.Constant)):
            end_line = tree.body[0].end_lineno
            lines = src.splitlines(keepends=True)
            body = "".join(lines[end_line:]).lstrip("\n")
            return _BOOTSTRAP + body
    except Exception:
        pass
    return _BOOTSTRAP + src


# ---------------------------------------------------------------------------
# Add one component to the live GH document
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

    # Reconfigure params
    params = comp.Params
    while params.Input.Count > 0:
        params.UnregisterInputParameter(params.Input[0], False)
    while params.Output.Count > 0:
        params.UnregisterOutputParameter(params.Output[0], False)

    for entry in inputs:
        params.RegisterInputParam(_make_input_param(entry))
    for entry in outputs:
        params.RegisterOutputParam(_make_output_param(entry))

    params.OnParametersChanged()

    # Inject code
    code = _read_body(filepath)
    _set_code(comp, code)

    return comp, comp_meta["panel"]


# ---------------------------------------------------------------------------
# Reopen helper
# ---------------------------------------------------------------------------

def _reopen(path: str):
    try:
        io      = GH.Instances.DocumentIO
        new_doc = io.LoadDocument(path)
        if new_doc is None:
            print("  WARN: LoadDocument returned None — open manually")
            return
        editor = GH.Instances.DocumentEditor
        editor.NewDocument(False)
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
    print(f"Source dir: {_SRC_DIR}")

    # Gather src files in sorted order
    src_files = sorted(glob.glob(os.path.join(_SRC_DIR, "gh_*.py")))
    if not src_files:
        print(f"ERROR: no gh_*.py files found in {_SRC_DIR}")
        return

    col_spacing = 500
    row_spacing = 320
    x_base      = 100
    y_base      = 100

    # Group by panel to arrange in columns
    panels: dict[str, list] = {}
    for fp in src_files:
        with open(fp, "r", encoding="utf-8") as f:
            src = f.read()
        comp_meta, _, _ = parse_annotations(src)
        panel = comp_meta["panel"] if comp_meta else "_unknown"
        panels.setdefault(panel, []).append(fp)

    placed = 0
    col = 0
    for panel_name, files in panels.items():
        for row, fp in enumerate(files):
            x = x_base + col * col_spacing
            y = y_base + row * row_spacing
            result = _add_component(doc, fp, float(x), float(y))
            if result:
                comp, panel = result
                print(f"  OK  {comp.NickName}  [{panel}]")
                placed += 1
            else:
                print(f"  FAIL {os.path.basename(fp)}")
        col += 1

    # Save
    doc.ExpireSolution()
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
        import traceback
        print(f"FATAL:\n{traceback.format_exc()}")
