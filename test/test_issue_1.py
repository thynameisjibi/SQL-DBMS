"""
Tests for Issue #1: Phase 0 Foundation
- Exception classes
- Multi-assignment UPDATE grammar parsing
- Multi-assignment UPDATE transformer output
"""

import pytest
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lark import Lark
from messages import (
    SuccessLog,
    InsertDateFormatException,
    InsertCharLengthExceeded,
    UpdateReferentialIntegrityError,
    UpdateTypeMismatchError,
    UpdateResult,
    ActiveTransactionError,
    NoActiveTransactionError,
    InvalidTransactionStateError,
)
from sql_transformer import SQLTransformer


# --------------------------------------------------------------------------- #
#                              Exception Tests                                #
# --------------------------------------------------------------------------- #

class TestExceptions:
    """Verify all new exception classes can be instantiated with correct messages."""

    def test_insert_date_format_exception(self):
        e = InsertDateFormatException()
        assert isinstance(e, Exception)
        assert str(e) == "Insertion has failed: Date format is not valid (YYYY-MM-DD)"

    def test_insert_char_length_exceeded(self):
        e = InsertCharLengthExceeded("name", 20)
        assert isinstance(e, Exception)
        assert str(e) == "Insertion has failed: 'name' exceeds char(20) length"

    def test_update_referential_integrity_error(self):
        e = UpdateReferentialIntegrityError()
        assert isinstance(e, Exception)
        assert str(e) == "Update has failed: Referential integrity violation"

    def test_update_type_mismatch_error(self):
        e = UpdateTypeMismatchError()
        assert isinstance(e, Exception)
        assert str(e) == "Update has failed: Types are not matched"

    def test_update_result_is_success_log(self):
        e = UpdateResult(3)
        assert isinstance(e, SuccessLog)
        assert str(e) == "'3' row(s) are updated"

    def test_update_result_zero_rows(self):
        e = UpdateResult(0)
        assert isinstance(e, SuccessLog)
        assert str(e) == "'0' row(s) are updated"

    def test_active_transaction_error(self):
        e = ActiveTransactionError()
        assert isinstance(e, Exception)
        assert str(e) == "Transaction has failed: A transaction is already active"

    def test_no_active_transaction_error(self):
        e = NoActiveTransactionError()
        assert isinstance(e, Exception)
        assert str(e) == "Transaction has failed: No active transaction"

    def test_invalid_transaction_state_error(self):
        e = InvalidTransactionStateError()
        assert isinstance(e, Exception)
        assert str(e) == "Transaction has failed: Invalid transaction state"


# --------------------------------------------------------------------------- #
#                              Grammar Tests                                  #
# --------------------------------------------------------------------------- #

@pytest.fixture(scope="module")
def sql_parser():
    grammar_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "grammar.lark")
    with open(grammar_path) as f:
        return Lark(f.read(), start="command", lexer="basic")


class TestUpdateGrammar:
    """Test that UPDATE statements with single and multiple assignments parse correctly."""

    def test_single_assignment_parses(self, sql_parser):
        query = "UPDATE account SET branch_name = 'Downtown' WHERE account_number = 9732;"
        tree = sql_parser.parse(query)
        assert tree is not None
        assert tree.data == "command"
        assert any(child.data == "update_query" for child in tree.iter_subtrees())

    def test_two_assignments_parses(self, sql_parser):
        query = "UPDATE account SET branch_name = 'Downtown', balance = 500 WHERE account_number = 9732;"
        tree = sql_parser.parse(query)
        assert tree is not None
        assert tree.data == "command"
        assert any(child.data == "update_query" for child in tree.iter_subtrees())

    def test_three_assignments_parses(self, sql_parser):
        query = "UPDATE account SET branch_name = 'Downtown', balance = 500, account_type = 'checking' WHERE account_number = 9732;"
        tree = sql_parser.parse(query)
        assert tree is not None
        assert tree.data == "command"
        assert any(child.data == "update_query" for child in tree.iter_subtrees())

    def test_update_without_where_parses(self, sql_parser):
        query = "UPDATE account SET balance = 0;"
        tree = sql_parser.parse(query)
        assert tree is not None
        assert tree.data == "command"
        assert any(child.data == "update_query" for child in tree.iter_subtrees())

    def test_update_complex_where_parses(self, sql_parser):
        query = "UPDATE account SET branch_name = 'Main', balance = 1000 WHERE account_number = 9732 AND balance < 500;"
        tree = sql_parser.parse(query)
        assert tree is not None
        assert tree.data == "command"
        assert any(child.data == "update_query" for child in tree.iter_subtrees())

    def test_multiple_assignments_without_where_parses(self, sql_parser):
        query = "UPDATE account SET branch_name = 'Downtown', balance = 500;"
        tree = sql_parser.parse(query)
        assert tree is not None
        assert tree.data == "command"
        assert any(child.data == "update_query" for child in tree.iter_subtrees())


# --------------------------------------------------------------------------- #
#                            Transformer Tests                                #
# --------------------------------------------------------------------------- #

