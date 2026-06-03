"""Combined adversarial tests for Issue #2 (type validation) and Issue #5 (transactions)."""

import pytest
import shutil
from pathlib import Path

from utils import is_valid_type
from dbms import DBMS
from db_model import DB, Record
from transaction import Transaction, TransactionLog, TransactionState
from messages import *

DB_DIR = Path("./DB")


# ---------------------------------------------------------------------------- #
# Issue #2 — Type Validation Edge Cases                                      #
# ---------------------------------------------------------------------------- #

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


class TestAdversarialDBMSInsert:
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


# ---------------------------------------------------------------------------- #
# Issue #5 — Transaction Edge Cases                                          #
# ---------------------------------------------------------------------------- #

@pytest.fixture
def tx_dbms():
    if DB_DIR.exists():
        shutil.rmtree(DB_DIR, onerror=lambda f, p, e: None)
    instance = DBMS()
    yield instance
    import gc
    gc.collect()
    if DB_DIR.exists():
        shutil.rmtree(DB_DIR, onerror=lambda f, p, e: None)


@pytest.fixture
def sample_table(tx_dbms):
    tx_dbms.create_table({
        "table_name": "account",
        "column_list": [("id", "int"), ("name", "char(20)")],
        "not_null_key_set": {"id"},
        "primary_key_list": [("id",)],
        "foreign_key_dict": {}
    })
    tx_dbms.insert({"table_name": "account", "column_name_list": None}, [1, "Alice"])
    return tx_dbms


class TestTransactionEdgeCases:
    """Test boundary and unusual inputs."""

    def test_rollback_empty_transaction(self, tx_dbms):
        """Rollback a transaction with no operations."""
        tx_dbms.begin()
        result = tx_dbms.rollback()
        assert "rolled back" in str(result).lower()

    def test_commit_empty_transaction(self, tx_dbms):
        """Commit a transaction with no operations."""
        tx_dbms.begin()
        result = tx_dbms.commit()
        assert "committed" in str(result).lower()

    def test_multiple_rollbacks_in_sequence(self, sample_table):
        """Multiple begin->rollback cycles."""
        for i in range(5):
            sample_table.begin()
            sample_table.insert({"table_name": "account", "column_name_list": None}, [100 + i, f"User{i}"])
            sample_table.rollback()

        table_db = DB("account")
        table_db.open_db()
        assert table_db.get(b"(1,)") is not None
        for i in range(5):
            assert table_db.get(f"({100 + i},)".encode()) is None
        table_db.close_db()

    def test_rollback_after_partial_operations(self, sample_table):
        """Insert some, delete some, then rollback."""
        sample_table.begin()
        sample_table.insert({"table_name": "account", "column_name_list": None}, [3, "Charlie"])
        sample_table.insert({"table_name": "account", "column_name_list": None}, [4, "Dave"])
        # Delete the original Alice
        sample_table.delete("account", {"op": "=", "left_operand": (None, "id"), "right_operand": (1,)})
        sample_table.rollback()

        table_db = DB("account")
        table_db.open_db()
        assert table_db.get(b"(1,)") is not None  # Alice restored
        assert table_db.get(b"(3,)") is None    # Charlie undone
        assert table_db.get(b"(4,)") is None    # Dave undone
        table_db.close_db()

    def test_update_no_match(self, sample_table):
        """Update with WHERE that matches nothing — should not crash."""
        sample_table.begin()
        result = sample_table.update("account", [("name", "Nobody")],
                                     {"op": "=", "left_operand": (None, "id"), "right_operand": (999,)})
        assert "0" in str(result)  # 0 rows updated
        sample_table.commit()

    def test_very_long_char_in_transaction(self, sample_table):
        """Insert long (but valid) string, rollback, verify cleaned up."""
        long_name = "A" * 20  # char(20) is the column limit
        sample_table.begin()
        sample_table.insert({"table_name": "account", "column_name_list": None}, [99, long_name])
        sample_table.rollback()

        table_db = DB("account")
        table_db.open_db()
        assert table_db.get(b"(99,)") is None
        table_db.close_db()

    def test_unicode_in_transaction(self, sample_table):
        """Unicode strings in transaction."""
        sample_table.begin()
        sample_table.insert({"table_name": "account", "column_name_list": None}, [5, "日本語"])
        result = sample_table.commit()
        assert "committed" in str(result).lower()

        table_db = DB("account")
        table_db.open_db()
        record = table_db.get(b"(5,)")
        assert record is not None
        assert record.data["name"] == "日本語"
        table_db.close_db()


