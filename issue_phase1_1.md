# Phase 1.1: Full Type & Constraint Checking

## Overview
Enhance INSERT validation to strictly enforce types, NOT NULL constraints, CHAR length limits, and date format validation.

## Current State
The current `is_valid_type()` function in `utils.py` has gaps:
- Accepts booleans as integers (Python bool is subclass of int)
- No CHAR(N) length validation
- No strict date format validation (YYYY-MM-DD)
- No specific error messages for different validation failures

## Tasks

### 1. Enhance `is_valid_type()` in utils.py
```python
def is_valid_type(valid_type, value):
    if value is None:
        return True  # NULL check handled separately
    
    try:
        if valid_type == "int":
            # Reject booleans
            return isinstance(value, int) and not isinstance(value, bool)
        
        elif valid_type.startswith("char"):
            max_len = eval_char_max_len(valid_type)
            return isinstance(value, str) and len(value) <= max_len
        
        elif valid_type == "date":
            if not isinstance(value, str):
                return False
            match = re.match(DATE_PATTERN, value)
            if not match:
                return False
            # Validate month/day ranges
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

### 2. Enhance INSERT validation in dbms.py
Add specific validation with detailed error messages in the `insert()` method (lines 163-168):
```python
for column_name, data_type, value in zip(table.columns.keys(), table.columns.values(), value_list):
    # Check NOT NULL
    if value is None and column_name in table.not_null_keys:
        raise InsertColumnNonNullableError(column_name)
    
    # Check char length
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

## Acceptance Criteria
- [ ] Boolean values rejected for INT columns
- [ ] CHAR(N) length enforced at insert time
- [ ] Date format strictly validated (YYYY-MM-DD with valid month/day ranges)
- [ ] NOT NULL constraint checked before type validation
- [ ] Specific exception raised for each validation failure

## Test Cases
```sql
-- Should FAIL: bool into int
INSERT INTO account VALUES (true, 'Test');

-- Should FAIL: wrong date format
INSERT INTO transactions VALUES ('2023/12/25');

-- Should FAIL: string too long for char(15)
INSERT INTO account VALUES (1234, 'ThisBranchNameIsWayTooLong');

-- Should FAIL: NULL into NOT NULL column
INSERT INTO account VALUES (NULL, 'Test');

-- Should FAIL: invalid month
INSERT INTO transactions VALUES ('2023-13-25');

-- Should PASS: valid date
INSERT INTO transactions VALUES ('2023-12-25');

-- Should PASS: valid char within length
INSERT INTO account VALUES (1234, 'Downtown');
```

## Files to Modify
- `utils.py` - `is_valid_type()` function (lines 58-69)
- `dbms.py` - `insert()` method (lines 163-168)
- `messages.py` - Already has exceptions from Phase 0

## Dependencies
- **Blocks:** None
- **Blocked by:** Phase 0 (exception classes must exist first)

## References
- IMPLEMENTATION_PLAN.md Phase 1.1
- Related: Phase 0 (exception classes)