class TestUpdateTransformer:
    """Verify SQLTransformer correctly handles UPDATE with single and multi-assignment."""

    def test_single_assignment_transformer(self, sql_parser):
        query = "UPDATE account SET branch_name = 'Downtown' WHERE account_number = 9732;"
        transformer = SQLTransformer()
        parsed = sql_parser.parse(query)
        transformer.transform(parsed)

        assert transformer.statement == "update"
        assert transformer.table["table_name"] == "account"
        assert "set_columns" in transformer.table
        assert len(transformer.table["set_columns"]) == 1
        assert transformer.table["set_columns"][0] == ("branch_name", "Downtown")
        assert transformer.where is not None

    def test_two_assignments_transformer(self, sql_parser):
        query = "UPDATE account SET branch_name = 'Downtown', balance = 500 WHERE account_number = 9732;"
        transformer = SQLTransformer()
        parsed = sql_parser.parse(query)
        transformer.transform(parsed)

        assert transformer.statement == "update"
        assert transformer.table["table_name"] == "account"
        assert "set_columns" in transformer.table
        assert len(transformer.table["set_columns"]) == 2
        assert ("branch_name", "Downtown") in transformer.table["set_columns"]
        assert ("balance", 500) in transformer.table["set_columns"]
        assert transformer.where is not None

    def test_three_assignments_transformer(self, sql_parser):
        query = "UPDATE account SET branch_name = 'Downtown', balance = 500, account_type = 'checking' WHERE account_number = 9732;"
        transformer = SQLTransformer()
        parsed = sql_parser.parse(query)
        transformer.transform(parsed)

        assert transformer.statement == "update"
        assert len(transformer.table["set_columns"]) == 3
        assert ("branch_name", "Downtown") in transformer.table["set_columns"]
        assert ("balance", 500) in transformer.table["set_columns"]
        assert ("account_type", "checking") in transformer.table["set_columns"]

    def test_update_without_where_transformer(self, sql_parser):
        query = "UPDATE account SET balance = 0;"
        transformer = SQLTransformer()
        parsed = sql_parser.parse(query)
        transformer.transform(parsed)

        assert transformer.statement == "update"
        assert transformer.table["table_name"] == "account"
        assert len(transformer.table["set_columns"]) == 1
        assert transformer.table["set_columns"][0] == ("balance", 0)
        assert transformer.where is None

    def test_update_complex_where_transformer(self, sql_parser):
        query = "UPDATE account SET branch_name = 'Main', balance = 1000 WHERE account_number = 9732 AND balance < 500;"
        transformer = SQLTransformer()
        parsed = sql_parser.parse(query)
        transformer.transform(parsed)

        assert transformer.statement == "update"
        assert len(transformer.table["set_columns"]) == 2
        assert transformer.where is not None
        # Verify AND structure is preserved in nested where dict
        assert isinstance(transformer.where.get("boolean_terms"), dict)
        assert transformer.where["boolean_terms"].get("op") == "and"
        assert isinstance(transformer.where["boolean_terms"].get("boolean_factors", []), list)

    def test_multiple_assignments_without_where_transformer(self, sql_parser):
        query = "UPDATE account SET branch_name = 'Downtown', balance = 500;"
        transformer = SQLTransformer()
        parsed = sql_parser.parse(query)
        transformer.transform(parsed)

        assert transformer.statement == "update"
        assert len(transformer.table["set_columns"]) == 2
        assert transformer.where is None


# --------------------------------------------------------------------------- #
#                         Adversarial / Edge Case Tests                     #
# --------------------------------------------------------------------------- #

class TestAdversarialEdgeCases:
    """Hostile QA: try to break the parser and transformer."""

    def test_update_with_null_value(self, sql_parser):
        query = "UPDATE account SET branch_name = NULL WHERE account_number = 9732;"
        transformer = SQLTransformer()
        parsed = sql_parser.parse(query)
        transformer.transform(parsed)
        assert transformer.table["set_columns"][0] == ("branch_name", None)

    def test_update_with_date_value(self, sql_parser):
        query = "UPDATE account SET opened = 2023-01-15 WHERE account_number = 9732;"
        transformer = SQLTransformer()
        parsed = sql_parser.parse(query)
        transformer.transform(parsed)
        assert transformer.table["set_columns"][0] == ("opened", "2023-01-15")

    def test_update_with_special_chars_in_string(self, sql_parser):
        query = "UPDATE account SET branch_name = 'Downtown, Main St.' WHERE account_number = 9732;"
        transformer = SQLTransformer()
        parsed = sql_parser.parse(query)
        transformer.transform(parsed)
        assert transformer.table["set_columns"][0] == ("branch_name", "Downtown, Main St.")

    def test_update_with_many_assignments(self, sql_parser):
        query = "UPDATE t SET a = 1, b = 2, c = 3, d = 4, e = 5, f = 6, g = 7, h = 8, i = 9, j = 10;"
        transformer = SQLTransformer()
        parsed = sql_parser.parse(query)
        transformer.transform(parsed)
        assert len(transformer.table["set_columns"]) == 10
        assert transformer.where is None

    def test_update_with_negative_int(self, sql_parser):
        query = "UPDATE account SET balance = -500 WHERE account_number = 9732;"
        transformer = SQLTransformer()
        parsed = sql_parser.parse(query)
        transformer.transform(parsed)
        assert transformer.table["set_columns"][0] == ("balance", -500)

    def test_update_with_quoted_keyword_value(self, sql_parser):
        query = "UPDATE account SET status = 'select' WHERE account_number = 9732;"
        transformer = SQLTransformer()
        parsed = sql_parser.parse(query)
        transformer.transform(parsed)
        assert transformer.table["set_columns"][0] == ("status", "select")

    def test_update_with_or_where(self, sql_parser):
        query = "UPDATE account SET balance = 0 WHERE account_number = 1 OR account_number = 2;"
        transformer = SQLTransformer()
        parsed = sql_parser.parse(query)
        transformer.transform(parsed)
        assert len(transformer.table["set_columns"]) == 1
        assert transformer.where is not None

    def test_update_with_null_where(self, sql_parser):
        query = "UPDATE account SET balance = 0 WHERE branch_name IS NULL;"
        transformer = SQLTransformer()
        parsed = sql_parser.parse(query)
        transformer.transform(parsed)
        assert transformer.where is not None
