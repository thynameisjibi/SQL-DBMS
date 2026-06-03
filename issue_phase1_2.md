# Phase 1.2: UPDATE Statement Implementation

## Overview
Implement the UPDATE statement with full constraint checking, supporting both single and multiple column assignments.

## Current State
The UPDATE grammar exists (grammar.lark line 152) but the transformer returns a placeholder string `"'UPDATE' requested"` instead of parsing the statement properly. The DBMS has no `update()` method.

## Tasks

### 1. Update Grammar (Phase 0.2 - Prerequisite)
Ensure grammar supports multiple assignments:
```lark
update_query : UPDATE table_name SET assignment ("," assignment)* [where_clause]
assignment : column_name EQUAL value
```

### 2. Update SQLTransformer
Replace the placeholder `update_query()` method (sql_transformer.py line 249):
```python
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

### 3. Implement DBMS.update() Method
Add new method in dbms.py after the `delete()` method:
```python
def update(self, table_name: str, set_columns: list, where_clause: dict):
    """
    UPDATE table_name SET column1=value1, column2=value2 WHERE condition
    
    Args:
        table_name: Target table name
        set_columns: List of (column_name, value) tuples
        where_clause: Parsed WHERE condition dict (or None for all rows)
    
    Returns:
        UpdateResult with count of affected rows
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
            
            # Update record
            table_db.put(key, record)
            success_cnt += 1
        
        key_value_pair = cursor.next()
    
    table_db.discard_cursor(cursor)
    table_db.close_db()
    
    return UpdateResult(success_cnt)
```

### 4. Update run.py
Add UPDATE handler (after line 47):
```python
elif statement == "update":
    result = dbms.update(table["table_name"], table["set_columns"], where)
    print(PROMPT + str(result))
```

Add exceptions to handler tuple (line 48-54):
```python
except (..., UpdateReferentialIntegrityError, UpdateTypeMismatchError) as e:
```

## Acceptance Criteria
- [ ] Single-column UPDATE works with WHERE clause
- [ ] Multi-column UPDATE works (comma-separated SET assignments)
- [ ] UPDATE without WHERE updates all rows
- [ ] FK constraint violations raise `UpdateReferentialIntegrityError`
- [ ] Type mismatches raise `UpdateTypeMismatchError`
- [ ] Returns correct count of updated rows

## Test Cases
```sql
-- Basic update with WHERE
UPDATE account SET branch_name = 'Downtown' WHERE account_number = 9732;

-- Multiple column update
UPDATE account SET branch_name = 'Perryridge', balance = 500 WHERE account_number = 9732;

-- Update all rows (no WHERE)
UPDATE account SET balance = 0;

-- Should FAIL: FK violation
UPDATE borrower SET loan_number = 'L-999' WHERE customer_name = 'Smith';

-- Should FAIL: type mismatch
UPDATE account SET balance = 'not_a_number' WHERE account_number = 9732;
```

## Files to Modify
- `grammar.lark` (line 152) - Phase 0.2
- `sql_transformer.py` (lines 249-251)
- `dbms.py` (add new method after line 269)
- `run.py` (lines 47-54)
- `messages.py` - Already has exceptions from Phase 0

## Dependencies
- **Blocks:** Phase 3.1 (transactions need UPDATE support)
- **Blocked by:** Phase 0 (grammar updates, exception classes)

## Implementation Notes
- The UPDATE implementation follows the same pattern as DELETE (cursor-based iteration)
- WHERE clause evaluation reuses existing `_evaluate_condition()` method
- FK validation happens BEFORE any updates are applied (all-or-nothing)

## References
- IMPLEMENTATION_PLAN.md Phase 1.2
- Related: Phase 0 (foundational changes)
