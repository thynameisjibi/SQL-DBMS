# SQL DBMS Enhancement - Implementation Plan (Revised)

A comprehensive phased implementation plan for enhancing the Python-based SQL Database Management System with indexing, transactions, type/constraint validation, and a GUI surface.

**Revision Notes:** This plan has been revised to address architectural gaps identified during codebase review. Key changes include:
- Split indexing into Hash Index (Phase 2.1) and B-Tree Index (Phase 2.2 bonus)
- Added Phase 0 for foundational changes (exceptions, grammar updates)
- Clarified transaction scope and rollback mechanics
- Added explicit module dependency structure

---

## Project Overview

**Current State:** A Python-based SQL DBMS using `dbm` for storage and Lark for SQL parsing. Supports basic CRUD operations with referential integrity.

**Target State:** Full-featured DBMS with:
- ✅ Complete type & constraint checking
- ✅ UPDATE statement support (single + multiple assignments)
- ✅ Hash indexing with query planner (B-Tree as bonus)
- ✅ ACID transactions with rollback (data operations only)
- ✅ Web-based GUI with live results

---

## Phase 0: Foundation & Prerequisites

### 0.1 Exception Classes & Message Enhancements

**Goal:** Add all missing exception classes required by subsequent phases.

#### Files to Modify

| File | Changes |
|------|---------|
| `messages.py` | Add 10 new exception classes |

#### New Exception Classes

```python
# messages.py - Add after existing exceptions

# Phase 1.1 - Type checking enhancements
class InsertDateFormatException(Exception):
    """Raised when date format doesn't match YYYY-MM-DD."""
    def __init__(self):
        super().__init__("Insertion has failed: Invalid date format")

class InsertCharLengthExceeded(Exception):
    """Raised when string exceeds char(N) length."""
    def __init__(self, max_len):
        super().__init__(f"Insertion has failed: String exceeds char({max_len})")

# Phase 1.2 - UPDATE statement errors
class UpdateReferentialIntegrityError(Exception):
    """Raised when FK constraint is violated on UPDATE."""
    def __init__(self):
        super().__init__("Update has failed: Referential integrity violation")

class UpdateTypeMismatchError(Exception):
    """Raised when type doesn't match column on UPDATE."""
    def __init__(self):
        super().__init__("Update has failed: Types are not matched")

class UpdateResult(SuccessLog):
    def __init__(self, num_updated):
        self.num_updated = num_updated
        super().__init__(f"'{self.num_updated}' row(s) are updated")

# Phase 3.1 - Transaction errors
class ActiveTransactionError(Exception):
    """Raised when trying to begin while a transaction is active."""
    def __init__(self):
        super().__init__("Transaction error: A transaction is already active")

class NoActiveTransactionError(Exception):
    """Raised when trying to commit/rollback without active transaction."""
    def __init__(self):
        super().__init__("Transaction error: No active transaction")

class InvalidTransactionStateError(Exception):
    """Raised when transaction operation is invalid for current state."""
    def __init__(self):
        super().__init__("Transaction error: Invalid transaction state")
```

#### Acceptance Criteria
- [ ] All 10 new exception classes added to `messages.py`
- [ ] Exception hierarchy follows existing patterns (inherit from `Exception` or `SuccessLog`)
- [ ] Error messages are clear and actionable

---

### 0.2 Grammar Updates for Multi-Assignment UPDATE

**Goal:** Extend grammar to support multiple SET assignments in UPDATE statements.

#### Files to Modify

| File | Changes |
|------|---------|
| `grammar.lark` | Update `update_query` rule (line 152) |

#### Grammar Changes

```lark
// grammar.lark - Line 152
// BEFORE:
update_query : UPDATE table_name SET assignment [where_clause]

// AFTER:
update_query : UPDATE table_name SET assignment ("," assignment)* [where_clause]
assignment : column_name EQUAL value
```

#### SQLTransformer Updates

```python
# sql_transformer.py - Replace existing update_query method (line 249)
def update_query(self, items):
    self.statement = items[0].lower()
    self.table = {
        "table_name": items[2],
        "set_columns": items[4] if isinstance(items[4], list) else [items[4]],
    }
    self.where = items[5] if len(items) > 5 else None
    return items

def assignment(self, items):
    return (items[0], items[2])  # (column_name, value)
```

#### Acceptance Criteria
- [ ] Grammar accepts: `UPDATE account SET branch_name = 'Downtown', balance = 500 WHERE account_number = 9732;`
- [ ] Grammar accepts: `UPDATE account SET balance = 0;` (no WHERE clause)
- [ ] Transformer returns `set_columns` as list of tuples: `[('branch_name', 'Downtown'), ('balance', 500)]`

---

## Phase 1: Core Enhancements

### 1.1 Full Type & Constraint Checking

**Goal:** Ensure every INSERT validates types, NOT NULL, PRIMARY KEY uniqueness, and FOREIGN KEY constraints strictly.

#### Files to Modify

| File | Changes |
|------|---------|
| `utils.py` | Enhance `is_valid_type()` for edge cases |
| `dbms.py` | `insert()` method (lines 142-218): Add stricter validation |

