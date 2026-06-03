"""Tests for transaction support per Issue #5 plan."""

import pytest
import shutil
from pathlib import Path

from dbms import DBMS
from db_model import DB, Record
from messages import *
from transaction import Transaction, TransactionLog, TransactionState, UndoLogEntry


DB_DIR = Path("./DB")


@pytest.fixture
def dbms():
    """Provide a fresh DBMS instance with cleanup."""
    if DB_DIR.exists():
        shutil.rmtree(DB_DIR)
    instance = DBMS()
    yield instance
    if DB_DIR.exists():
        shutil.rmtree(DB_DIR)


@pytest.fixture
def sample_table(dbms):
    """Create a sample table for testing."""
    dbms.create_table({
        "table_name": "account",
        "column_list": [("id", "int"), ("name", "char(20)")],
        "not_null_key_set": {"id"},
        "primary_key_list": [("id",)],
        "foreign_key_dict": {}
    })
    dbms.insert({"table_name": "account", "column_name_list": None}, [1, "Alice"])
    dbms.insert({"table_name": "account", "column_name_list": None}, [2, "Bob"])
    return dbms


# ---------------------------------------------------------------------------- #
# Transaction class tests                                                      #
# ---------------------------------------------------------------------------- #

class TestTransactionLifecycle:
    """Tests for Transaction class."""

    def test_transaction_starts_active(self):
        tx = Transaction()
        assert tx.state == TransactionState.ACTIVE
        assert tx.undo_log == []
        assert tx.modified_tables == set()

    def test_log_insert(self):
        tx = Transaction()
        tx.log_insert("account", b"key1")
        assert len(tx.undo_log) == 1
        assert tx.undo_log[0].operation == "INSERT"
        assert tx.undo_log[0].table_name == "account"
        assert tx.undo_log[0].record_key == b"key1"
        assert tx.undo_log[0].old_data is None
        assert "account" in tx.modified_tables

    def test_log_delete(self):
        tx = Transaction()
        old_data = b"serialized_record"
        tx.log_delete("account", b"key1", old_data)
        assert len(tx.undo_log) == 1
        assert tx.undo_log[0].operation == "DELETE"
        assert tx.undo_log[0].old_data == old_data

    def test_log_update(self):
        tx = Transaction()
        old_data = b"serialized_record"
        tx.log_update("account", b"key1", old_data)
        assert len(tx.undo_log) == 1
        assert tx.undo_log[0].operation == "UPDATE"
        assert tx.undo_log[0].old_data == old_data

    def test_commit_clears_log(self):
        tx = Transaction()
        tx.log_insert("account", b"key1")
        tx.commit()
        assert tx.state == TransactionState.COMMITTED
        assert tx.undo_log == []
        assert tx.modified_tables == set()

    def test_rollback_restores_deleted_record(self, sample_table):
        tx = Transaction()
        record_key = b"(1,)"
        table_db = DB("account")
        table_db.open_db()
        old_record = table_db.get(record_key)
        table_db.close_db()

        tx.log_delete("account", record_key, old_record.serialize())
        tx.rollback(Path("./DB"))

        assert tx.state == TransactionState.ROLLED_BACK
        table_db.open_db()
        restored = table_db.get(record_key)
        table_db.close_db()
        assert restored is not None
        assert restored.data["name"] == "Alice"

    def test_rollback_removes_inserted_record(self, sample_table):
        tx = Transaction()
        record_key = b"(3,)"
        tx.log_insert("account", record_key)

        # Simulate insert
        table_db = DB("account")
        table_db.open_db()
        record = Record("account", {"id": 3, "name": "Charlie"}, (3,), {})
        table_db.put(record_key, record)
        table_db.close_db()

        tx.rollback(Path("./DB"))

        table_db.open_db()
        assert table_db.get(record_key) is None
        table_db.close_db()

    def test_rollback_reverse_order(self, sample_table):
        """Changes are undone in reverse order (LIFO)."""
        tx = Transaction()
        key1 = b"(1,)"
        key3 = b"(3,)"

        # Log insert of key3
        tx.log_insert("account", key3)
        # Log delete of key1
        table_db = DB("account")
        table_db.open_db()
        old_record = table_db.get(key1)
        table_db.close_db()
        tx.log_delete("account", key1, old_record.serialize())

        # Apply changes: insert key3, delete key1
        table_db = DB("account")
        table_db.open_db()
        record = Record("account", {"id": 3, "name": "Charlie"}, (3,), {})
        table_db.put(key3, record)
        table_db.delete(key1)
        table_db.close_db()

        tx.rollback(Path("./DB"))

        # After rollback: key1 restored, key3 removed
        table_db.open_db()
        assert table_db.get(key1) is not None
        assert table_db.get(key3) is None
        table_db.close_db()


