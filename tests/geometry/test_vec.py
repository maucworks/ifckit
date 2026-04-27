"""Tests for ifckit.geometry.Vec"""
import math
import pytest
from ifckit.geometry import Vec


def test_init_defaults():
    v = Vec()
    assert v.x == 0.0
    assert v.y == 0.0
    assert v.z == 0.0


def test_init_values():
    v = Vec(1, 2, 3)
    assert v.x == 1.0
    assert v.y == 2.0
    assert v.z == 3.0


def test_from_tuple():
    v = Vec.from_tuple((4.0, 5.0, 6.0))
    assert v == Vec(4, 5, 6)


def test_add():
    assert Vec(1, 2, 3) + Vec(4, 5, 6) == Vec(5, 7, 9)


def test_sub():
    assert Vec(5, 7, 9) - Vec(4, 5, 6) == Vec(1, 2, 3)


def test_mul():
    assert Vec(1, 2, 3) * 2 == Vec(2, 4, 6)


def test_rmul():
    assert 3 * Vec(1, 2, 3) == Vec(3, 6, 9)


def test_truediv():
    assert Vec(2, 4, 6) / 2 == Vec(1, 2, 3)


def test_neg():
    assert -Vec(1, -2, 3) == Vec(-1, 2, -3)


def test_abs_length():
    v = Vec(3, 4, 0)
    assert abs(v) == pytest.approx(5.0)


def test_dot():
    assert Vec(1, 0, 0) @ Vec(0, 1, 0) == pytest.approx(0.0)
    assert Vec(1, 2, 3) @ Vec(1, 2, 3) == pytest.approx(14.0)


def test_cross():
    result = Vec(1, 0, 0) ** Vec(0, 1, 0)
    assert result.equals(Vec(0, 0, 1))


def test_iter_unpack():
    x, y, z = Vec(1, 2, 3)
    assert (x, y, z) == (1.0, 2.0, 3.0)


def test_getitem():
    v = Vec(7, 8, 9)
    assert v[0] == 7.0
    assert v[1] == 8.0
    assert v[2] == 9.0


def test_len():
    assert len(Vec(1, 2, 3)) == 3


def test_eq():
    assert Vec(1, 2, 3) == Vec(1, 2, 3)
    assert Vec(1, 2, 3) != Vec(1, 2, 4)


def test_eq_non_vec():
    assert Vec(1, 2, 3) != (1, 2, 3)


def test_repr():
    assert repr(Vec(1, 2, 3)) == "Vec(1.0, 2.0, 3.0)"


def test_equals_fuzzy():
    a = Vec(1, 2, 3)
    b = Vec(1 + 1e-7, 2, 3)
    assert a.equals(b)
    assert not a.equals(Vec(1.1, 2, 3))


def test_length_method():
    assert Vec(0, 0, 5).length() == pytest.approx(5.0)


def test_length_squared():
    assert Vec(3, 4, 0).length_squared() == pytest.approx(25.0)


def test_normalized():
    v = Vec(0, 0, 5).normalized()
    assert v.equals(Vec(0, 0, 1))


def test_normalized_zero_raises():
    with pytest.raises(ValueError):
        Vec(0, 0, 0).normalized()


def test_lerp():
    a = Vec(0, 0, 0)
    b = Vec(10, 0, 0)
    assert a.lerp(b, 0.5).equals(Vec(5, 0, 0))
    assert a.lerp(b, 0.0).equals(a)
    assert a.lerp(b, 1.0).equals(b)


def test_distance_to():
    assert Vec(0, 0, 0).distance_to(Vec(3, 4, 0)) == pytest.approx(5.0)


def test_angle_to():
    a = Vec(1, 0, 0)
    b = Vec(0, 1, 0)
    assert a.angle_to(b) == pytest.approx(math.pi / 2)
    assert a.angle_to(a) == pytest.approx(0.0)


def test_signed_angle_to():
    x = Vec(1, 0, 0)
    y = Vec(0, 1, 0)
    z = Vec(0, 0, 1)
    assert x.signed_angle_to(y, z) == pytest.approx(math.pi / 2)
    assert y.signed_angle_to(x, z) == pytest.approx(-math.pi / 2)


def test_angle_to_plane():
    v = Vec(1, 0, 0)
    normal = Vec(0, 0, 1)
    assert v.angle_to_plane(normal) == pytest.approx(0.0)


def test_rotate_around_z():
    v = Vec(1, 0, 0)
    rotated = v.rotate_around(Vec(0, 0, 1), math.pi / 2)
    assert rotated.equals(Vec(0, 1, 0))


def test_rotate_around_full_circle():
    v = Vec(1, 0, 0)
    rotated = v.rotate_around(Vec(0, 0, 1), 2 * math.pi)
    assert rotated.equals(v)


def test_to_tuple():
    assert Vec(1, 2, 3).to_tuple() == (1.0, 2.0, 3.0)


def test_dot_method_alias():
    assert Vec(1, 2, 3).dot(Vec(1, 2, 3)) == pytest.approx(14.0)


def test_cross_method_alias():
    assert Vec(1, 0, 0).cross(Vec(0, 1, 0)).equals(Vec(0, 0, 1))
