"""
ifckit.elements.registry
=======================

Element type registry - single source of truth for element type → class mapping.

This registry provides a central place to register element types. Classes register
themselves automatically via the metaclass, so adding new element types requires
no manual registration.

Usage::

    from ifckit.elements.registry import ElementRegistry

    # Get class from type string
    cls = ElementRegistry.get("basic_wall")
    wall = cls.from_dict({...})

    # Get all registered types
    types = ElementRegistry.types()

    # Check if type exists
    if ElementRegistry.has("beam"):
        ...
"""

from typing import Dict, Type

# Common aliases for element types (e.g., "beam" -> "basic_beam")
_ELEMENT_ALIASES: Dict[str, str] = {
    "wall": "basic_wall",
    "beam": "basic_beam",
    "column": "basic_column",
    "slab": "basic_slab",
}


class ElementRegistry:
    """
    Registry mapping element_type strings to PendingElement subclasses.

    Uses a metaclass on PendingElement to auto-register subclasses when they
    are defined. This means adding a new element type requires no manual
    registration - just define the class with the `element_type` attribute.

    Also supports aliases (e.g., "beam" maps to "basic_beam").
    """

    _registry: Dict[str, Type] = {}

    @classmethod
    def register(cls, element_type: str, element_cls: Type) -> None:
        """Register an element class with its type string."""
        cls._registry[element_type] = element_cls

    @classmethod
    def get(cls, element_type: str) -> Type:
        """Get element class by type string.
        
        Supports both exact types and aliases (e.g., "beam" -> "basic_beam").
        """
        if element_type in cls._registry:
            return cls._registry[element_type]
        
        # Try alias
        alias_type = _ELEMENT_ALIASES.get(element_type)
        if alias_type and alias_type in cls._registry:
            return cls._registry[alias_type]
        
        raise KeyError(f"Unknown element type: {element_type!r}. Available: {list(cls._registry.keys())}")

    @classmethod
    def has(cls, element_type: str) -> bool:
        """Check if element type is registered."""
        return element_type in cls._registry or _ELEMENT_ALIASES.get(element_type) in cls._registry

    @classmethod
    def types(cls) -> Dict[str, Type]:
        """Get all registered types."""
        return dict(cls._registry)


class RegisterElementType(type):
    """
    Metaclass that auto-registers PendingElement subclasses.

    When a class inherits from PendingElement and defines `element_type`,
    this metaclass automatically registers it in the ElementRegistry.
    """

    def __new__(mcs, name: str, bases: tuple, namespace: dict) -> type:
        cls = super().__new__(mcs, name, bases, namespace)

        # Only register if this class defines element_type (not the base class)
        if "element_type" in namespace:
            element_type = namespace["element_type"]
            if element_type:  # Skip if empty string
                ElementRegistry.register(element_type, cls)

        return cls