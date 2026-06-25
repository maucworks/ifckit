# Style Guide

## Python

- **Line length**: 100 characters
- **Formatter**: `ruff format`
- **Linter**: `ruff check` (rules E, F, I, D)
- Configuration is in `pyproject.toml`
- Run `make lint` and `make fmt` before submitting.

## Docstrings

**Format**: Google-style (`Args:`, `Returns:`, `Raises:`).

**`__init__` parameters** are documented in the **class docstring**, not
in a separate `__init__` docstring. The `__init__` method carries no
docstring of its own; the class docstring covers all constructor
parameters in a single `Args:` block.

**`to_dict` / `from_dict`**: single-line:
```python
"""Serialise to a plain dict."""
"""Deserialize from a dict."""
```

**Properties and simple getters**: single-line, e.g.:
```python
"""Length of the vector."""
"""The element's start point as a Vec."""
```

**`build()` methods**: single-line describing what is built:
```python
"""Build and insert door components into the IFC model."""
```

**Modules**: every `.py` file (including `__init__.py`) has a module-level
docstring with the fully qualified module name as an RST heading followed
by a brief description:

```python
"""
ifckit.foo.bar
==============

Brief description of this module.
"""
```

## Commit Messages

- Subject line: **50 characters or less**, imperative mood.
- Use body to explain *why* (not *what*) when the subject isn't sufficient.
- Keep commits small and focused on a single concern.
