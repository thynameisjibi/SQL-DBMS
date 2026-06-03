"""Integration tests for DBMS.insert() type validation per Issue #2 plan."""

import pytest
import shutil
from pathlib import Path

from dbms import DBMS
from messages import (
    InsertTypeMismatchError,
    InsertColumnNonNullableError,
)


@pytest.fixture
def dbms():
    """Provide a fresh DBMS instance with clean DB directory."""
    db_dir = Path("./DB")
    if db_dir.exists():
        shutil.rmtree(db_dir)
    dbms = DBMS()
    # Create a test table with various types
    dbms.create_table({
        "table_name": "test_table",
        "column_list": [
            ("id", "int"),
            ("name", "char(10)"),
            ("birth_date", "date"),
        ],
        "not_null_key_set": {"id"},
        "primary_key_list": [["id"]],
        "foreign_key_dict": {}
    })
    yield dbms
    # Cleanup
    import gc
    gc.collect()
    if db_dir.exists():
        shutil.rmtree(db_dir, ignore_errors=True)


class TestInsertValidCases:
    """Valid INSERT cases should succeed."""

    def test_insert_valid_int_char_date(self, dbms):
        result = dbms.insert({
            "table_name": "test_table",
            "column_name_list": []
        }, [1, "alice", "2023-12-25"])
        assert "inserted" in str(result).lower()

    def test_insert_with_null_for_nullable(self, dbms):
        result = dbms.insert({
            "table_name": "test_table",
            "column_name_list": []
        }, [1, None, None])
        assert "inserted" in str(result).lower()

    def test_insert_exact_char_length(self, dbms):
        """CHAR(10) with exactly 10 characters should pass."""
        result = dbms.insert({
            "table_name": "test_table",
            "column_name_list": []
        }, [2, "a" * 10, "2023-01-01"])
        assert "inserted" in str(result).lower()

    def test_insert_empty_string_char(self, dbms):
        result = dbms.insert({
            "table_name": "test_table",
            "column_name_list": []
        }, [3, "", "2023-06-15"])
        assert "inserted" in str(result).lower()


class TestInsertInvalidTypeCases:
    """Invalid type INSERT cases should raise InsertTypeMismatchError."""

    def test_insert_bool_as_int_fails(self, dbms):
        with pytest.raises(InsertTypeMismatchError):
            dbms.insert({
                "table_name": "test_table",
                "column_name_list": []
            }, [True, "alice", "2023-12-25"])

    def test_insert_string_as_int_fails(self, dbms):
        with pytest.raises(InsertTypeMismatchError):
            dbms.insert({
                "table_name": "test_table",
                "column_name_list": []
            }, ["not_an_int", "alice", "2023-12-25"])

    def test_insert_char_overflow_fails(self, dbms):
        """CHAR(10) with 11 characters must be rejected, not truncated."""
        with pytest.raises(InsertTypeMismatchError):
            dbms.insert({
                "table_name": "test_table",
                "column_name_list": []
            }, [1, "a" * 11, "2023-12-25"])

    def test_insert_int_as_char_fails(self, dbms):
        with pytest.raises(InsertTypeMismatchError):
            dbms.insert({
                "table_name": "test_table",
                "column_name_list": []
            }, [1, 12345, "2023-12-25"])

    def test_insert_invalid_date_month_fails(self, dbms):
        with pytest.raises(InsertTypeMismatchError):
            dbms.insert({
                "table_name": "test_table",
                "column_name_list": []
            }, [1, "alice", "2023-13-25"])

    def test_insert_invalid_date_day_fails(self, dbms):
        with pytest.raises(InsertTypeMismatchError):
            dbms.insert({
                "table_name": "test_table",
                "column_name_list": []
            }, [1, "alice", "2023-12-32"])

    def test_insert_bad_date_format_fails(self, dbms):
        with pytest.raises(InsertTypeMismatchError):
            dbms.insert({
                "table_name": "test_table",
                "column_name_list": []
            }, [1, "alice", "25-12-2023"])


class TestInsertNullConstraints:
    """NOT NULL constraint tests."""

    def test_insert_null_not_nullable_fails(self, dbms):
        with pytest.raises(InsertColumnNonNullableError):
            dbms.insert({
                "table_name": "test_table",
                "column_name_list": []
            }, [None, "alice", "2023-12-25"])

    def test_insert_null_for_nullable_passes(self, dbms):
        """name and birth_date are nullable — NULL should be allowed."""
        result = dbms.insert({
            "table_name": "test_table",
            "column_name_list": []
        }, [42, None, None])
        assert "inserted" in str(result).lower()
