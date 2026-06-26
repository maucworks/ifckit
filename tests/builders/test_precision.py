import pytest

from ifckit.builders._precision import get_precision, round_coord, set_precision


class TestSetPrecision:
    @pytest.mark.parametrize("d", [0, 4, 10])
    def test_valid_range(self, d):
        set_precision(d)
        assert get_precision() == d

    def test_negative_raises(self):
        with pytest.raises(ValueError, match="0-10"):
            set_precision(-1)

    def test_too_high_raises(self):
        with pytest.raises(ValueError, match="0-10"):
            set_precision(11)

    def test_non_int_raises(self):
        with pytest.raises(TypeError, match="must be int"):
            set_precision(3.5)

    def test_affects_rounding(self):
        set_precision(2)
        assert round_coord(1.23456789) == 1.23
        set_precision(5)
        assert round_coord(1.23456789) == 1.23457

    def test_restore_default(self):
        set_precision(4)
        assert get_precision() == 4