#### Enhanced Validation Logic

```python
# utils.py - Replace is_valid_type function (line 58)
def is_valid_type(valid_type, value):
    """
    Validate value against column type specification.
    
    Args:
        valid_type: Type string from schema (e.g., "int", "char(15)", "date")
        value: Python value to validate
    
    Returns:
        bool: True if valid, False otherwise
    """
    if value is None:
        return True  # NULL check handled separately by NOT NULL constraint
    
    try:
        if valid_type == "int":
            # Reject booleans (bool is subclass of int in Python)
            return isinstance(value, int) and not isinstance(value, bool)
        
        elif valid_type.startswith("char"):
            max_len = eval_char_max_len(valid_type)
            return isinstance(value, str) and len(value) <= max_len
        
        elif valid_type == "date":
            # Strict YYYY-MM-DD format validation
            if not isinstance(value, str):
                return False
            match = re.match(DATE_PATTERN, value)
            if not match:
                return False
            # Additional: validate month/day ranges
            year, month, day = map(int, match.groups())
            if month < 1 or month > 12:
                return False
            if day < 1 or day > 31:
                return False
            return True
    
    except (ValueError, TypeError):
        return False
    
    return False
```

#### Enhanced INSERT Validation in DBMS

```python
# dbms.py - insert() method, add after line 165
# Enhanced type validation with specific error messages
for column_name, data_type, value in zip(table.columns.keys(), table.columns.values(), value_list):
    # Check NOT NULL constraint
    if value is None and column_name in table.not_null_keys:
        raise InsertColumnNonNullableError(column_name)
    
    # Check char length constraint
    if data_type.startswith("char") and value is not None:
        max_len = eval_char_max_len(data_type)
        if len(value) > max_len:
            raise InsertCharLengthExceeded(max_len)
    
    # Check date format
    if data_type == "date" and value is not None:
        if not re.match(DATE_PATTERN, value):
            raise InsertDateFormatException()
    
    # Check type match
    if not is_valid_type(data_type, value):
        raise InsertTypeMismatchError()
```

#### Test Cases

```sql
-- Should fail: bool into int
INSERT INTO account VALUES (true, 'Test');

-- Should fail: wrong date format
INSERT INTO transactions VALUES ('2023/12/25');

-- Should fail: string too long for char(15)
INSERT INTO account VALUES (1234, 'ThisBranchNameIsWayTooLong');

-- Should fail: NULL into NOT NULL column
INSERT INTO account VALUES (NULL, 'Test');

-- Should pass: valid date
INSERT INTO transactions VALUES ('2023-12-25');
```

#### Acceptance Criteria
- [ ] Boolean values rejected for INT columns
- [ ] Date format strictly enforced (YYYY-MM-DD)
- [ ] CHAR(N) length enforced at insert time
- [ ] NOT NULL constraint checked before type validation
- [ ] All test cases pass

---

### 1.2 UPDATE Statement Implementation

**Goal:** Support `UPDATE table_name SET column = value [WHERE condition]` with full constraint checking.

#### Files to Modify

| File | Changes |
|------|---------|
| `dbms.py` | Add new `update()` method |
| `run.py` | Add UPDATE statement handler |

#### DBMS Update Method

```python
# dbms.py - Add new method after delete() (line 269)
def update(self, table_name: str, set_columns: list, where_clause: dict):
    """
    UPDATE table_name SET column1=value1, column2=value2 WHERE condition
    
    Args:
        table_name: Target table name
        set_columns: List of (column_name, value) tuples
        where_clause: Parsed WHERE condition dict (or None for all rows)
    
    Returns:
        UpdateResult with count of affected rows
    
    Raises:
        NoSuchTable: Table doesn't exist
        NonExistingColumnDefError: SET column doesn't exist
        UpdateTypeMismatchError: Value type doesn't match column type
        UpdateReferentialIntegrityError: FK constraint violated
    """
    # Validate table exists
    self.meta_db.open_db()
    table_key = self.meta_db.create_key_from_value(table_name)
    table = self.meta_db.get(table_key)
    if not table:
        raise NoSuchTable()
    self.meta_db.close_db()
    
    # Validate SET columns exist and types match
    for col_name, value in set_columns:
        if col_name not in table.columns:
            raise NonExistingColumnDefError(col_name)
        if value is None and col_name in table.not_null_keys:
            raise InsertColumnNonNullableError(col_name)
        if not is_valid_type(table.columns[col_name], value):
            raise UpdateTypeMismatchError()
    
    # Open table database
    table_db = DB(table_name)
    table_db.open_db()
    cursor = table_db.create_cursor()
    
    success_cnt = 0
    key_value_pair = cursor.first()
    
    while key_value_pair:
        key, value = key_value_pair
        record = Record.deserialize(value)
        
        # Check WHERE condition
        satisfies = self._evaluate_condition(
            deepcopy(where_clause), [table], record.data
        ) if where_clause else True
        
        if satisfies == True:
            # Validate FK constraints for each update
            for col_name, new_value in set_columns:
                if table.foreign_keys and col_name in table.foreign_keys:
                    ref_table_name, ref_col_name = table.foreign_keys[col_name]
                    
                    # Check if new_value exists in referenced table
                    self.meta_db.open_db()
                    ref_key = self.meta_db.create_key_from_value(ref_table_name)
                    ref_table_schema = self.meta_db.get(ref_key)
                    self.meta_db.close_db()
                    
                    ref_db = DB(ref_table_name)
                    ref_db.open_db()
                    ref_record_key = ref_db.create_key_from_value((new_value,))
                    if not ref_db.exists(ref_record_key):
                        ref_db.close_db()
                        raise UpdateReferentialIntegrityError()
                    ref_db.close_db()
            
            # Apply updates
            for col_name, new_value in set_columns:
                record.data[col_name] = new_value
            
            # Update record in database
            table_db.put(key, record)
            success_cnt += 1
        
        key_value_pair = cursor.next()
    
    table_db.discard_cursor(cursor)
    table_db.close_db()
    
    return UpdateResult(success_cnt)
```

