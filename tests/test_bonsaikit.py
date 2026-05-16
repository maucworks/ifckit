"""Tests for ifckit.bonsaikit — conversion functions (requires no Blender)."""

import pytest
from ifckit.geometry import Plane, Vec


class TestConversions:
    def test_vector_from_bpy_sequence(self):
        from ifckit.bonsaikit import vector_from_bpy

        v = vector_from_bpy((3.0, 4.0, 5.0))
        assert isinstance(v, Vec)
        assert v.x == 3.0
        assert v.y == 4.0
        assert v.z == 5.0

    def test_vector_from_bpy_list(self):
        from ifckit.bonsaikit import vector_from_bpy

        v = vector_from_bpy([1.0, 2.0, 3.0])
        assert v.equals(Vec(1, 2, 3))

    def test_matrix_to_plane_identity(self):
        from ifckit.bonsaikit import matrix_to_plane

        m = [
            [1, 0, 0, 0],
            [0, 1, 0, 0],
            [0, 0, 1, 0],
            [0, 0, 0, 1],
        ]
        p = matrix_to_plane(m)
        assert isinstance(p, Plane)
        assert p.origin.equals(Vec(0, 0, 0))
        assert p.x_axis.equals(Vec(1, 0, 0))
        assert p.y_axis.equals(Vec(0, 1, 0))

    def test_matrix_to_plane_translation(self):
        from ifckit.bonsaikit import matrix_to_plane

        m = [
            [1, 0, 0, 10],
            [0, 1, 0, 20],
            [0, 0, 1, 30],
            [0, 0, 0, 1],
        ]
        p = matrix_to_plane(m)
        assert p.origin.equals(Vec(10, 20, 30))

    def test_matrix_to_plane_rotation(self):
        from ifckit.bonsaikit import matrix_to_plane

        # 90 deg rotation around Z: X->Y, Y->-X
        m = [
            [0, -1, 0, 0],
            [1, 0, 0, 0],
            [0, 0, 1, 0],
            [0, 0, 0, 1],
        ]
        p = matrix_to_plane(m)
        assert p.x_axis.equals(Vec(0, 1, 0))
        assert p.y_axis.equals(Vec(-1, 0, 0))

    def test_bonsai_import_guard(self):
        from ifckit.bonsaikit import vector_to_bpy, plane_to_matrix, _BONSAI_AVAILABLE

        # These should fail with ImportError when NOT running inside Blender
        with pytest.raises(ImportError):
            _ = vector_to_bpy(Vec(1, 2, 3))

        with pytest.raises(ImportError):
            _ = plane_to_matrix(Plane(Vec(0, 0, 0), Vec(1, 0, 0), Vec(0, 1, 0)))

    def test_require_bonsai_raises(self):
        from ifckit.bonsaikit import _require_bonsai

        with pytest.raises(ImportError, match="requires Blender"):
            _require_bonsai("test_fn")
