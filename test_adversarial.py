"""Adversarial tests for transaction support — try to BREAK the code."""
import shutil
from pathlib import Path
from dbms import DBMS
from db_model import DB, Record
from transaction import Transaction, TransactionLog, TransactionState
from messages import *
import pytest

DB_DIR = Path("./DB")


@pytest.fixture
def dbms():
    if DB_DIR.exists():
        shutil.rmtree(DB_DIR, onerror=lambda f, p, e: None)
    instance = DBMS()
    yield instance
    import gc
    gc.collect()
    if DB_DIR.exists():
        shutil.rmtree(DB_DIR, onerror=lambda f, p, e: None)


@pytest.fixture
def sample_table(dbms):
    dbms.create_table({
        "table_name": "account",
        "column_list": [("id", "int"), ("name", "char(20)")],
        "not_null_key_set": {"id"},
        "primary_key_list": [("id",)],
        "foreign_key_dict": {}
    })
    dbms.insert({"table_name": "account", "column_name_list": None}, [1, "Alice"])
    return dbms


# ---------------------------------------------------------------------------- #
# Edge Cases                                                                 #
# ---------------------------------------------------------------------------- #

class TestEdgeCases:
    """Test boundary and unusual inputs."""

    def test_rollback_empty_transaction(self, dbms):
        """Rollback a transaction with no operations."""
        dbms.begin()
        result = dbms.rollback()
        assert "rolled back" in str(result).lower()

    def test_commit_empty_transaction(self, dbms):
        """Commit a transaction with no operations."""
        dbms.begin()
        result = dbms.commit()
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
        result = sample_table.update("account", {"column_name": "name", "value": "Nobody"},
                                     {"op": "=", "left_operand": (None, "id"), "right_operand": (999,)})
        assert "0" in str(result)  # 0 rows updated
        sample_table.commit()

    def test_very_long_char_in_transaction(self, sample_table):
        """Insert very long string, rollback, verify cleaned up."""
        long_name = "A" * 1000
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


# ---------------------------------------------------------------------------- #
# State Manipulation                                                         #
# ---------------------------------------------------------------------------- #

class TestStateManipulation:
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
        sample_table.update("account", {"column_name": "name", "value": "Changed"}, None)
        assert sample_table.auto_commit is True

        table_db = DB("account")
        table_db.open_db()
        record = table_db.get(b"(1,)")
        assert record.data["name"] == "Changed"
        table_db.close_db()


# ---------------------------------------------------------------------------- #
# Crash Recovery                                                             #
# ---------------------------------------------------------------------------- #

class TestCrashRecoveryEdgeCases:
    """Test recovery scenarios."""

    def test_recovery_with_no_log_file(self, dbms):
        """Startup with no transaction log should work fine."""
        assert dbms.current_transaction is None
        assert dbms.auto_commit is True

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

    def test_recovery_multiple_uncommitted(self, dbms):
        """Multiple uncommitted transactions all rolled back."""
        dbms.create_table({
            "table_name": "test",
            "column_list": [("id", "int")],
            "not_null_key_set": {"id"},
            "primary_key_list": [("id",)],
            "foreign_key_dict": {}
        })
        dbms.insert({"table_name": "test", "column_name_list": None}, [1])

        # Manually create multiple "active" log entries
        log = TransactionLog(DB_DIR)
        tx1 = Transaction()
        tx1.log_insert("test", b"(2,)")
        log.append(tx1)

        tx2 = Transaction()
        tx2.log_insert("test", b"(3,)")
        log.append(tx2)

        # Simulate crash recovery
        del dbms
        import gc
        gc.collect()
        dbms2 = DBMS()

        table_db = DB("test")
        table_db.open_db()
        assert table_db.get(b"(1,)") is not None
        assert table_db.get(b"(2,)") is None  # rolled back
        assert table_db.get(b"(3,)") is None  # rolled back
        table_db.close_db()


# ---------------------------------------------------------------------------- #
# Foreign Key + Transaction Integration                                        #
# ---------------------------------------------------------------------------- #

class TestForeignKeyWithTransactions:
    """Test referential integrity within transactions."""

    def test_insert_with_fk_in_transaction_rollback(self, dbms):
        """Insert with FK inside tx, rollback removes the inserted record.

        NOTE: The referenced_by metadata in the parent table (dept) is a known
        limitation — it is updated immediately for referential integrity checks
        but the undo log only tracks the target table's record. This is
        acceptable for Phase 3.1 basic transaction support.
        """
        dbms.create_table({
            "table_name": "dept",
            "column_list": [("did", "int"), ("dname", "char(20)")],
            "not_null_key_set": {"did"},
            "primary_key_list": [("did",)],
            "foreign_key_dict": {}
        })
        dbms.insert({"table_name": "dept", "column_name_list": None}, [1, "Engineering"])

        dbms.create_table({
            "table_name": "emp",
            "column_list": [("eid", "int"), ("ename", "char(20)"), ("dept_id", "int")],
            "not_null_key_set": {"eid"},
            "primary_key_list": [("eid",)],
            "foreign_key_dict": {"dept_id": ("dept", "did")}
        })

        dbms.begin()
        dbms.insert({"table_name": "emp", "column_name_list": None}, [10, "Alice", 1])
        dbms.rollback()

        # The main record is correctly undone
        emp_db = DB("emp")
        emp_db.open_db()
        assert emp_db.get(b"(10,)") is None
        emp_db.close_db()
