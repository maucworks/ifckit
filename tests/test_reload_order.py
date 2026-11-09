# This file was generated with the assistance of an AI coding tool.
"""Reload-order coverage for import-time registries.

``RegisterProfileType._registry`` is populated when profile modules are
*executed*. ``reload_all()`` only re-executes modules listed in
``_RELOAD_ORDER`` — any concrete profile module missing from that list
silently drops out of the registry after a GH live-reload, and
``Profile.dispatch_from_dict`` then fails on its ``profile_type``
("Unknown profile_type 'derived'" in the Preview node).
"""

import importlib
import inspect
import pkgutil
import subprocess
import sys

import ifckit.profiles
import ifckit.reload
from ifckit.profiles.base import Profile


def _concrete_profile_modules():
    """Profile submodules defining a concrete Profile subclass."""
    found = []
    for info in pkgutil.iter_modules(ifckit.profiles.__path__):
        name = "ifckit.profiles." + info.name
        module = importlib.import_module(name)
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(obj, Profile)
                and obj is not Profile
                and obj.__module__ == module.__name__
                and getattr(obj, "profile_type", None)
            ):
                found.append(name)
                break
    return sorted(set(found))


def test_reload_order_covers_all_profile_modules():
    order = set(ifckit.reload._RELOAD_ORDER)
    missing = [m for m in _concrete_profile_modules() if m not in order]
    assert not missing, "profile modules missing from _RELOAD_ORDER: %r" % (missing,)


def test_dispatch_survives_reload_all():
    # Reload in a child process: reload_all() re-executes ifckit modules,
    # which rebinds enum/class identities — in-process that would poison
    # any later test still holding pre-reload references.
    code = (
        "import importlib, ifckit.profiles, ifckit.reload\n"
        "from ifckit.profiles.base import Profile, RegisterProfileType\n"
        "before = set(RegisterProfileType._registry.keys())\n"
        "assert 'derived' in before\n"
        "ifckit.reload.reload_all()\n"
        "after = set(RegisterProfileType._registry.keys())\n"
        "assert 'derived' in after\n"
        "assert before <= after\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=120
    )
    assert proc.returncode == 0, proc.stderr