#### Run.py Handler

```python
# run.py - Add to statement handling (after line 47)
elif statement == "update":
    result = dbms.update(table["table_name"], table["set_columns"], where)
    print(PROMPT + str(result))
```

#### Exception Handler Update

```python
# run.py - Add to exception tuple (line 48-54)
except (..., UpdateReferentialIntegrityError, UpdateTypeMismatchError) as e:
```

#### Test Cases

```sql
-- Basic update
UPDATE account SET branch_name = 'Downtown' WHERE account_number = 9732;

-- Multiple column update
UPDATE account SET branch_name = 'Perryridge', balance = 500 WHERE account_number = 9732;

-- Update with no WHERE (all rows)
UPDATE account SET balance = 0;

-- Should fail: FK violation
UPDATE borrower SET loan_number = 'L-999' WHERE customer_name = 'Smith';

-- Should fail: type mismatch
UPDATE account SET balance = 'not_a_number' WHERE account_number = 9732;
```

#### Acceptance Criteria
- [ ] Single-column UPDATE works with WHERE clause
- [ ] Multi-column UPDATE works (comma-separated SET assignments)
- [ ] UPDATE without WHERE updates all rows
- [ ] FK constraint violations raise `UpdateReferentialIntegrityError`
- [ ] Type mismatches raise `UpdateTypeMismatchError`
- [ ] Returns correct count of updated rows

---

### 1.3 ALTER TABLE (Optional Enhancement)

**Goal:** Support `ALTER TABLE table_name ADD/DROP COLUMN column_name type`.

**Note:** This is marked as OPTIONAL. Implement only if time permits after core features.

#### Grammar Addition

```lark
// grammar.lark - Add after line 153
alter_table_query : ALTER TABLE table_name ADD column_definition
                  | ALTER TABLE table_name DROP COLUMN column_name
```

#### Acceptance Criteria
- [ ] ADD COLUMN works with type and NOT NULL constraint
- [ ] DROP COLUMN removes column from schema
- [ ] Existing records preserved with default NULL for new columns

---

## Phase 2: Indexing System

### 2.1 Hash Index Implementation (Core)

**Goal:** Build a hash-based index that makes single-column lookups fast (O(1) average case).

**Note:** Revised from "B-Tree" to "Hash Index" for accuracy. The original plan incorrectly labeled a dictionary-based index as B-Tree.

#### New Files

| File | Purpose |
|------|---------|
| `index.py` | HashIndex and IndexManager classes |

#### Index Module Design

