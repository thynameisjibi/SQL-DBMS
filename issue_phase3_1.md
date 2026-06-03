# Phase 3.1: Basic Transaction Support (BEGIN/COMMIT/ROLLBACK)

## Overview
Implement ACID transaction support for data manipulation operations (INSERT, UPDATE, DELETE) with undo logging and crash recovery.

**Scope Clarification:**
- ✅ **INCLUDED:** INSERT, UPDATE, DELETE operations
- ❌ **EXCLUDED:** Schema changes (CREATE TABLE, DROP TABLE, ALTER TABLE)
  - Rationale: Schema changes require MetaDB modifications that complicate rollback
  - Schema changes auto-commit immediately

## Current State
No transaction support. All operations are auto-committed immediately.

## Tasks

### 1. Create transaction.py Module
New file with three main classes:

#### TransactionState Enum
```python
class TransactionState:
    ACTIVE = 'active'
    COMMITTED = 'committed'
    ROLLED_BACK = 'rolled_back'
```

#### UndoLogEntry Class
```python
class UndoLogEntry:
    """Represents a single undo operation."""
    
    def __init__(self, table_name: str, record_key: bytes, 
                 old_data: Optional[bytes], operation: str):
        # operation: 'INSERT', 'UPDATE', or 'DELETE'
        # old_data: serialized Record for UPDATE/DELETE, None for INSERT
```

#### Transaction Class
```python
class Transaction:
    """Active transaction with undo logging."""
    
    def __init__(self):
        self.tx_id = unique_id
        self.undo_log: List[UndoLogEntry] = []
        self.state = TransactionState.ACTIVE
        self.modified_tables: set = set()
    
    def log_insert(self, table_name: str, record_key: bytes):
        """Log INSERT for rollback (need to delete)."""
    
    def log_delete(self, table_name: str, record_key: bytes, record_data: bytes):
        """Log DELETE for rollback (need to restore)."""
    
    def log_update(self, table_name: str, record_key: bytes, old_data: bytes):
        """Log UPDATE for rollback (need to restore old value)."""
    
    def rollback(self, db_dir: Path, index_managers: dict = None):
        """Undo all changes in reverse order."""
    
    def commit(self):
        """Finalize and clear undo log."""
```

#### TransactionLog Class
```python
class TransactionLog:
    """Persist transaction logs for crash recovery."""
    
    def append(self, transaction: Transaction):
        """Append state to append-only log file."""
    
    def get_uncommitted(self) -> List[Transaction]:
        """Get active transactions for recovery."""
    
    def clear(self):
        """Clear log after recovery."""
```

### 2. Modify DBMS for Transactions

#### Add to __init__()
```python
self.current_transaction: Optional[Transaction] = None
self.auto_commit = True
self.transaction_log = TransactionLog()
self._recover_uncommitted_transactions()
```

#### Implement Transaction Commands
```python
def begin(self) -> str:
    """Start new transaction."""
    if self.current_transaction and self.current_transaction.state == TransactionState.ACTIVE:
        raise ActiveTransactionError()
    
    self.current_transaction = Transaction()
    self.auto_commit = False
    self.transaction_log.append(self.current_transaction)
    return "Transaction started"

def commit(self) -> str:
    """Commit current transaction."""
    if not self.current_transaction:
        raise NoActiveTransactionError()
    
    self.current_transaction.commit()
    self.transaction_log.append(self.current_transaction)
    self.current_transaction = None
    self.auto_commit = True
    return "Transaction committed"

def rollback(self) -> str:
    """Rollback current transaction."""
    if not self.current_transaction:
        raise NoActiveTransactionError()
    
    self.current_transaction.rollback(self.db_dir, self.index_managers)
    self.transaction_log.append(self.current_transaction)
    self.current_transaction = None
    self.auto_commit = True
    return "Transaction rolled back"
```

### 3. Modify INSERT/UPDATE/DELETE to Log Operations

#### INSERT (dbms.py line ~215)
```python
# Before table_db.put(record_key, record)
if self.current_transaction:
    self.current_transaction.log_insert(table_name, record_key)
    self.transaction_log.append(self.current_transaction)
```

