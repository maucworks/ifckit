"""
tests/test_bonsai_hatch_map.py
================================

Unit tests for BONSAI_HATCH_MAP and _resolve_named_hatch_pattern()
in IfcSvgImporter — no Rhino needed (uses a mock doc).

M4.
"""
import sys
import types
import pytest

# ---------------------------------------------------------------------------
# Stub out Rhino so IfcSvgImporter can be imported without Rhino installed
# ---------------------------------------------------------------------------

def _make_rhino_stub():
    rhino = types.ModuleType("Rhino")
    rhino.RhinoDoc = types.SimpleNamespace(ActiveDoc=None)

    unit_system = types.ModuleType("Rhino.UnitSystem")
    unit_system.Millimeters = "mm"
    unit_system.Centimeters = "cm"
    unit_system.Meters = "m"
    unit_system.Feet = "ft"
    unit_system.Inches = "in"
    rhino.UnitSystem = unit_system

    sys.modules.setdefault("Rhino", rhino)
    sys.modules.setdefault("Rhino.UnitSystem", unit_system)


_make_rhino_stub()

from ifckit.rhino_import import BONSAI_HATCH_MAP, IfcSvgImporter  # noqa: E402


class _HatchPattern:
    def __init__(self, name):
        self.Name = name


class _HatchPatternsCollection:
    def __init__(self, names):
        self._items = [_HatchPattern(n) for n in names]

    @property
    def Count(self):
        return len(self._items)

    def __getitem__(self, idx):
        return self._items[idx]


class _MockDoc:
    def __init__(self, pattern_names):
        self.HatchPatterns = _HatchPatternsCollection(pattern_names)
        self.ModelUnitSystem = "mm"


def _make_importer(pattern_names=("Solid", "ANSI31", "Concrete", "Wood")):
    doc = _MockDoc(pattern_names)
    imp = object.__new__(IfcSvgImporter)  # bypass __init__ (needs Rhino)
    imp.doc = doc
    imp.layer_root = "IFC-SVG"
    imp.hatch_map = dict(BONSAI_HATCH_MAP)
    imp._layer_cache = {}
    imp._hatch_pattern_index = 0   # "Solid" is index 0
    imp._guid_hatch_index = {}
    return imp


# ---------------------------------------------------------------------------
# BONSAI_HATCH_MAP content
# ---------------------------------------------------------------------------

def test_bonsai_hatch_map_contains_solid():
    assert "Solid" in BONSAI_HATCH_MAP
    assert BONSAI_HATCH_MAP["Solid"] == "Solid"


def test_bonsai_hatch_map_contains_ansi31():
    assert "ANSI31" in BONSAI_HATCH_MAP


def test_bonsai_hatch_map_contains_concrete():
    assert "CONCRETE" in BONSAI_HATCH_MAP


# ---------------------------------------------------------------------------
# _resolve_named_hatch_pattern()
# ---------------------------------------------------------------------------

def test_resolve_known_pattern():
    imp = _make_importer()
    # "ANSI31" maps to "ANSI31", which is index 1 in mock doc
    idx = imp._resolve_named_hatch_pattern("ANSI31")
    assert idx == 1


def test_resolve_solid_returns_zero():
    imp = _make_importer()
    idx = imp._resolve_named_hatch_pattern("Solid")
    assert idx == 0


def test_resolve_concrete_via_map():
    imp = _make_importer()
    # BONSAI_HATCH_MAP["CONCRETE"] = "Concrete" → index 2 in mock doc
    idx = imp._resolve_named_hatch_pattern("CONCRETE")
    assert idx == 2


def test_resolve_unknown_name_falls_back_to_default():
    imp = _make_importer()
    imp._hatch_pattern_index = 0
    # "UNKNOWN_XYZ" not in map → fallback to default (0)
    idx = imp._resolve_named_hatch_pattern("UNKNOWN_XYZ")
    assert idx == 0


def test_resolve_direct_rhino_name():
    """A name not in hatch_map but matching a Rhino pattern directly."""
    imp = _make_importer()
    # "Wood" is not a Bonsai key but IS index 3 in the mock doc
    idx = imp._resolve_named_hatch_pattern("Wood")
    assert idx == 3


def test_hatch_map_can_be_overridden():
    imp = _make_importer()
    imp.hatch_map["CUSTOM"] = "ANSI31"
    idx = imp._resolve_named_hatch_pattern("CUSTOM")
    assert idx == 1
