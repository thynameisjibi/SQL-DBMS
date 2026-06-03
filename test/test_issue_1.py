"""
Tests for Issue #1: Phase 0 Foundation
- Exception classes
- Multi-assignment UPDATE grammar parsing
- Multi-assignment UPDATE transformer output
"""

import pytest
import sys
import os
import tempfile
import shutil

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
        assert "date" in str(e).lower() or "format" in str(e).lower()

    def test_insert_char_length_exceeded(self):
        e = InsertCharLengthExceeded("name", 20)
        assert isinstance(e, Exception)
        assert "char" in str(e).lower() or "length" in str(e).lower()
        assert "name" in str(e)
        assert "20" in str(e)

    def test_update_referential_integrity_error(self):
        e = UpdateReferentialIntegrityError()
        assert isinstance(e, Exception)
        assert "referential" in str(e).lower() or "integrity" in str(e).lower()

    def test_update_type_mismatch_error(self):
        e = UpdateTypeMismatchError()
        assert isinstance(e, Exception)
        assert "type" in str(e).lower() or "mismatch" in str(e).lower()

    def test_update_result_is_success_log(self):
        e = UpdateResult(3)
        assert isinstance(e, SuccessLog)
        assert "3" in str(e)
        assert "row" in str(e).lower() or "update" in str(e).lower()

    def test_active_transaction_error(self):
        e = ActiveTransactionError()
        assert isinstance(e, Exception)
        assert "transaction" in str(e).lower() or "active" in str(e).lower()

    def test_no_active_transaction_error(self):
        e = NoActiveTransactionError()
        assert isinstance(e, Exception)
        assert "transaction" in str(e).lower() or "active" in str(e).lower()

    def test_invalid_transaction_state_error(self):
        e = InvalidTransactionStateError()
        assert isinstance(e, Exception)
        assert "transaction" in str(e).lower() or "state" in str(e).lower()


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

    def test_two_assignments_parses(self, sql_parser):
        query = "UPDATE account SET branch_name = 'Downtown', balance = 500 WHERE account_number = 9732;"
        tree = sql_parser.parse(query)
        assert tree is not None
        assert tree.data == "command"

    def test_three_assignments_parses(self, sql_parser):
        query = "UPDATE account SET branch_name = 'Downtown', balance = 500, account_type = 'checking' WHERE account_number = 9732;"
        tree = sql_parser.parse(query)
        assert tree is not None
        assert tree.data == "command"

    def test_update_without_where_parses(self, sql_parser):
        query = "UPDATE account SET balance = 0;"
        tree = sql_parser.parse(query)
        assert tree is not None
        assert tree.data == "command"

    def test_update_complex_where_parses(self, sql_parser):
        query = "UPDATE account SET branch_name = 'Main', balance = 1000 WHERE account_number = 9732 AND balance < 500;"
        tree = sql_parser.parse(query)
        assert tree is not None
        assert tree.data == "command"

    def test_multiple_assignments_without_where_parses(self, sql_parser):
        query = "UPDATE account SET branch_name = 'Downtown', balance = 500;"
        tree = sql_parser.parse(query)
        assert tree is not None
        assert tree.data == "command"


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
        # The where should be a dict with boolean expression
        assert isinstance(transformer.where, dict)

    def test_multiple_assignments_without_where_transformer(self, sql_parser):
        query = "UPDATE account SET branch_name = 'Downtown', balance = 500;"
        transformer = SQLTransformer()
        parsed = sql_parser.parse(query)
        transformer.transform(parsed)

        assert transformer.statement == "update"
        assert len(transformer.table["set_columns"]) == 2
        assert transformer.where is None