```python
# index.py
import pickle
from pathlib import Path
from typing import Dict, Set, Any, Optional

class HashIndex:
    """
    Hash-based index for single-column lookups.
    Provides O(1) average-case search, insert, and delete operations.
    
    Note: This is NOT a B-Tree. For true O(log n) guaranteed performance
    with range queries, see Phase 2.2 (B-Tree Index - Bonus).
    """
    
    def __init__(self, column_name: str, ascending: bool = True):
        self.column_name = column_name
        self.ascending = ascending
        self.index: Dict[Any, Set[bytes]] = {}  # value -> set of record_keys
    
    def insert(self, value: Any, record_key: bytes):
        """Add a value->key mapping to the index. O(1) average."""
        if value not in self.index:
            self.index[value] = set()
        self.index[value].add(record_key)
    
    def delete(self, value: Any, record_key: bytes):
        """Remove a value->key mapping from the index. O(1) average."""
        if value in self.index:
            self.index[value].discard(record_key)
            if not self.index[value]:
                del self.index[value]
    
    def search(self, value: Any) -> Set[bytes]:
        """Return set of record_keys matching value. O(1) average."""
        return self.index.get(value, set())
    
    def range_search(self, low: Any, high: Any) -> Set[bytes]:
        """
        Return all record_keys where low <= value <= high.
        O(n) - hash indexes are NOT optimized for range queries.
        For better range performance, use B-Tree Index (Phase 2.2).
        """
        results = set()
        for value, keys in self.index.items():
            if low <= value <= high:
                results.update(keys)
        return results
    
    def get_all_keys(self) -> Set[bytes]:
        """Return all indexed record keys. O(n)."""
        all_keys = set()
        for keys in self.index.values():
            all_keys.update(keys)
        return all_keys
    
    def serialize(self) -> bytes:
        """Serialize index for persistence."""
        return pickle.dumps(self.__dict__)
    
    @classmethod
    def deserialize(cls, data: bytes) -> 'HashIndex':
        """Deserialize index from bytes."""
        obj = cls.__new__(cls)
        obj.__dict__.update(pickle.loads(data))
        return obj


class IndexManager:
    """
    Manages indexes for a single table.
    Persists indexes to disk alongside table data.
    """
    
    def __init__(self, table_name: str, db_dir: Path = None):
        self.table_name = table_name
        self.db_dir = db_dir or Path("./DB")
        self.db_dir.mkdir(exist_ok=True)
        self.indexes: Dict[str, HashIndex] = {}  # column_name -> HashIndex
        self.index_file = self.db_dir / f"{table_name}_indexes.idx"
        self.load_indexes()
    
    def create_index(self, column_name: str) -> bool:
        """Create a new index on a column. Returns False if already exists."""
        if column_name in self.indexes:
            return False
        self.indexes[column_name] = HashIndex(column_name)
        self.save_indexes()
        return True
    
    def drop_index(self, column_name: str) -> bool:
        """Drop an existing index. Returns False if doesn't exist."""
        if column_name not in self.indexes:
            return False
        del self.indexes[column_name]
        self.save_indexes()
        return True
    
    def get_index(self, column_name: str) -> Optional[HashIndex]:
        """Get index for a column, or None if not indexed."""
        return self.indexes.get(column_name)
    
    def update_index(self, operation: str, record_key: bytes, record_data: dict, 
                     old_data: Optional[dict] = None):
        """
        Maintain indexes on INSERT/UPDATE/DELETE.
        
        Args:
            operation: 'insert', 'update', or 'delete'
            record_key: The record's primary key
            record_data: The record's data dict
            old_data: Previous data (required for UPDATE operations)
        """
        for col_name, index in self.indexes.items():
            value = record_data.get(col_name)
            
            if operation == 'insert':
                index.insert(value, record_key)
            
            elif operation == 'delete':
                index.delete(value, record_key)
            
            elif operation == 'update':
                # For update, remove old value, add new value
                if old_data:
                    old_value = old_data.get(col_name)
                    if old_value is not None:
                        index.delete(old_value, record_key)
                index.insert(value, record_key)
    
    def save_indexes(self):
        """Persist indexes to disk."""
        with open(self.index_file, 'wb') as f:
            pickle.dump(self.indexes, f)
    
    def load_indexes(self):
        """Load indexes from disk."""
        if self.index_file.exists():
            with open(self.index_file, 'rb') as f:
                self.indexes = pickle.load(f)
```

#### Grammar Additions

```lark
// grammar.lark - Add after line 154
create_index_query : CREATE INDEX index_name ON table_name column_name
drop_index_query : DROP INDEX index_name ON table_name
index_name : IDENTIFIER
```

#### DBMS Integration

```python
# dbms.py - Add imports and modify __init__
from index import IndexManager

class DBMS:
    def __init__(self):
        self.db_dir = Path("./DB")
        self.db_dir.mkdir(exist_ok=True)
        self.meta_db = MetaDB()
        self.index_managers: Dict[str, IndexManager] = {}  # table_name -> IndexManager
    
    def _get_index_manager(self, table_name: str) -> IndexManager:
        """Get or create IndexManager for a table."""
        if table_name not in self.index_managers:
            self.index_managers[table_name] = IndexManager(table_name, self.db_dir)
        return self.index_managers[table_name]
    
    def create_index(self, table_name: str, column_name: str, index_name: str):
        """Create an index on a table column."""
        # Validate table and column exist
        self.meta_db.open_db()
        table_key = self.meta_db.create_key_from_value(table_name)
        table = self.meta_db.get(table_key)
        if not table:
            raise NoSuchTable()
        if column_name not in table.columns:
            raise NonExistingColumnDefError(column_name)
        self.meta_db.close_db()
        
        index_mgr = self._get_index_manager(table_name)
        if not index_mgr.create_index(column_name):
            raise DuplicateColumnDefError()  # Index already exists
        
        # Build index from existing data
        table_db = DB(table_name)
        table_db.open_db()
        cursor = table_db.create_cursor()
        key_value_pair = cursor.first()
        
        while key_value_pair:
            key, value = key_value_pair
            record = Record.deserialize(value)
            index_mgr.update_index('insert', key, record.data)
            key_value_pair = cursor.next()
        
        table_db.discard_cursor(cursor)
        table_db.close_db()
        
        return f"Index '{index_name}' created on {table_name}.{column_name}"
```

#### Modify INSERT/UPDATE/DELETE to Maintain Indexes

```python
# dbms.py - insert() method, after line 215
# Add index maintenance
if table_name in self.index_managers:
    index_mgr = self.index_managers[table_name]
    index_mgr.update_index('insert', record_key, data)
```

