# Phase 2.1: Hash Index Implementation

## Overview
Implement a hash-based indexing system for O(1) average-case single-column lookups. This replaces the original plan's "B-Tree" terminology with accurate "Hash Index" since the proposed implementation uses a dictionary.

**Note:** A true B-Tree implementation is deferred to Phase 2.3 (Advanced Bonus) as it requires significantly more complex node management logic.

## Current State
No indexing exists. All queries use full table scans (O(n)).

## Tasks

### 1. Create index.py Module
New file with two main classes:

#### HashIndex Class
```python
class HashIndex:
    """Hash-based index for O(1) average-case lookups."""
    
    def __init__(self, column_name: str, ascending: bool = True):
        self.column_name = column_name
        self.ascending = ascending
        self.index: Dict[Any, Set[bytes]] = {}  # value -> set of record_keys
    
    def insert(self, value: Any, record_key: bytes):
        """Add value->key mapping. O(1) average."""
    
    def delete(self, value: Any, record_key: bytes):
        """Remove value->key mapping. O(1) average."""
    
    def search(self, value: Any) -> Set[bytes]:
        """Return matching record_keys. O(1) average."""
    
    def range_search(self, low: Any, high: Any) -> Set[bytes]:
        """Return keys in range. O(n) - hash indexes are NOT optimized for ranges."""
```

#### IndexManager Class
```python
class IndexManager:
    """Manages indexes for a single table with disk persistence."""
    
    def __init__(self, table_name: str, db_dir: Path = None):
        self.table_name = table_name
        self.indexes: Dict[str, HashIndex] = {}
        self.index_file = self.db_dir / f"{table_name}_indexes.idx"
        self.load_indexes()
    
    def create_index(self, column_name: str) -> bool:
        """Create index on column. Returns False if exists."""
    
    def drop_index(self, column_name: str) -> bool:
        """Drop index. Returns False if doesn't exist."""
    
    def update_index(self, operation: str, record_key: bytes, record_data: dict, old_data: dict = None):
        """Maintain index on INSERT/UPDATE/DELETE."""
    
    def save_indexes(self) / load_indexes(self):
        """Pickle-based persistence."""
```

### 2. Add Grammar Rules
```lark
create_index_query : CREATE INDEX index_name ON table_name column_name
drop_index_query : DROP INDEX index_name ON table_name
index_name : IDENTIFIER
```

### 3. Integrate with DBMS
- Add `index_managers` dict to DBMS.__init__()
- Implement `create_index()` and `drop_index()` methods
- Modify INSERT/UPDATE/DELETE to call `index_mgr.update_index()`
- Build indexes from existing data when CREATE INDEX is called

### 4. Add to run.py
Handle CREATE/DROP INDEX commands similar to other DDL statements.

## Acceptance Criteria
- [ ] CREATE INDEX command works
- [ ] DROP INDEX command works
- [ ] Indexes persist across DBMS restarts
- [ ] INSERT/UPDATE/DELETE maintain index consistency
- [ ] Index lookups are measurably faster than full scans for large tables (>1000 rows)
- [ ] No breaking changes to existing functionality

## Test Cases
```sql
-- Create index
CREATE INDEX idx_account_branch ON account branch_name;

-- Use index (automatic, verified via performance)
SELECT * FROM account WHERE branch_name = 'Perryridge';

-- Drop index
DROP INDEX idx_account_branch ON account;

-- Verify index maintenance
INSERT INTO account VALUES (9999, 'TestBranch');
SELECT * FROM account WHERE branch_name = 'TestBranch';  -- Should find inserted row
```

## Performance Benchmarks
```python
# Test with 10,000 rows
# Without index: ~10ms for point lookup
# With index: ~0.1ms for point lookup (100x improvement)
```

## Files to Create/Modify
- **NEW:** `index.py`
- **MODIFY:** `grammar.lark` (add index rules)
- **MODIFY:** `sql_transformer.py` (add handlers)
- **MODIFY:** `dbms.py` (integrate IndexManager)
- **MODIFY:** `run.py` (add command handlers)

## Dependencies
- **Blocks:** Phase 2.2 (Query Planner needs indexes)
- **Blocked by:** Phase 1 (stable INSERT/UPDATE/DELETE)

## Implementation Notes

### Why Hash Index Instead of B-Tree?
The original plan called this a "B-Tree" but the implementation uses a Python dict, which is a hash table. This is actually a **Hash Index** with:
- ✅ O(1) average-case point lookups
- ❌ O(n) range queries (must scan all entries)
- ❌ No guaranteed O(log n) worst-case

A true B-Tree requires:
- Node splitting/merging logic
- Tree traversal algorithms
- Disk page management
- Significantly more code (~500+ lines vs ~200)

### Index Persistence
Indexes are pickled to `{table_name}_indexes.idx` files. On DBMS startup:
1. Check if index file exists
2. Load with pickle
3. Rebuild if table data is newer (optional optimization)

### Index Maintenance Strategy
- **INSERT:** Add to all indexes on the table
- **DELETE:** Remove from all indexes
- **UPDATE:** Remove old value, add new value

## References
- IMPLEMENTATION_PLAN.md Phase 2.1 (revised from B-Tree to Hash Index)
- Phase 2.2: Query Planner (uses indexes for optimization)
- Phase 2.3: B-Tree Index (advanced bonus for true O(log n))