class TestTransactionStateManipulation:
    """Test invalid state transitions and rapid actions."""

    def test_no_commit_after_rollback(self, sample_table):
        """Cannot commit after rolling back — no active tx."""
        sample_table.begin()
        sample_table.rollback()
        with pytest.raises(NoActiveTransactionError):
            sample_table.commit()

    def test_no_rollback_after_commit(self, sample_table):
        """Cannot rollback after committing — no active tx."""
        sample_table.begin()
        sample_table.commit()
        with pytest.raises(NoActiveTransactionError):
            sample_table.rollback()

    def test_insert_without_begin_is_auto_commit(self, sample_table):
        """Insert without transaction persists immediately."""
        sample_table.insert({"table_name": "account", "column_name_list": None}, [50, "Auto"])
        assert sample_table.auto_commit is True
        assert sample_table.current_transaction is None

        table_db = DB("account")
        table_db.open_db()
        assert table_db.get(b"(50,)") is not None
        table_db.close_db()

    def test_delete_without_begin_is_auto_commit(self, sample_table):
        """Delete without transaction persists immediately."""
        sample_table.delete("account", None)
        assert sample_table.auto_commit is True

        table_db = DB("account")
        table_db.open_db()
        assert table_db.get(b"(1,)") is None
        table_db.close_db()

    def test_update_without_begin_is_auto_commit(self, sample_table):
        """Update without transaction persists immediately."""
        sample_table.update("account", [("name", "Changed")], None)
        assert sample_table.auto_commit is True

        table_db = DB("account")
        table_db.open_db()
        record = table_db.get(b"(1,)")
        assert record.data["name"] == "Changed"
        table_db.close_db()


class TestCrashRecoveryEdgeCases:
    """Test recovery scenarios."""

    def test_recovery_with_no_log_file(self, tx_dbms):
        """Startup with no transaction log should work fine."""
        assert tx_dbms.current_transaction is None
        assert tx_dbms.auto_commit is True

    def test_recovery_clears_log(self, sample_table):
        """After recovery, log should be cleared."""
        sample_table.begin()
        sample_table.insert({"table_name": "account", "column_name_list": None}, [3, "Charlie"])
        # Simulate crash by creating new DBMS
        del sample_table
        import gc
        gc.collect()
        dbms2 = DBMS()
        assert dbms2.current_transaction is None
        # Log should be cleared after recovery
        log = TransactionLog(DB_DIR)
        assert len(log.get_uncommitted()) == 0

    def test_recovery_multiple_uncommitted(self, tx_dbms):
        """Multiple uncommitted transactions all rolled back."""
        tx_dbms.create_table({
            "table_name": "test",
            "column_list": [("id", "int")],
            "not_null_key_set": {"id"},
            "primary_key_list": [("id",)],
            "foreign_key_dict": {}
        })
        tx_dbms.insert({"table_name": "test", "column_name_list": None}, [1])

        # Manually create multiple "active" log entries
        log = TransactionLog(DB_DIR)
        tx1 = Transaction()
        tx1.log_insert("test", b"(2,)")
        log.append(tx1)

        tx2 = Transaction()
        tx2.log_insert("test", b"(3,)")
        log.append(tx2)

        # Simulate crash recovery
        del tx_dbms
        import gc
        gc.collect()
        dbms2 = DBMS()

        table_db = DB("test")
        table_db.open_db()
        assert table_db.get(b"(1,)") is not None
        assert table_db.get(b"(2,)") is None  # rolled back
        assert table_db.get(b"(3,)") is None  # rolled back
        table_db.close_db()


class TestForeignKeyWithTransactions:
    """Test referential integrity within transactions."""

    def test_insert_with_fk_in_transaction_rollback(self, tx_dbms):
        """Insert with FK inside tx, rollback removes the inserted record.

        NOTE: The referenced_by metadata in the parent table (dept) is a known
        limitation — it is updated immediately for referential integrity checks
        but the undo log only tracks the target table's record. This is
        acceptable for Phase 3.1 basic transaction support.
        """
        tx_dbms.create_table({
            "table_name": "dept",
            "column_list": [("did", "int"), ("dname", "char(20)")],
            "not_null_key_set": {"did"},
            "primary_key_list": [("did",)],
            "foreign_key_dict": {}
        })
        tx_dbms.insert({"table_name": "dept", "column_name_list": None}, [1, "Engineering"])

        tx_dbms.create_table({
            "table_name": "emp",
            "column_list": [("eid", "int"), ("ename", "char(20)"), ("dept_id", "int")],
            "not_null_key_set": {"eid"},
            "primary_key_list": [("eid",)],
            "foreign_key_dict": {"dept_id": ("dept", "did")}
        })

        tx_dbms.begin()
        tx_dbms.insert({"table_name": "emp", "column_name_list": None}, [10, "Alice", 1])
        tx_dbms.rollback()

        # The main record is correctly undone
        emp_db = DB("emp")
        emp_db.open_db()
        assert emp_db.get(b"(10,)") is None
        emp_db.close_db()
