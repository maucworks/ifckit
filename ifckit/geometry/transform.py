"""
ifckit.geometry.transform
=========================

4×4 affine transform (homogeneous coordinates).

Zero external dependencies — only stdlib math.

Usage::

    t = Transform.translation(Vec(10, 0, 0)) @ Transform.rotation(Vec(0, 0, 1), pi/4)
    v2 = t.apply(v)
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Tuple

from ifckit.geometry.primitives import Vec

if TYPE_CHECKING:
    from ifckit.geometry.primitives import Plane

# A 4×4 matrix stored as four row-tuples (row-major).
_Mat4 = Tuple[
    Tuple[float, float, float, float],
    Tuple[float, float, float, float],
    Tuple[float, float, float, float],
    Tuple[float, float, float, float],
]


class Transform:
    """4×4 homogeneous affine transform (row-major)."""

    __slots__ = ("m",)

    def __init__(self, m: _Mat4) -> None:
        self.m = m

    # ------------------------------------------------------------------
    # Static constructors
    # ------------------------------------------------------------------

    @staticmethod
    def identity() -> Transform:
        """Create an identity transform."""
        return Transform(
            (
                (1, 0, 0, 0),
                (0, 1, 0, 0),
                (0, 0, 1, 0),
                (0, 0, 0, 1),
            )
        )

    @staticmethod
    def translation(v: Vec) -> Transform:
        """Create a translation transform."""
        return Transform(
            (
                (1, 0, 0, v.x),
                (0, 1, 0, v.y),
                (0, 0, 1, v.z),
                (0, 0, 0, 1),
            )
        )

    @staticmethod
    def rotation(axis: Vec, angle: float) -> Transform:
        """Rotate around *axis* by *angle* radians (right-hand rule)."""
        k = axis.normalized()
        c = math.cos(angle)
        s = math.sin(angle)
        t = 1 - c
        x, y, z = k.x, k.y, k.z
        return Transform(
            (
                (t * x * x + c, t * x * y - s * z, t * x * z + s * y, 0),
                (t * x * y + s * z, t * y * y + c, t * y * z - s * x, 0),
                (t * x * z - s * y, t * y * z + s * x, t * z * z + c, 0),
                (0, 0, 0, 1),
            )
        )

    @staticmethod
    def scaling(sx: float, sy: float, sz: float) -> Transform:
        """Scale factor per axis (centered at world origin)."""
        return Transform(
            (
                (sx, 0, 0, 0),
                (0, sy, 0, 0),
                (0, 0, sz, 0),
                (0, 0, 0, 1),
            )
        )

    @staticmethod
    def uniform_scale(s: float) -> Transform:
        """Uniform scale centered at origin."""
        return Transform.scaling(s, s, s)

    @staticmethod
    def reflection(plane: "Plane") -> Transform:
        """Mirror over an arbitrary plane.

        *plane.z_axis* is the normal of the mirror plane.
        *plane.origin* is a point on the mirror plane.
        """
        from ifckit.geometry.primitives import Plane as _Plane

        plane = _Plane(plane.origin, plane.x_axis, plane.y_axis)
        n = plane.z_axis.normalized()
        # Householder: H = I - 2*n*n^T  (reflect through origin)
        H = Transform(
            (
                (1 - 2 * n.x * n.x, -2 * n.x * n.y, -2 * n.x * n.z, 0),
                (-2 * n.y * n.x, 1 - 2 * n.y * n.y, -2 * n.y * n.z, 0),
                (-2 * n.z * n.x, -2 * n.z * n.y, 1 - 2 * n.z * n.z, 0),
                (0, 0, 0, 1),
            )
        )
        # Compose: T(o) @ H @ T(-o)
        T_pos = Transform.translation(plane.origin)
        T_neg = Transform.translation(-plane.origin)
        return T_pos @ H @ T_neg

    # ------------------------------------------------------------------
    # Apply
    # ------------------------------------------------------------------

    def apply(self, v: Vec) -> Vec:
        """Transform *v* as a **point** (translates)."""
        x, y, z, w = self._mul(v.x, v.y, v.z, 1.0)
        if w != 1.0 and abs(w) > 1e-12:
            return Vec(x / w, y / w, z / w)
        return Vec(x, y, z)

    def apply_vector(self, v: Vec) -> Vec:
        """Transform *v* as a **direction** (ignores translation)."""
        x, y, z, _ = self._mul(v.x, v.y, v.z, 0.0)
        return Vec(x, y, z)

    def _mul(self, x: float, y: float, z: float, w: float) -> Tuple[float, float, float, float]:
        m = self.m
        return (
            m[0][0] * x + m[0][1] * y + m[0][2] * z + m[0][3] * w,
            m[1][0] * x + m[1][1] * y + m[1][2] * z + m[1][3] * w,
            m[2][0] * x + m[2][1] * y + m[2][2] * z + m[2][3] * w,
            m[3][0] * x + m[3][1] * y + m[3][2] * z + m[3][3] * w,
        )

    # ------------------------------------------------------------------
    # Composition
    # ------------------------------------------------------------------

    def __matmul__(self, other: Transform) -> Transform:
        """Compose: ``self @ other`` means apply *other* first, then *self*."""
        a = self.m
        b = other.m
        return Transform(
            (
                (
                    a[0][0] * b[0][0] + a[0][1] * b[1][0] + a[0][2] * b[2][0] + a[0][3] * b[3][0],
                    a[0][0] * b[0][1] + a[0][1] * b[1][1] + a[0][2] * b[2][1] + a[0][3] * b[3][1],
                    a[0][0] * b[0][2] + a[0][1] * b[1][2] + a[0][2] * b[2][2] + a[0][3] * b[3][2],
                    a[0][0] * b[0][3] + a[0][1] * b[1][3] + a[0][2] * b[2][3] + a[0][3] * b[3][3],
                ),
                (
                    a[1][0] * b[0][0] + a[1][1] * b[1][0] + a[1][2] * b[2][0] + a[1][3] * b[3][0],
                    a[1][0] * b[0][1] + a[1][1] * b[1][1] + a[1][2] * b[2][1] + a[1][3] * b[3][1],
                    a[1][0] * b[0][2] + a[1][1] * b[1][2] + a[1][2] * b[2][2] + a[1][3] * b[3][2],
                    a[1][0] * b[0][3] + a[1][1] * b[1][3] + a[1][2] * b[2][3] + a[1][3] * b[3][3],
                ),
                (
                    a[2][0] * b[0][0] + a[2][1] * b[1][0] + a[2][2] * b[2][0] + a[2][3] * b[3][0],
                    a[2][0] * b[0][1] + a[2][1] * b[1][1] + a[2][2] * b[2][1] + a[2][3] * b[3][1],
                    a[2][0] * b[0][2] + a[2][1] * b[1][2] + a[2][2] * b[2][2] + a[2][3] * b[3][2],
                    a[2][0] * b[0][3] + a[2][1] * b[1][3] + a[2][2] * b[2][3] + a[2][3] * b[3][3],
                ),
                (
                    a[3][0] * b[0][0] + a[3][1] * b[1][0] + a[3][2] * b[2][0] + a[3][3] * b[3][0],
                    a[3][0] * b[0][1] + a[3][1] * b[1][1] + a[3][2] * b[2][1] + a[3][3] * b[3][1],
                    a[3][0] * b[0][2] + a[3][1] * b[1][2] + a[3][2] * b[2][2] + a[3][3] * b[3][2],
                    a[3][0] * b[0][3] + a[3][1] * b[1][3] + a[3][2] * b[2][3] + a[3][3] * b[3][3],
                ),
            )
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def inverse(self) -> Transform:
        """Analytic inverse for affine transforms (last row = (0,0,0,1)).

        Returns the inverse matrix, or raises ValueError if singular.
        """
        m = self.m
        # 3×3 submatrix A
        a00, a01, a02 = m[0][0], m[0][1], m[0][2]
        a10, a11, a12 = m[1][0], m[1][1], m[1][2]
        a20, a21, a22 = m[2][0], m[2][1], m[2][2]

        det = (
            a00 * (a11 * a22 - a12 * a21)
            - a01 * (a10 * a22 - a12 * a20)
            + a02 * (a10 * a21 - a11 * a20)
        )
        if abs(det) < 1e-12:
            raise ValueError("Transform is singular, cannot invert")
        inv_det = 1.0 / det

        # Transpose of cofactor matrix = adj(A)
        # M^-1 = adj(A)^T / det
        r00 = (a11 * a22 - a12 * a21) * inv_det
        r01 = (a02 * a21 - a01 * a22) * inv_det
        r02 = (a01 * a12 - a02 * a11) * inv_det
        r10 = (a12 * a20 - a10 * a22) * inv_det
        r11 = (a00 * a22 - a02 * a20) * inv_det
        r12 = (a02 * a10 - a00 * a12) * inv_det
        r20 = (a10 * a21 - a11 * a20) * inv_det
        r21 = (a01 * a20 - a00 * a21) * inv_det
        r22 = (a00 * a11 - a01 * a10) * inv_det

        # Translation: -A^-1 @ t
        t0 = m[0][3]
        t1 = m[1][3]
        t2 = m[2][3]
        tx = -(r00 * t0 + r01 * t1 + r02 * t2)
        ty = -(r10 * t0 + r11 * t1 + r12 * t2)
        tz = -(r20 * t0 + r21 * t1 + r22 * t2)
        return Transform(
            (
                (r00, r01, r02, tx),
                (r10, r11, r12, ty),
                (r20, r21, r22, tz),
                (0, 0, 0, 1),
            )
        )

    def is_uniform_scale(self) -> bool:
        """True if the linear part preserves circles (uniform scale + rotation + reflection).

        Checks whether the 3×3 linear part has equal singular values.
        """
        m = self.m
        # Extract rows (or columns — same SingVal for orthogonal transforms)
        s0 = m[0][0] * m[0][0] + m[1][0] * m[1][0] + m[2][0] * m[2][0]
        s1 = m[0][1] * m[0][1] + m[1][1] * m[1][1] + m[2][1] * m[2][1]
        s2 = m[0][2] * m[0][2] + m[1][2] * m[1][2] + m[2][2] * m[2][2]
        # Also check row lengths
        r0 = m[0][0] * m[0][0] + m[0][1] * m[0][1] + m[0][2] * m[0][2]
        r1 = m[1][0] * m[1][0] + m[1][1] * m[1][1] + m[1][2] * m[1][2]
        r2 = m[2][0] * m[2][0] + m[2][1] * m[2][1] + m[2][2] * m[2][2]
        lengths = [s0, s1, s2, r0, r1, r2]
        return all(abs(val - lengths[0]) < 1e-6 for val in lengths)

    def __repr__(self) -> str:
        m = self.m
        return f"Transform(({m[0]}, {m[1]}, {m[2]}, {m[3]}))"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Transform):
            return False
        return self.m == other.m