#### Acceptance Criteria
- [ ] CREATE INDEX command works
- [ ] DROP INDEX command works
- [ ] Indexes persist across DBMS restarts
- [ ] INSERT/UPDATE/DELETE maintain index consistency
- [ ] Index lookups are measurably faster than full table scans for large tables (>1000 rows)

---

### 2.2 Query Planner with Index Selection (Bonus)

**Goal:** A planner that picks index vs. scan based on selectivity estimates.

#### New Files

| File | Purpose |
|------|---------|
| `planner.py` | Query optimizer that chooses index vs. full table scan |

#### Query Planner Design

```python
# planner.py
from typing import Tuple, Optional, Dict, Any
from index import HashIndex, IndexManager

class QueryPlan:
    """Represents an execution plan for a query."""
    
    def __init__(self, plan_type: str, info: Optional[Dict] = None):
        self.plan_type = plan_type  # 'index' or 'scan'
        self.info = info or {}
    
    def __repr__(self):
        return f"QueryPlan({self.plan_type}, {self.info})"


class QueryPlanner:
    """
    Decides whether to use an index or full table scan.
    Uses simple cost-based optimization.
    """
    
    # Threshold: use index if it reduces scan to < 20% of table
    INDEX_SELECTIVITY_THRESHOLD = 0.2
    
    @classmethod
    def plan_select(
        cls,
        table_name: str,
        table_row_count: int,
        where_clause: Optional[Dict],
        index_manager: IndexManager
    ) -> QueryPlan:
        """
        Generate execution plan for a SELECT query.
        
        Returns:
            QueryPlan with 'index' or 'scan' type
        """
        if not where_clause or not index_manager.indexes:
            return QueryPlan('scan', {'reason': 'No WHERE clause or no indexes'})
        
        # Extract columns from WHERE clause
        where_columns = cls._extract_where_columns(where_clause)
        
        if not where_columns:
            return QueryPlan('scan', {'reason': 'No indexable columns in WHERE'})
        
        # Find matching indexes and estimate selectivity
        best_index = None
        best_selectivity = float('inf')
        
        for col in where_columns:
            index = index_manager.get_index(col)
            if index:
                selectivity = cls._estimate_selectivity(index, table_row_count)
                if selectivity < best_selectivity:
                    best_selectivity = selectivity
                    best_index = index
        
        # Decide: index or scan?
        if best_index and best_selectivity < cls.INDEX_SELECTIVITY_THRESHOLD:
            return QueryPlan('index', {
                'index': best_index,
                'column': best_index.column_name,
                'estimated_rows': int(table_row_count * best_selectivity)
            })
        else:
            return QueryPlan('scan', {
                'reason': f'Best index selectivity {best_selectivity:.2f} > threshold'
            })
    
    @classmethod
    def _extract_where_columns(cls, where_clause: Dict) -> list:
        """Recursively extract column references from WHERE clause."""
        columns = []
        
        if not isinstance(where_clause, dict):
            return columns
        
        if 'left_operand' in where_clause:
            left = where_clause['left_operand']
            if isinstance(left, tuple) and len(left) == 2:
                columns.append(left[1])  # column_name
        
        # Recursively extract from boolean factors/terms
        if 'boolean_factors' in where_clause:
            for factor in where_clause['boolean_factors']:
                columns.extend(cls._extract_where_columns(factor))
        
        if 'boolean_terms' in where_clause:
            for term in where_clause['boolean_terms']:
                columns.extend(cls._extract_where_columns(term))
        
        return columns
    
    @classmethod
    def _estimate_selectivity(cls, index: HashIndex, table_row_count: int) -> float:
        """
        Estimate selectivity of an index.
        Selectivity = fraction of rows returned (lower = more selective = better)
        """
        if table_row_count == 0:
            return 1.0
        
        unique_values = len(index.index)
        if unique_values == 0:
            return 1.0
        
        # Simple estimate: assume uniform distribution
        avg_rows_per_value = table_row_count / unique_values
        selectivity = avg_rows_per_value / table_row_count
        
        return min(selectivity, 1.0)
```

#### Acceptance Criteria
- [ ] Query planner chooses index when selectivity < 20%
- [ ] Query planner falls back to scan for low-selectivity queries
- [ ] EXPLAIN command shows chosen execution plan

---

### 2.3 B-Tree Index (Advanced Bonus)

**Goal:** Implement a true B-Tree index for guaranteed O(log n) performance and efficient range queries.

**Note:** This is an ADVANCED bonus feature. Complete Phase 2.1 first.

#### Acceptance Criteria
- [ ] B-Tree node splitting/merging implemented
- [ ] Range queries are O(log n + k) where k = result size
- [ ] B-Tree outperforms hash index on range queries

---

## Phase 3: Transactions

### 3.1 Basic Transaction Support

**Goal:** BEGIN, COMMIT, ROLLBACK for data manipulation operations (INSERT, UPDATE, DELETE).

