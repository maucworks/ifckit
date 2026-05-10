"""
ifckit.components.materials — centralized material definitions.

Import in any component to avoid repeating the same dicts::

    from ifckit.components.materials import ALUMINUM, GLASS, VOID
"""

ALUMINUM = {
    "color": {"r": 0.8, "g": 0.8, "b": 0.8},
    "transparency": 0.0,
    "name": "Aluminum",
}

GLASS = {
    "color": {"r": 0.9, "g": 0.95, "b": 1.0},
    "transparency": 0.5,
    "name": "Clear glass",
}

DOOR_PANEL = {
    "color": {"r": 0.9, "g": 0.0, "b": 0.0},
    "transparency": 0.0,
    "name": "Door panel",
}

VOID = {
    "color": {"r": 0.5, "g": 0.5, "b": 0.5},
    "transparency": 1.0,
    "name": "Opening void",
}
