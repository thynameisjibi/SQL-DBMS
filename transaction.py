"""Transaction support with undo logging and crash recovery."""

import json
from pathlib import Path
from typing import List, Optional, Set
from enum import Enum
from datetime import datetime

from db_model import DB, Record


class TransactionState(str, Enum):
    """Transaction lifecycle states."""
    ACTIVE = 'active'
    COMMITTED = 'committed'
    ROLLED_BACK = 'rolled_back'


class UndoLogEntry:
    """Represents a single undo operation."""

    def __init__(self, table_name: str, record_key: bytes,
                 old_data: Optional[bytes], operation: str):
        self.table_name = table_name
        self.record_key = record_key
        self.old_data = old_data  # serialized Record for UPDATE/DELETE, None for INSERT
        self.operation = operation  # 'INSERT', 'UPDATE', or 'DELETE'

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict."""
        return {
            'table_name': self.table_name,
            'record_key': self.record_key.decode('latin-1'),
            'old_data': self.old_data.decode('latin-1') if self.old_data else None,
            'operation': self.operation
        }

    @classmethod
    def from_dict(cls, d: dict) -> 'UndoLogEntry':
        """Deserialize from dict."""
        return cls(
            table_name=d['table_name'],
            record_key=d['record_key'].encode('latin-1'),
            old_data=d['old_data'].encode('latin-1') if d['old_data'] else None,
            operation=d['operation']
        )


class Transaction:
    """Active transaction with undo logging."""

    _counter = 0

    def __init__(self):
        Transaction._counter += 1
        self.tx_id = Transaction._counter
        self.undo_log: List[UndoLogEntry] = []
        self.state = TransactionState.ACTIVE
        self.modified_tables: Set[str] = set()
        self.start_time = datetime.now().isoformat()

    def log_insert(self, table_name: str, record_key: bytes):
        """Log INSERT for rollback (need to delete)."""
        self.undo_log.append(UndoLogEntry(table_name, record_key, None, 'INSERT'))
        self.modified_tables.add(table_name)

    def log_delete(self, table_name: str, record_key: bytes, record_data: bytes):
        """Log DELETE for rollback (need to restore)."""
        self.undo_log.append(UndoLogEntry(table_name, record_key, record_data, 'DELETE'))
        self.modified_tables.add(table_name)

    def log_update(self, table_name: str, record_key: bytes, old_data: bytes):
        """Log UPDATE for rollback (need to restore old value)."""
        self.undo_log.append(UndoLogEntry(table_name, record_key, old_data, 'UPDATE'))
        self.modified_tables.add(table_name)

    def rollback(self, db_dir: Path):
        """Undo all changes in reverse order (LIFO)."""
        for entry in reversed(self.undo_log):
            table_db = DB(entry.table_name)
            table_db.open_db()
            try:
                if entry.operation == 'INSERT':
                    # Delete the inserted record
                    table_db.delete(entry.record_key)
                elif entry.operation == 'DELETE':
                    # Restore the deleted record
                    record = Record.deserialize(entry.old_data)
                    table_db.put(entry.record_key, record)
                elif entry.operation == 'UPDATE':
                    # Restore the old record
                    record = Record.deserialize(entry.old_data)
                    table_db.put(entry.record_key, record)
            finally:
                table_db.close_db()

        self.state = TransactionState.ROLLED_BACK
        self.undo_log.clear()
        self.modified_tables.clear()

    def commit(self):
        """Finalize and clear undo log."""
        self.state = TransactionState.COMMITTED
        self.undo_log.clear()
        self.modified_tables.clear()


class TransactionLog:
    """Persist transaction logs for crash recovery."""

    def __init__(self, db_dir: Path = Path("./DB")):
        self.db_dir = db_dir
        self.db_dir.mkdir(exist_ok=True)
        self.log_file = self.db_dir / "transaction.log"

    def append(self, transaction: Transaction):
        """Append state to append-only log file."""
        entry = {
            'tx_id': transaction.tx_id,
            'state': transaction.state.value,
            'undo_log': [log.to_dict() for log in transaction.undo_log],
            'modified_tables': list(transaction.modified_tables),
            'start_time': transaction.start_time
        }
        with open(self.log_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')

    def get_uncommitted(self) -> List[Transaction]:
        """Get active transactions for recovery."""
        if not self.log_file.exists():
            return []

        # Track the latest entry per tx_id
        transactions = {}
        with open(self.log_file, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                tx_id = entry['tx_id']
                transactions[tx_id] = entry

        uncommitted = []
        for entry in transactions.values():
            if entry['state'] == TransactionState.ACTIVE.value:
                tx = Transaction()
                tx.tx_id = entry['tx_id']
                tx.state = TransactionState.ACTIVE
                tx.undo_log = [UndoLogEntry.from_dict(log) for log in entry['undo_log']]
                tx.modified_tables = set(entry['modified_tables'])
                tx.start_time = entry['start_time']
                uncommitted.append(tx)

        return uncommitted

    def clear(self):
        """Clear log after recovery."""
        if self.log_file.exists():
            self.log_file.unlink()