**Scope Clarification:**
- ✅ INCLUDED: INSERT, UPDATE, DELETE operations
- ❌ EXCLUDED: Schema changes (CREATE TABLE, DROP TABLE, ALTER TABLE)
  - Rationale: Schema changes require MetaDB modifications that complicate rollback
  - Schema changes auto-commit immediately

#### New Files

| File | Purpose |
|------|---------|
| `transaction.py` | Transaction manager with undo logging |

#### Transaction Module Design

```python
# transaction.py
import pickle
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

class TransactionState:
    ACTIVE = 'active'
    COMMITTED = 'committed'
    ROLLED_BACK = 'rolled_back'


class UndoLogEntry:
    """Represents a single undo operation."""
    
    def __init__(
        self,
        table_name: str,
        record_key: bytes,
        old_data: Optional[bytes],
        operation: str  # 'INSERT', 'UPDATE', 'DELETE'
    ):
        self.table_name = table_name
        self.record_key = record_key
        self.old_data = old_data  # Serialized Record for UPDATE/DELETE
        self.operation = operation
    
    def to_dict(self) -> dict:
        return {
            'table_name': self.table_name,
            'record_key': self.record_key.hex(),
            'old_data': self.old_data.hex() if self.old_data else None,
            'operation': self.operation,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'UndoLogEntry':
        return cls(
            table_name=data['table_name'],
            record_key=bytes.fromhex(data['record_key']),
            old_data=bytes.fromhex(data['old_data']) if data['old_data'] else None,
            operation=data['operation'],
        )


class Transaction:
    """
    Represents an active transaction with undo logging.
    All changes are logged and can be rolled back.
    """
    
    _counter = 0  # Class-level counter for transaction IDs
    
    def __init__(self):
        Transaction._counter += 1
        self.tx_id = Transaction._counter
        self.undo_log: List[UndoLogEntry] = []
        self.state = TransactionState.ACTIVE
        self.modified_tables: set = set()
        self.start_time = datetime.now()
    
    def log_insert(self, table_name: str, record_key: bytes):
        """Log an INSERT for potential rollback (need to delete)."""
        entry = UndoLogEntry(
            table_name=table_name,
            record_key=record_key,
            old_data=None,  # Nothing to restore for INSERT
            operation='INSERT'
        )
        self.undo_log.append(entry)
        self.modified_tables.add(table_name)
    
    def log_delete(self, table_name: str, record_key: bytes, record_data: bytes):
        """Log a DELETE for potential rollback (need to restore)."""
        entry = UndoLogEntry(
            table_name=table_name,
            record_key=record_key,
            old_data=record_data,  # Full record to restore
            operation='DELETE'
        )
        self.undo_log.append(entry)
        self.modified_tables.add(table_name)
    
    def log_update(
        self,
        table_name: str,
        record_key: bytes,
        old_record_data: bytes
    ):
        """Log an UPDATE for potential rollback (need to restore old value)."""
        entry = UndoLogEntry(
            table_name=table_name,
            record_key=record_key,
            old_data=old_record_data,  # Old record state
            operation='UPDATE'
        )
        self.undo_log.append(entry)
        self.modified_tables.add(table_name)
    
    def rollback(self, db_dir: Path, index_managers: Optional[Dict] = None):
        """
        Undo all changes in reverse order.
        
        Args:
            db_dir: Path to database directory
            index_managers: Dict of table_name -> IndexManager (optional)
        """
        from db_model import DB, Record
        
        for entry in reversed(self.undo_log):
            table_db = DB(entry.table_name)
            table_db.open_db()
            
            if entry.operation == 'INSERT':
                # Delete the inserted record
                if table_db.exists(entry.record_key):
                    del table_db.DB[entry.record_key]
            
            elif entry.operation == 'DELETE':
                # Restore the deleted record
                table_db.DB[entry.record_key] = entry.old_data
            
            elif entry.operation == 'UPDATE':
                # Restore old value
                table_db.DB[entry.record_key] = entry.old_data
            
            table_db.close_db()
        
        self.state = TransactionState.ROLLED_BACK
    
    def commit(self):
        """Finalize transaction and clear undo log."""
        self.state = TransactionState.COMMITTED
        self.undo_log.clear()  # Clear undo log after commit
    
    def to_dict(self) -> dict:
        return {
            'tx_id': self.tx_id,
            'state': self.state,
            'undo_log': [entry.to_dict() for entry in self.undo_log],
            'modified_tables': list(self.modified_tables),
            'start_time': self.start_time.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Transaction':
        tx = cls.__new__(cls)
        tx.tx_id = data['tx_id']
        tx.state = data['state']
        tx.undo_log = [UndoLogEntry.from_dict(e) for e in data['undo_log']]
        tx.modified_tables = set(data['modified_tables'])
        tx.start_time = datetime.fromisoformat(data['start_time'])
        return tx


class TransactionLog:
    """
    Persist transaction logs to disk for crash recovery.
    Uses append-only log format.
    """
    
    def __init__(self, log_file: str = "DB/transaction.log"):
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(exist_ok=True, parents=True)
    
    def append(self, transaction: Transaction):
        """Append transaction state to log file."""
        with open(self.log_file, 'a') as f:
            log_entry = json.dumps(transaction.to_dict())
            f.write(log_entry + '\n')
    
    def get_uncommitted(self) -> List[Transaction]:
        """Get all uncommitted transactions for recovery."""
        uncommitted = []
        
        if not self.log_file.exists():
            return uncommitted
        
        # Read log and find latest state for each transaction
        tx_states: Dict[int, dict] = {}
        
        with open(self.log_file, 'r') as f:
            for line in f:
                data = json.loads(line.strip())
                tx_states[data['tx_id']] = data
        
        # Return only active transactions
        for data in tx_states.values():
            if data['state'] == TransactionState.ACTIVE:
                uncommitted.append(Transaction.from_dict(data))
        
        return uncommitted
    
    def clear(self):
        """Clear the transaction log (after recovery)."""
        if self.log_file.exists():
            self.log_file.unlink()
```

