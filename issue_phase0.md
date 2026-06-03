# Phase 0: Foundation & Prerequisites

## Overview
Foundational changes required before implementing core enhancements. These changes unblock Phase 1 (Type Checking & UPDATE) and subsequent phases.

## Tasks

### 0.1 Exception Classes (messages.py)
Add 10 new exception classes:

**Type Checking (Phase 1.1):**
- `InsertDateFormatException` - Invalid date format
- `InsertCharLengthExceeded` - String exceeds char(N) length  
- `UpdateReferentialIntegrityError` - FK constraint violated on UPDATE
- `UpdateTypeMismatchError` - Type mismatch on UPDATE
- `UpdateResult` (SuccessLog) - Success with row count

**Transactions (Phase 3.1):**
- `ActiveTransactionError` - Nested BEGIN attempt
- `NoActiveTransactionError` - COMMIT/ROLLBACK without BEGIN
- `InvalidTransactionStateError` - Invalid transaction operation

### 0.2 Grammar Updates (grammar.lark, sql_transformer.py)
Update UPDATE grammar to support multiple assignments:
```lark
update_query : UPDATE table_name SET assignment ("," assignment)* [where_clause]
assignment : column_name EQUAL value
```

Update transformer to return `set_columns` as list of tuples.

## Acceptance Criteria
- [ ] All 10 exception classes added
- [ ] Grammar accepts multi-assignment UPDATE
- [ ] Backward compatible with single-assignment UPDATE
- [ ] All test cases pass

## Test Cases
```sql
-- Multi-assignment
UPDATE account SET branch_name = 'Downtown', balance = 500 WHERE account_number = 9732;

-- Single-assignment (backward compat)
UPDATE account SET branch_name = 'Downtown' WHERE account_number = 9732;
```

## Files to Modify
- `messages.py`
- `grammar.lark` (line 152)
- `sql_transformer.py`

## References
- See IMPLEMENTATION_PLAN.md Phase 0