#### DELETE (dbms.py line ~263)
```python
# Before table_db.delete_by_cursor(outer_cursor)
if self.current_transaction:
    self.current_transaction.log_delete(table_name, key, value)
    self.transaction_log.append(self.current_transaction)
```

#### UPDATE (dbms.py - new method)
```python
# Before applying updates
old_data = deepcopy(record.data)

# After validation, before update
if self.current_transaction:
    self.current_transaction.log_update(table_name, key, old_data.serialize())
    self.transaction_log.append(self.current_transaction)
```

### 4. Add Grammar Rules
```lark
begin_query : BEGIN
commit_query : COMMIT
rollback_query : ROLLBACK
```

### 5. Add to run.py
Handle BEGIN/COMMIT/ROLLBACK commands and add transaction exceptions to error handler.

## Acceptance Criteria
- [ ] BEGIN starts a new transaction
- [ ] COMMIT finalizes all changes
- [ ] ROLLBACK undoes all changes in reverse order
- [ ] Nested BEGIN raises `ActiveTransactionError`
- [ ] COMMIT/ROLLBACK without BEGIN raises `NoActiveTransactionError`
- [ ] Uncommitted transactions are recovered after crash
- [ ] Schema changes (CREATE/DROP TABLE) auto-commit immediately

## Test Cases
```sql
-- Basic transaction
BEGIN;
INSERT INTO account VALUES (1234, 'TestBranch');
INSERT INTO account VALUES (5678, 'TestBranch2');
COMMIT;

-- Rollback transaction
BEGIN;
INSERT INTO account VALUES (9999, 'RollbackTest');
DELETE FROM account WHERE account_number = 1234;
ROLLBACK;
-- Changes should be undone

-- Nested transaction (should FAIL)
BEGIN;
BEGIN;  -- Error: A transaction is already active

-- Commit without begin (should FAIL)
COMMIT;  -- Error: No active transaction

-- Schema change auto-commits
BEGIN;
CREATE TABLE test (id int);  -- This commits immediately
ROLLBACK;
-- 'test' table should still exist
```

## Crash Recovery Test
```python
# Simulate crash after BEGIN but before COMMIT
dbms.begin()
dbms.insert(...)
# Kill process (simulate crash)

# On restart:
dbms = DBMS()  # Should automatically rollback uncommitted transaction
# Inserted data should be gone
```

## Files to Create/Modify
- **NEW:** `transaction.py`
- **MODIFY:** `grammar.lark` (add transaction rules)
- **MODIFY:** `sql_transformer.py` (add handlers)
- **MODIFY:** `dbms.py` (add transaction management)
- **MODIFY:** `run.py` (add command handlers)
- **MODIFY:** `messages.py` - Already has exceptions from Phase 0

## Dependencies
- **Blocks:** Phase 3.2 (Index Rollback)
- **Blocked by:** Phase 1 (stable INSERT/UPDATE/DELETE)

## Implementation Notes

### Undo Log Format
The undo log is append-only and stored in `DB/transaction.log`:
```json
{"tx_id": 1, "state": "active", "undo_log": [...], "modified_tables": ["account"], "start_time": "..."}
{"tx_id": 1, "state": "committed", ...}
```

### Rollback Order
Changes are undone in **reverse order** (LIFO):
1. Last operation is undone first
2. Ensures referential integrity during rollback
3. Example: If INSERT then DELETE, rollback does: restore DELETE then remove INSERT

### Index Rollback (Phase 3.2 Bonus)
Basic transaction rollback doesn't handle indexes. Phase 3.2 adds:
- Remove index entries on INSERT rollback
- Restore index entries on DELETE rollback
- Restore old index values on UPDATE rollback

### Auto-Commit Mode
By default, `auto_commit = True`. Each statement is its own transaction.
- BEGIN disables auto-commit
- COMMIT/ROLLBACK re-enables auto-commit

## References
- IMPLEMENTATION_PLAN.md Phase 3.1
- Phase 3.2: Index Rollback Integration (bonus)