#### Modify DBMS for Transactions

```python
# dbms.py - Add imports and modify __init__
from transaction import Transaction, TransactionLog, TransactionState

class DBMS:
    def __init__(self):
        self.db_dir = Path("./DB")
        self.db_dir.mkdir(exist_ok=True)
        self.meta_db = MetaDB()
        self.index_managers: Dict[str, IndexManager] = {}
        
        # Transaction management
        self.current_transaction: Optional[Transaction] = None
        self.auto_commit = True
        self.transaction_log = TransactionLog()
        
        # Recover any uncommitted transactions from crash
        self._recover_uncommitted_transactions()
    
    def _recover_uncommitted_transactions(self):
        """Roll back any uncommitted transactions from previous crash."""
        uncommitted = self.transaction_log.get_uncommitted()
        
        for tx in uncommitted:
            print(f"Recovering uncommitted transaction {tx.tx_id}...")
            tx.rollback(self.db_dir, self.index_managers)
        
        self.transaction_log.clear()
    
    def begin(self) -> str:
        """Start a new transaction."""
        if self.current_transaction and self.current_transaction.state == TransactionState.ACTIVE:
            raise ActiveTransactionError()
        
        self.current_transaction = Transaction()
        self.auto_commit = False
        self.transaction_log.append(self.current_transaction)
        
        return "Transaction started"
    
    def commit(self) -> str:
        """Commit the current transaction."""
        if not self.current_transaction:
            raise NoActiveTransactionError()
        if self.current_transaction.state != TransactionState.ACTIVE:
            raise InvalidTransactionStateError()
        
        self.current_transaction.commit()
        self.transaction_log.append(self.current_transaction)
        
        self.current_transaction = None
        self.auto_commit = True
        
        return "Transaction committed"
    
    def rollback(self) -> str:
        """Rollback the current transaction."""
        if not self.current_transaction:
            raise NoActiveTransactionError()
        
        self.current_transaction.rollback(self.db_dir, self.index_managers)
        self.transaction_log.append(self.current_transaction)
        
        self.current_transaction = None
        self.auto_commit = True
        
        return "Transaction rolled back"
```

#### Modify INSERT/UPDATE/DELETE to Log for Transactions

```python
# dbms.py - insert() method, before line 215
# Log for transaction rollback
if self.current_transaction:
    self.current_transaction.log_insert(table_name, record_key)
    self.transaction_log.append(self.current_transaction)
```

#### Grammar Additions

```lark
// grammar.lark - Add after line 155
begin_query : BEGIN
commit_query : COMMIT
rollback_query : ROLLBACK
```

#### SQLTransformer Handlers

```python
# sql_transformer.py - Add after line 251
def begin_query(self, items):
    self.statement = "begin"
    return items

def commit_query(self, items):
    self.statement = "commit"
    return items

def rollback_query(self, items):
    self.statement = "rollback"
    return items
```

#### Run.py Handler

```python
# run.py - Add to statement handling
elif statement == "begin":
    result = dbms.begin()
    print(PROMPT + str(result))
elif statement == "commit":
    result = dbms.commit()
    print(PROMPT + str(result))
elif statement == "rollback":
    result = dbms.rollback()
    print(PROMPT + str(result))
```

#### Test Cases

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

-- Nested transaction attempt (should fail)
BEGIN;
BEGIN;  -- Error: A transaction is already active