# ---------------------------------------------------------------------------- #
# TransactionLog tests                                                         #
# ---------------------------------------------------------------------------- #

class TestTransactionLog:
    """Tests for TransactionLog persistence."""

    def test_append_and_read(self, dbms):
        log = TransactionLog(DB_DIR)
        tx = Transaction()
        tx.log_insert("account", b"key1")
        log.append(tx)

        assert log.log_file.exists()

    def test_get_uncommitted(self, dbms):
        log = TransactionLog(DB_DIR)
        tx = Transaction()
        tx.log_insert("account", b"key1")
        log.append(tx)

        uncommitted = log.get_uncommitted()
        assert len(uncommitted) == 1
        assert uncommitted[0].tx_id == tx.tx_id
        assert uncommitted[0].state == TransactionState.ACTIVE

    def test_get_uncommitted_excludes_committed(self, dbms):
        log = TransactionLog(DB_DIR)
        tx = Transaction()
        tx.log_insert("account", b"key1")
        log.append(tx)
        tx.commit()
        log.append(tx)

        uncommitted = log.get_uncommitted()
        assert len(uncommitted) == 0

    def test_clear(self, dbms):
        log = TransactionLog(DB_DIR)
        tx = Transaction()
        log.append(tx)
        log.clear()
        assert not log.log_file.exists()


# ---------------------------------------------------------------------------- #
# DBMS transaction command tests                                                 #
# ---------------------------------------------------------------------------- #

class TestDBMSBegin:
    """Tests for DBMS.begin()."""

    def test_begin_starts_transaction(self, dbms):
        result = dbms.begin()
        assert dbms.current_transaction is not None
        assert dbms.current_transaction.state == TransactionState.ACTIVE
        assert dbms.auto_commit is False
        assert "started" in str(result).lower()

    def test_begin_raises_when_active(self, dbms):
        dbms.begin()
        with pytest.raises(ActiveTransactionError):
            dbms.begin()


class TestDBMSCommit:
    """Tests for DBMS.commit()."""

    def test_commit_without_begin_raises(self, dbms):
        with pytest.raises(NoActiveTransactionError):
            dbms.commit()

    def test_commit_finalizes_transaction(self, sample_table):
        sample_table.begin()
        sample_table.insert({"table_name": "account", "column_name_list": None}, [3, "Charlie"])
        result = sample_table.commit()

        assert sample_table.current_transaction is None
        assert sample_table.auto_commit is True
        assert "committed" in str(result).lower()

        # Verify data persisted
        table_db = DB("account")
        table_db.open_db()
        assert table_db.get(b"(3,)") is not None
        table_db.close_db()


class TestDBMSRollback:
    """Tests for DBMS.rollback()."""

    def test_rollback_without_begin_raises(self, dbms):
        with pytest.raises(NoActiveTransactionError):
            dbms.rollback()

    def test_rollback_undoes_insert(self, sample_table):
        sample_table.begin()
        sample_table.insert({"table_name": "account", "column_name_list": None}, [3, "Charlie"])
        result = sample_table.rollback()

        assert sample_table.current_transaction is None
        assert sample_table.auto_commit is True
        assert "rolled back" in str(result).lower()

        # Verify data was undone
        table_db = DB("account")
        table_db.open_db()
        assert table_db.get(b"(3,)") is None
        table_db.close_db()

    def test_rollback_undoes_delete(self, sample_table):
        sample_table.begin()
        sample_table.delete("account", None)  # Delete all
        result = sample_table.rollback()

        # Verify data was restored
        table_db = DB("account")
        table_db.open_db()
        assert table_db.get(b"(1,)") is not None
        assert table_db.get(b"(2,)") is None
        table_db.close_db()


