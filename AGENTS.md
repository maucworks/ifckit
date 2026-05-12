# AGENTS.md

Guidelines for AI coding agents contributing to ifckit. This file is
intended to be read by all AI agents regardless of platform (Claude Code,
Copilot, Cursor, etc.) in addition to any tool-specific configuration files.

Human contributors using AI tools should also read this document carefully,
as they are responsible for ensuring their contributions comply with these
guidelines.

## Project Overview

ifckit is a framework-agnostic IFC builder library for architecture and
infrastructure. It provides Python classes to construct IFC models programmatically
without depending on a specific CAD host application.

## Licensing

All contributions must be compatible with the project's licensing:

- **ifckit library**: **GPL-3.0-or-later**
- See `COPYING` for the full license text.

There is no Contributor License Agreement (CLA). By submitting a pull request,
you agree that your contribution is licensed under the applicable license above.

## Indicating AI-Generated Code

Contributors must clearly indicate when code has been generated or
substantially written by an AI tool.

### Commits

Commits that modify existing code must include a note in the **body** of the
commit message (not the subject line) indicating that the change was
AI-generated. For example:

```
Fix off-by-one error in element iteration

The loop termination condition was incorrect when processing
IfcRelAggregates relationships.

Generated with the assistance of an AI coding tool.
```

### New Files

New files that are AI-generated must include a comment near the top of the
file indicating this:

```python
# This file was generated with the assistance of an AI coding tool.
```

### Pull Requests

Pull requests containing AI-generated code must indicate in the PR description
which parts of the contribution are AI-generated. If the entire PR is
AI-generated, state that clearly. If only specific commits or files are
AI-generated, identify them.

## Pull Request Guidelines

### Scope and Size

- Each pull request should address a **single issue or feature**.
- Do not mix unrelated changes (e.g., bug fixes with refactoring or style
  changes) in the same PR.
- Large pull requests should be broken down into **multiple small, standalone
  commits** that are each easy to review independently. Rewrite commit history
  for this purpose if necessary.
- PRs that are minimal, focused solutions to a specific problem are much more
  likely to be accepted.

### What to Avoid

- **Over-engineering**: Do not add features, abstractions, or configurability
  beyond what is needed to solve the immediate problem.
- **Scope creep**: Do not make changes to files or code that are not directly
  related to the task at hand.
- **Unnecessary additions**: Do not add docstrings, comments, type annotations,
  or error handling to code you did not otherwise need to change.
- **Cosmetic changes**: Do not reformat, rename, or reorganize code that is
  unrelated to your change.

## Commit Messages

- The **subject line** must be **50 characters or less**.
- Use the **imperative mood** (e.g., "Fix crash in wall builder", not
  "Fixed crash" or "Fixes crash").
- A commit message can be a single line if the purpose is obvious from the
  subject alone.
- Otherwise, add a blank line after the subject followed by a short explanation
  of a few lines in the body.

## Code Style

### Python

- **Line length**: 100 characters
- **Formatter**: ruff
- **Linter**: ruff (rules E, F, I)
- Configuration is in `pyproject.toml`

Run linters and formatters **before submitting** your pull request. Do not rely
on CI to catch formatting issues.

## Testing

- Pull requests with test coverage are **much more likely to be merged**.
- If tests are appropriate and feasible for your change, they should be
- included.
- Tests are not required for every change (e.g., documentation-only changes),
  but the expectation is that testable code changes come with tests.
- Tests use **pytest** and are located in the `tests/` directory.
- Run the existing test suite before submitting: `pytest tests/`

## Architecture Quick Reference

### Directory Structure

- `ifckit/` — Main Python package
  - `builders/` — Factory classes for walls, beams, slabs, doors/windows, spaces, bridges, openings, etc.
  - `components/` — JSON-based and Pythonic component definitions
  - `elements/` — Base element classes (building, bridge, space, openings, etc.)
  - `geometry/` — Geometry primitives (frames, paths)
  - `profiles/` — Cross-section profile classes (I-beam, L-beam, steel sections, etc.)
  - `schema/` — IFC schema introspection
  - `model.py` — IFC model wrapper
  - `handles.py` — Handle management
  - `validator.py` — IFC validation
- `tests/` — Test suite (pytest)
- `examples/` — Example scripts
- `grasshopper/` — Grasshopper (Rhino) integration
- `docs/` — Architecture and design documentation

### Dependencies

- **Runtime**: none required by default
- **Optional**: `ifcopenshell` for IFC file output
- **Python**: >= 3.9
