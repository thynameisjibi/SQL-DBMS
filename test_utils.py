"""Unit tests for utils.is_valid_type() per Issue #2 plan."""

import pytest
from utils import is_valid_type


class TestIntValidation:
    """Tests for INT type validation."""

    def test_int_positive_passes(self):
        assert is_valid_type("int", 123) is True

    def test_int_zero_passes(self):
        assert is_valid_type("int", 0) is True

    def test_int_negative_passes(self):
        assert is_valid_type("int", -42) is True

    def test_int_bool_true_fails(self):
        """Python bool is subclass of int — must be explicitly rejected."""
        assert is_valid_type("int", True) is False

    def test_int_bool_false_fails(self):
        assert is_valid_type("int", False) is False

    def test_int_string_fails(self):
        assert is_valid_type("int", "123") is False

    def test_int_float_fails(self):
        assert is_valid_type("int", 3.14) is False

    def test_int_none_passes(self):
        assert is_valid_type("int", None) is True


class TestCharValidation:
    """Tests for CHAR(N) type validation."""

    def test_char_short_string_passes(self):
        assert is_valid_type("char(5)", "abc") is True

    def test_char_exact_length_passes(self):
        assert is_valid_type("char(5)", "abcde") is True

    def test_char_overflow_fails(self):
        """Strings exceeding max length must be rejected, not truncated."""
        assert is_valid_type("char(5)", "abcdef") is False

    def test_char_empty_string_passes(self):
        assert is_valid_type("char(5)", "") is True

    def test_char_digit_string_passes(self):
        """Digit-only strings are valid for CHAR if within length."""
        assert is_valid_type("char(5)", "123") is True

    def test_char_not_string_fails(self):
        assert is_valid_type("char(5)", 123) is False

    def test_char_none_passes(self):
        assert is_valid_type("char(5)", None) is True


class TestDateValidation:
    """Tests for DATE type validation."""

    def test_date_valid_passes(self):
        assert is_valid_type("date", "2023-12-25") is True

    def test_date_first_day_passes(self):
        assert is_valid_type("date", "2023-01-01") is True

    def test_date_last_day_passes(self):
        assert is_valid_type("date", "2023-12-31") is True

    def test_date_invalid_month_fails(self):
        """Month must be 01-12."""
        assert is_valid_type("date", "2023-13-25") is False

    def test_date_month_zero_fails(self):
        assert is_valid_type("date", "2023-00-25") is False

    def test_date_invalid_day_fails(self):
        """Day must be 01-31."""
        assert is_valid_type("date", "2023-12-32") is False

    def test_date_day_zero_fails(self):
        assert is_valid_type("date", "2023-12-00") is False

    def test_date_not_string_fails(self):
        assert is_valid_type("date", 20231225) is False

    def test_date_bad_format_fails(self):
        assert is_valid_type("date", "25-12-2023") is False

    def test_date_none_passes(self):
        assert is_valid_type("date", None) is True


class TestEdgeCases:
    """Edge cases from plan."""

    def test_unknown_type_returns_false(self):
        assert is_valid_type("float", 3.14) is False

    def test_char_large_n_boundary(self):
        assert is_valid_type("char(100)", "x" * 100) is True
        assert is_valid_type("char(100)", "x" * 101) is False