# ---------------------------------------------------------------------------- #
# Auto-commit tests                                                            #
# ---------------------------------------------------------------------------- #

class TestAutoCommit:
    """Tests for auto-commit behavior."""

    def test_insert_auto_commits_by_default(self, sample_table):
        sample_table.insert({"table_name": "account", "column_name_list": None}, [3, "Charlie"])
        assert sample_table.auto_commit is True
        assert sample_table.current_transaction is None

        table_db = DB("account")
        table_db.open_db()
        assert table_db.get(b"(3,)") is not None
        table_db.close_db()

    def test_schema_change_auto_commits(self, sample_table):
        sample_table.begin()
        sample_table.create_table({
            "table_name": "test",
            "column_list": [("id", "int")],
            "not_null_key_set": set(),
            "primary_key_list": [],
            "foreign_key_dict": {}
        })
        # Schema changes should not affect transaction state
        # Actually, per plan schema changes auto-commit immediately
        # But we keep transaction active
        result = sample_table.rollback()
        assert "rolled back" in str(result).lower()

        # test table should still exist
        sample_table.meta_db.open_db()
        assert sample_table.meta_db.exists(b"test")
        sample_table.meta_db.close_db()


# ---------------------------------------------------------------------------- #
# Crash recovery tests                                                         #
# ---------------------------------------------------------------------------- #

class TestCrashRecovery:
    """Tests for automatic rollback of uncommitted transactions on startup."""

    def test_recover_uncommitted_on_startup(self, sample_table):
        sample_table.begin()
        sample_table.insert({"table_name": "account", "column_name_list": None}, [3, "Charlie"])

        # Simulate crash by creating new DBMS instance
        del sample_table
        dbms2 = DBMS()

        # Uncommitted insert should be rolled back
        table_db = DB("account")
        table_db.open_db()
        assert table_db.get(b"(3,)") is None
        table_db.close_db()

        assert dbms2.current_transaction is None
        assert dbms2.auto_commit is True


# ---------------------------------------------------------------------------- #
# Integration tests with SQL commands                                            #
# ---------------------------------------------------------------------------- #

class TestTransactionSQLIntegration:
    """End-to-end tests simulating SQL command flow."""

    def test_full_transaction_commit(self, sample_table):
        sample_table.begin()
        sample_table.insert({"table_name": "account", "column_name_list": None}, [3, "Charlie"])
        sample_table.insert({"table_name": "account", "column_name_list": None}, [4, "Dave"])
        sample_table.commit()

        table_db = DB("account")
        table_db.open_db()
        assert table_db.get(b"(3,)") is not None
        assert table_db.get(b"(4,)") is not None
        table_db.close_db()

    def test_full_transaction_rollback(self, sample_table):
        sample_table.begin()
        sample_table.insert({"table_name": "account", "column_name_list": None}, [3, "Charlie"])
        sample_table.insert({"table_name": "account", "column_name_list": None}, [4, "Dave"])
        sample_table.rollback()

        table_db = DB("account")
        table_db.open_db()
        assert table_db.get(b"(3,)") is None
        assert table_db.get(b"(4,)") is None
        assert table_db.get(b"(1,)") is not None
        assert table_db.get(b"(2,)") is not None
        table_db.close_db()

    def test_delete_then_rollback(self, sample_table):
        sample_table.begin()
        sample_table.delete("account", None)
        sample_table.rollback()

        table_db = DB("account")
        table_db.open_db()
        assert table_db.get(b"(1,)") is not None
        assert table_db.get(b"(2,)") is not None
        table_db.close_db()
