"""Adversarial tests for Issue #2 — trying to break the type validation."""

import pytest
import shutil
from pathlib import Path

from utils import is_valid_type
from dbms import DBMS


class TestAdversarialUtils:
    """Edge cases and attacks against is_valid_type()."""

    # --- INT edge cases ---
    def test_int_very_large_number_passes(self):
        assert is_valid_type("int", 10**18) is True

    def test_int_numpy_bool_fails(self):
        """numpy.bool_ is also a subclass of int in some versions."""
        try:
            import numpy as np
            assert is_valid_type("int", np.bool_(True)) is False
        except ImportError:
            pytest.skip("numpy not installed")

    def test_int_subclass_of_int_fails(self):
        """Custom int subclass should still be rejected if we were strict,
        but for now isinstance catches it. The plan only mentions bool."""
        class MyInt(int):
            pass
        # MyInt is still an int subclass — per plan, only bool is explicitly rejected
        assert is_valid_type("int", MyInt(5)) is True  # acceptable per current plan

    # --- CHAR edge cases ---
    def test_char_unicode_passes(self):
        assert is_valid_type("char(5)", "日本語") is True

    def test_char_emoji_boundary(self):
        """Emoji are multi-byte but len() counts codepoints."""
        assert is_valid_type("char(2)", "👍👍") is True
        assert is_valid_type("char(1)", "👍👍") is False

    def test_char_whitespace_passes(self):
        assert is_valid_type("char(5)", "   ") is True

    def test_char_newline_fails(self):
        assert is_valid_type("char(5)", "a\nb") is True  # len 3
        assert is_valid_type("char(2)", "a\nb") is False  # len 3 > 2

    def test_char_bytes_fails(self):
        assert is_valid_type("char(5)", b"hello") is False

    def test_char_list_fails(self):
        assert is_valid_type("char(5)", ["h", "i"]) is False

    # --- DATE edge cases ---
    def test_date_leap_year_feb29_passes(self):
        """Feb 29 on leap year — we accept since we only check 01-31."""
        assert is_valid_type("date", "2024-02-29") is True

    def test_date_non_leap_feb29_passes(self):
        """Feb 29 on non-leap year — our simple validation accepts it.
        Full calendar validation is future work per plan."""
        assert is_valid_type("date", "2023-02-29") is True

    def test_date_year_zero_passes(self):
        assert is_valid_type("date", "0000-01-01") is True

    def test_date_year_9999_passes(self):
        assert is_valid_type("date", "9999-12-31") is True

    def test_date_missing_leading_zero_fails(self):
        assert is_valid_type("date", "2023-1-01") is False
        assert is_valid_type("date", "2023-01-1") is False

    def test_date_extra_characters_fails(self):
        assert is_valid_type("date", "2023-01-01 ") is False
        assert is_valid_type("date", " 2023-01-01") is False

    def test_date_empty_string_fails(self):
        assert is_valid_type("date", "") is False

    def test_date_none_passes(self):
        assert is_valid_type("date", None) is True

    # --- General attacks ---
    def test_none_type_name_returns_false(self):
        """None type name should return False gracefully instead of crashing."""
        assert is_valid_type(None, 123) is False

    def test_empty_type_name_fails(self):
        assert is_valid_type("", 123) is False

    def test_malformed_char_type_returns_false(self):
        """Malformed char types should return False gracefully."""
        assert is_valid_type("char()", "test") is False
        assert is_valid_type("char(x)", "test") is False


class TestAdversarialDBMS:
    """Integration-level adversarial tests against DBMS.insert()."""

    @pytest.fixture
    def dbms(self):
        db_dir = Path("./DB")
        if db_dir.exists():
            shutil.rmtree(db_dir, ignore_errors=True)
        dbms = DBMS()
        dbms.create_table({
            "table_name": "attack_table",
            "column_list": [
                ("id", "int"),
                ("label", "char(5)"),
                ("created", "date"),
            ],
            "not_null_key_set": {"id"},
            "primary_key_list": [["id"]],
            "foreign_key_dict": {}
        })
        yield dbms
        import gc
        gc.collect()
        if db_dir.exists():
            shutil.rmtree(db_dir, ignore_errors=True)

    def test_rapid_inserts_same_pk_fails(self, dbms):
        """First insert succeeds, second with same PK should fail."""
        from messages import InsertDuplicatePrimaryKeyError
        dbms.insert({
            "table_name": "attack_table",
            "column_name_list": []
        }, [1, "a", "2023-01-01"])
        with pytest.raises(InsertDuplicatePrimaryKeyError):
            dbms.insert({
                "table_name": "attack_table",
                "column_name_list": []
            }, [1, "b", "2023-01-02"])

    def test_insert_bool_false_as_int_fails(self, dbms):
        """False is also a bool — must be rejected."""
        from messages import InsertTypeMismatchError
        with pytest.raises(InsertTypeMismatchError):
            dbms.insert({
                "table_name": "attack_table",
                "column_name_list": []
            }, [False, "x", "2023-01-01"])

    def test_insert_char_at_exact_boundary(self, dbms):
        """Exactly 5 chars for CHAR(5) should pass."""
        result = dbms.insert({
            "table_name": "attack_table",
            "column_name_list": []
        }, [2, "12345", "2023-01-01"])
        assert "inserted" in str(result).lower()

    def test_insert_char_one_over_boundary(self, dbms):
        """6 chars for CHAR(5) must fail."""
        from messages import InsertTypeMismatchError
        with pytest.raises(InsertTypeMismatchError):
            dbms.insert({
                "table_name": "attack_table",
                "column_name_list": []
            }, [3, "123456", "2023-01-01"])

    def test_insert_unicode_in_char(self, dbms):
        """Unicode within length should pass."""
        result = dbms.insert({
            "table_name": "attack_table",
            "column_name_list": []
        }, [4, "日本語", "2023-01-01"])
        assert "inserted" in str(result).lower()

    def test_insert_unicode_overflow_char(self, dbms):
        """Unicode exceeding length must fail."""
        from messages import InsertTypeMismatchError
        with pytest.raises(InsertTypeMismatchError):
            dbms.insert({
                "table_name": "attack_table",
                "column_name_list": []
            }, [5, "日本語ですよ", "2023-01-01"])  # 6 chars > char(5)

    def test_insert_all_null_except_not_null(self, dbms):
        """Only id is NOT NULL — should pass with id set and rest NULL."""
        result = dbms.insert({
            "table_name": "attack_table",
            "column_name_list": []
        }, [6, None, None])
        assert "inserted" in str(result).lower()