-- Commit without begin (should fail)
COMMIT;  -- Error: No active transaction
```

#### Acceptance Criteria
- [ ] BEGIN starts a new transaction
- [ ] COMMIT finalizes all changes
- [ ] ROLLBACK undoes all changes in reverse order
- [ ] Nested BEGIN raises ActiveTransactionError
- [ ] COMMIT/ROLLBACK without BEGIN raises NoActiveTransactionError
- [ ] Uncommitted transactions are recovered after crash

---

### 3.2 Index Rollback Integration (Bonus)

**Goal:** Rollback that also undoes index changes.

#### Acceptance Criteria
- [ ] Index entries are removed on INSERT rollback
- [ ] Index entries are restored on DELETE rollback
- [ ] Index entries are restored to old values on UPDATE rollback

---

## Phase 4: GUI Surface

### 4.1 Web-Based Interface

**Goal:** A front end to talk to your engine: run queries, see results, read errors.

#### New Files

| File | Purpose |
|------|---------|
| `gui/app.py` | Flask web application |
| `gui/templates/index.html` | Single-page interface |
| `gui/static/style.css` | Styling |
| `gui/static/app.js` | Client-side logic |
| `gui/requirements.txt` | Additional dependencies |

#### Acceptance Criteria
- [ ] Web UI executes all SQL commands
- [ ] Results displayed in tabular format
- [ ] Errors displayed with helpful messages
- [ ] Schema browser shows tables and columns
- [ ] Transaction controls (BEGIN/COMMIT/ROLLBACK) work

---

## Implementation Timeline

| Phase | Duration | Key Deliverables |
|-------|----------|------------------|
| **Phase 0** | Day 1-2 | Exception classes, grammar updates |
| **Phase 1** | Week 1-2 | Type checking, UPDATE statement |
| **Phase 2** | Week 3-4 | Hash indexing, query planner |
| **Phase 3** | Week 5-6 | Transactions, rollback, crash recovery |
| **Phase 4** | Week 7-8 | Web GUI, live results, schema browser |

---

## Module Dependencies

```
dbms.py
├── db_model.py (Table, Record, DB, MetaDB)
├── utils.py (is_valid_type, comparison operators)
├── messages.py (all exceptions)
├── index.py (IndexManager, HashIndex) - Phase 2.1
├── transaction.py (Transaction, TransactionLog) - Phase 3.1
└── planner.py (QueryPlanner) - Phase 2.2

run.py
├── dbms.py
├── sql_transformer.py
└── grammar.lark (via Lark parser)

gui/app.py
├── dbms.py
└── Flask framework
```

**No Circular Dependencies:** All dependencies flow downward. `dbms.py` imports `index.py` and `transaction.py`, but those modules do NOT import `dbms.py`.

---

## Testing Strategy

### Test Directory Structure

```
test/
├── test_basic_ops.py      # CREATE, INSERT, SELECT, UPDATE, DELETE
├── test_constraints.py    # Type checking, NOT NULL, PK/FK validation
├── test_indexing.py       # Index creation, lookup speed, maintenance
├── test_transactions.py   # BEGIN/COMMIT/ROLLBACK, crash recovery
├── test_gui.py            # API endpoint testing
└── fixtures/
    └── sample_data.sql    # Test data
```

---

## Success Criteria

### Phase 0
- [ ] All 10 new exception classes added
- [ ] Grammar accepts multi-assignment UPDATE
- [ ] Transformer correctly parses multi-assignment UPDATE

### Phase 1
- [ ] All type validations pass test suite
- [ ] UPDATE statement works with WHERE clause
- [ ] Multi-column UPDATE works
- [ ] Constraint violations raise appropriate errors

### Phase 2
- [ ] Hash index lookups are O(1) average case
- [ ] Query planner chooses index when beneficial
- [ ] Indexes stay consistent after INSERT/UPDATE/DELETE
- [ ] (Bonus) B-Tree index implemented with O(log n) guarantees

### Phase 3
- [ ] BEGIN/COMMIT/ROLLBACK work correctly
- [ ] Rollback restores data to pre-transaction state
- [ ] Uncommitted transactions recover after crash
- [ ] (Bonus) Index rollback integrated

### Phase 4
- [ ] Web GUI executes all SQL commands
- [ ] Schema browser shows tables and columns
- [ ] Errors display helpful messages with suggestions

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| `dbm` locking on concurrent access | High | Use file locks (`fcntl` on Unix, `msvcrt` on Windows) |
| Index maintenance slows writes | Medium | Batch index updates, lazy index building |
| Transaction logs grow large | Medium | Implement log rotation, periodic checkpointing |
| Index rollback complexity | High | Phase 3.2 marked as bonus; can defer |
| Web GUI adds complexity | Low | Keep optional (`python -m gui.app`), CLI remains primary |

---

## Appendix: File Modification Summary

| File | Phase | Changes |
|------|-------|---------|
| `messages.py` | 0.1 | Add 10 new exception classes |
| `grammar.lark` | 0.2, 2.1, 3.1 | UPDATE, INDEX, TRANSACTION rules |
| `sql_transformer.py` | 0.2, 2.1, 3.1 | New query handlers |
| `utils.py` | 1.1 | Enhanced type validation |
| `dbms.py` | 1.1, 1.2, 2.1, 3.1 | All core logic updates |
| `run.py` | 1.2, 3.1 | Transaction/UPDATE command handling |
| `index.py` | 2.1 | **NEW** - Hash index |
| `planner.py` | 2.2 | **NEW** - Query optimizer |
| `transaction.py` | 3.1 | **NEW** - Transaction manager |
| `gui/*` | 4.1 | **NEW** - Web interface |

---

*Document Version: 2.0 (Revised)*  
*Last Updated: 2024*  
*Project: SQL-DBMS Enhancement*  
*Revision Notes: Split indexing phases, clarified transaction scope, added module dependency map, fixed B-Tree vs Hash Index terminology*
