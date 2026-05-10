"""
ifckit.components.pythonic — auto-discovered Python generative components.

Any file ending in ``_component.py`` in this directory is imported and
its ``FillComponent`` subclass is registered in ``COMPONENT_REGISTRY``
keyed by the file name minus the ``_component`` suffix.

No decorator, ``name`` attribute, or ``register()`` call needed —
the component class just needs to inherit from ``FillComponent``.
"""

import importlib
import pkgutil

from ifckit.components import COMPONENT_REGISTRY, FillComponent

for _imp, _modname, _ispkg in pkgutil.iter_modules([__path__[0]]):
    if not _modname.endswith("_component"):
        continue
    _mod = importlib.import_module(f"{__name__}.{_modname}")
    for _attr_name in dir(_mod):
        _cls = getattr(_mod, _attr_name)
        if isinstance(_cls, type) and issubclass(_cls, FillComponent) and _cls is not FillComponent:
            _full_key = _modname
            _short_key = _modname.replace("_component", "")
            if _full_key not in COMPONENT_REGISTRY:
                COMPONENT_REGISTRY[_full_key] = _cls
            if _short_key not in COMPONENT_REGISTRY:
                COMPONENT_REGISTRY[_short_key] = _cls
            break
