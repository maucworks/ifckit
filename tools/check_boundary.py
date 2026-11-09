# This file was generated with the assistance of an AI coding tool.
"""Repo-boundary check: this library must never reference its check-out layer.

Enforced convention (see AGENTS.md → "Repo boundary"):

- No mention of the admin/checkout environment that hosts working clones:
  no plan paths, no admin repo names, no "monorepo"/"admin" vocabulary.
- Checked on (1) every git-tracked file at HEAD and (2) every commit that
  is not yet on the upstream remote — pending history is enforceable,
  shared history is project decision, not lint.

Run directly:  python tools/check_boundary.py
Runs as part of the default pytest suite: tests/test_repo_boundary.py.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Tokens that may never appear in tracked content or pending commit messages.
BLOCKLIST = [
    "196-ifckit-admin",
    "ifckit-admin",
    "admin repo",
    "admin environment",
    "admin workspace",
    "admin layer",
    "admin checkout",
    "monorepo",
    "plans/ifckit",
    "plans/plankit",
    "plans/geometrykit",
    "plans/__archive",
    "PLAN-minibim",
    "PLAN-plankit",
    "PLAN-occ-exit",
    "STRATEGY-ils",
]

_SKIP_PREFIXES = (".venv/", "node_modules/", ".git/")
#: The policy document legitimately names the forbidden tokens; skip it.
_SKIP_FILES = ("AGENTS.md", "tools/check_boundary.py")


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout


def scan_files() -> list[str]:
    """Scan every tracked file at HEAD; return violation lines."""
    hits: list[str] = []
    for path in [p for p in _git("ls-files").splitlines() if p]:
        if path.startswith(_SKIP_PREFIXES) or path in _SKIP_FILES:
            continue
        full = REPO_ROOT / path
        if (full.stat().st_size if full.exists() else 1 << 30) > 1 << 20:
            continue
        try:
            content = full.read_text(errors="replace")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(content.splitlines(), start=1):
            lower = line.lower()
            if any(tok in lower for tok in BLOCKLIST):
                hits.append(f"{path}:{lineno}: {line.strip()[:100]}")
    return hits


def scan_pending_commits() -> list[str]:
    """Scan commit subjects+bodies of commits not yet on the upstream remote."""
    hits: list[str] = []
    revs = "origin/master"
    try:
        _git("rev-parse", "--verify", "origin/master")
    except subprocess.CalledProcessError:
        revs = "@{u}" if _git("rev-parse", "--verify", "@{u}") else None
    log = _git("log", "--format=%s%n%b", f"{revs}..HEAD")
    sha = _git("log", "--format=%h", f"{revs}..HEAD").splitlines()
    for block in log.split("\n\n"):
        if not block.strip():
            continue
        if any(tok in block.lower() for tok in BLOCKLIST):
            first = block.strip().splitlines()[0][:100]
            hits.append(f"commit {sha.pop(0) if sha else '?'}: {first}")
    return hits


def main() -> int:
    violations = scan_files() + scan_pending_commits()
    if violations:
        print("Repo-boundary violations found (AGENTS.md → 'Repo boundary'):")
        for v in violations:
            print(f"  {v}")
        return 1
    print("boundary ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
