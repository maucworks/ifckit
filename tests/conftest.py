"""Shared pytest fixtures for ifckit tests."""
import pytest


@pytest.fixture
def tmp_ifc_path(tmp_path):
    """A temporary .ifc file path."""
    return str(tmp_path / "test.ifc")
