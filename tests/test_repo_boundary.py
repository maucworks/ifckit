# This file was generated with the assistance of an AI coding tool.
"""Repo-boundary enforcement test — see tools/check_boundary.py and the
'Repo boundary' section in AGENTS.md."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_repo_boundary():
    """No check-out/admin/plan references anywhere in tracked content."""
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "tools" / "check_boundary.py")],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, f"repo-boundary violations:\n{proc.stdout}{proc.stderr}"
