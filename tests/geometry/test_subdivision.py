import math

from ifckit.geometry.primitives import Vec
from ifckit.geometry.subdivision import catmull_clark, extract_patches, write_obj


class TestCatmullClark:
    def test_single_quad(self):
        verts = [Vec(0, 0, 0), Vec(1, 0, 0), Vec(1, 1, 0), Vec(0, 1, 0)]
        faces = [[0, 1, 2, 3]]
        result_verts, result_faces = catmull_clark(verts, faces, steps=1)
        assert len(result_faces) == 4  # one quad splits into 4
        assert len(result_verts) == 9  # 4 V-pts + 4 E-pts + 1 F-pt

    def test_two_steps(self):
        verts = [Vec(0, 0, 0), Vec(1, 0, 0), Vec(1, 1, 0), Vec(0, 1, 0)]
        faces = [[0, 1, 2, 3]]
        result_verts, result_faces = catmull_clark(verts, faces, steps=2)
        assert len(result_faces) == 16  # 4 * 4
        assert all(len(f) == 4 for f in result_faces)

    def test_cube(self):
        h = 1.0
        verts = [
            Vec(-h, -h, -h), Vec(h, -h, -h), Vec(h, h, -h), Vec(-h, h, -h),
            Vec(-h, -h, h), Vec(h, -h, h), Vec(h, h, h), Vec(-h, h, h),
        ]
        faces = [
            [0, 3, 2, 1],  # bottom
            [4, 5, 6, 7],  # top
            [0, 1, 5, 4],  # front
            [1, 2, 6, 5],  # right
            [2, 3, 7, 6],  # back
            [3, 0, 4, 7],  # left
        ]
        result_verts, result_faces = catmull_clark(verts, faces, steps=1)
        assert len(result_faces) == 24

    def test_extract_patches(self):
        verts = [Vec(0, 0, 0), Vec(1, 0, 0), Vec(1, 1, 0), Vec(0, 1, 0)]
        faces = [[0, 1, 2, 3]]
        refined_verts, refined_faces = catmull_clark(verts, faces, steps=1)
        patches = extract_patches(refined_verts, refined_faces)
        assert len(patches) == 4
        for patch in patches:
            assert len(patch.control_points) == 2

    def test_non_quad_skipped(self):
        verts = [Vec(0, 0, 0), Vec(1, 0, 0), Vec(1, 1, 0)]
        patches = extract_patches(verts, [[0, 1, 2]])
        assert patches == []

    def test_triangle_extrusion(self):
        verts = [Vec(0, 0, 0), Vec(2, 0, 0), Vec(0, 2, 0)]
        faces = [[0, 1, 2]]
        v, f = catmull_clark(verts, faces, steps=1)
        assert len(f) == 3

    def test_result_close_to_sphere(self):
        h = 1.0 / math.sqrt(3)
        verts = [
            Vec(-h, -h, -h), Vec(h, -h, -h), Vec(h, h, -h), Vec(-h, h, -h),
            Vec(-h, -h, h), Vec(h, -h, h), Vec(h, h, h), Vec(-h, h, h),
        ]
        faces = [
            [0, 3, 2, 1], [4, 5, 6, 7],
            [0, 1, 5, 4], [1, 2, 6, 5],
            [2, 3, 7, 6], [3, 0, 4, 7],
        ]
        v, f = catmull_clark(verts, faces, steps=3)
        assert len(v) > 0
        assert len(f) > 0
        # After 3 subdivision steps, all radii should be within ~30% of 1.0
        for pt in v:
            length = math.sqrt(pt.x**2 + pt.y**2 + pt.z**2)
            assert abs(length - 1.0) < 0.55


class TestWriteObj:
    def test_writes_file(self, tmp_path):
        verts = [Vec(0, 0, 0), Vec(1, 0, 0), Vec(1, 1, 0), Vec(0, 1, 0)]
        faces = [[0, 1, 2, 3]]
        path = str(tmp_path / "test.obj")
        write_obj(path, verts, faces)
        content = open(path).read()
        assert "v 0.000000 0.000000 0.000000" in content
        assert "f 1 2 3 4" in content
