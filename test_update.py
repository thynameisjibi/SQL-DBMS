"""
Tests for UPDATE statement implementation (Issue #3).
Run with: python -m pytest test_update.py -v
"""

import shutil
import sys
import os
import unittest
from pathlib import Path

from lark import Lark

# Ensure we import from the current worktree
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dbms import DBMS
from sql_transformer import SQLTransformer
from messages import *


class UpdateTestBase(unittest.TestCase):
    """Base class for UPDATE tests with common setup/teardown."""

    DB_DIR = Path("./DB_TEST_UPDATE")

    @classmethod
    def setUpClass(cls):
        # Point DBMS to test directory
        DBMS.db_dir = cls.DB_DIR
        with open('grammar.lark') as file:
            cls.sql_parser = Lark(file.read(), start="command", lexer="basic")

    def setUp(self):
        # Clean and create fresh DB directory
        if self.DB_DIR.exists():
            shutil.rmtree(self.DB_DIR)
        self.DB_DIR.mkdir(exist_ok=True)
        self.dbms = DBMS()
        self.dbms.db_dir = self.DB_DIR

    def tearDown(self):
        if self.DB_DIR.exists():
            shutil.rmtree(self.DB_DIR)

    def parse_and_transform(self, query: str):
        """Parse a single SQL query and return transformed results."""
        sql_transformer = SQLTransformer()
        parsed = self.sql_parser.parse(query)
        transformed = sql_transformer.transform(parsed)
        return transformed

    def create_test_tables(self):
        """Create standard test tables used across multiple tests."""
        # Table: students(id PK, name NOT NULL, dept_name NOT NULL FK->department)
        self.dbms.create_table({
            "table_name": "students",
            "column_list": [("id", "char(5)"), ("name", "char(20)"), ("dept_name", "char(20)")],
            "not_null_key_set": {"id", "name", "dept_name"},
            "primary_key_list": [("id",)],
            "foreign_key_dict": {"dept_name": ("department", "dept_name")}
        })
        # Table: department(dept_name PK)
        self.dbms.create_table({
            "table_name": "department",
            "column_list": [("dept_name", "char(20)"), ("building", "char(20)"), ("budget", "int")],
            "not_null_key_set": {"dept_name"},
            "primary_key_list": [("dept_name",)],
            "foreign_key_dict": {}
        })
        # Insert parent rows first
        self.dbms.insert({"table_name": "department", "column_name_list": None},
                         ["CS", "Building A", 100])
        self.dbms.insert({"table_name": "department", "column_name_list": None},
                         ["EE", "Building B", 200])
        # Insert student rows
        self.dbms.insert({"table_name": "students", "column_name_list": None},
                         ["S001", "Alice", "CS"])
        self.dbms.insert({"table_name": "students", "column_name_list": None},
                         ["S002", "Bob", "CS"])
        self.dbms.insert({"table_name": "students", "column_name_list": None},
                         ["S003", "Charlie", "EE"])


class TestUpdateGrammarAndTransformer(UpdateTestBase):
    """Tests for grammar parsing and AST transformation of UPDATE."""

    def test_parse_simple_update(self):
        """UPDATE without WHERE should parse and transform correctly."""
        statement, table, record, tables, select_columns, where = \
            self.parse_and_transform("update students set name = 'Dave';")
        self.assertEqual(statement, "update")
        self.assertEqual(table["table_name"], "students")
        self.assertIn("assignments", table)
        self.assertEqual(table["assignments"], [("name", "Dave")])
        self.assertIsNone(where)

    def test_parse_update_with_where(self):
        """UPDATE with WHERE should include condition in transform."""
        statement, table, record, tables, select_columns, where = \
            self.parse_and_transform("update students set name = 'Dave' where id = 'S001';")
        self.assertEqual(statement, "update")
        self.assertEqual(table["table_name"], "students")
        self.assertIn("assignments", table)
        self.assertEqual(table["assignments"], [("name", "Dave")])
        self.assertIsNotNone(where)

    def test_parse_update_multiple_columns(self):
        """UPDATE with multiple assignments should produce a list."""
        statement, table, record, tables, select_columns, where = \
            self.parse_and_transform("update students set name = 'Dave', dept_name = 'EE';")
        self.assertEqual(statement, "update")
        self.assertIn("assignments", table)
        self.assertEqual(table["assignments"], [("name", "Dave"), ("dept_name", "EE")])


class TestUpdateBasicExecution(UpdateTestBase):
    """Tests for basic UPDATE execution behavior."""

    def test_update_without_where(self):
        """UPDATE without WHERE should update all rows."""
        self.create_test_tables()
        result = self.dbms.update("students", [("name", "Updated")], None)
        self.assertEqual(str(result), "'3' row(s) are updated")
        # Verify via select
        output = self.dbms.select(["students"], None, None)
        self.assertIn("Updated", output)

    def test_update_with_where(self):
        """UPDATE with WHERE should only update matching rows."""
        self.create_test_tables()
        where = {
            "op": None,
            "boolean_terms": {
                "op": None,
                "boolean_factors": {
                    "op": None,
                    "boolean_test": {
                        "op": "=",
                        "left_operand": (None, "id"),
                        "right_operand": ("S001",)
                    }
                }
            }
        }
        result = self.dbms.update("students", [("name", "AliceUpdated")], where)
        self.assertEqual(str(result), "'1' row(s) are updated")
        # Verify only S001 changed
        output = self.dbms.select(["students"], None, None)
        self.assertIn("AliceUpdated", output)
        self.assertIn("Bob", output)
        self.assertIn("Charlie", output)

    def test_update_multiple_columns(self):
        """UPDATE should support setting multiple columns at once."""
        self.create_test_tables()
        result = self.dbms.update("students", [("name", "NewName"), ("dept_name", "EE")], None)
        self.assertEqual(str(result), "'3' row(s) are updated")


class TestUpdateConstraints(UpdateTestBase):
    """Tests for UPDATE constraint validation."""

    def test_update_nonexistent_column(self):
        """Updating a non-existent column should raise UpdateColumnExistenceError."""
        self.create_test_tables()
        with self.assertRaises(UpdateColumnExistenceError):
            self.dbms.update("students", [("nonexistent", "value")], None)

    def test_update_type_mismatch(self):
        """Updating with wrong type should raise UpdateTypeMismatchError."""
        self.create_test_tables()
        with self.assertRaises(UpdateTypeMismatchError):
            self.dbms.update("students", [("id", 12345)], None)  # int instead of char

    def test_update_not_null_to_null(self):
        """Setting a NOT NULL column to NULL should raise UpdateColumnNonNullableError."""
        self.create_test_tables()
        with self.assertRaises(UpdateColumnNonNullableError):
            self.dbms.update("students", [("name", None)], None)

    def test_update_duplicate_primary_key(self):
        """Updating PK to an existing value should raise UpdateDuplicatePrimaryKeyError."""
        self.create_test_tables()
        with self.assertRaises(UpdateDuplicatePrimaryKeyError):
            self.dbms.update("students", [("id", "S002")], None)

    def test_update_referential_integrity(self):
        """Updating FK to non-existent referenced value should raise UpdateReferentialIntegrityError."""
        self.create_test_tables()
        with self.assertRaises(UpdateReferentialIntegrityError):
            self.dbms.update("students", [("dept_name", "BIO")], None)


class TestUpdateEdgeCases(UpdateTestBase):
    """Edge case tests for UPDATE."""

    def test_update_no_matching_rows(self):
        """UPDATE with WHERE that matches nothing should report 0 rows updated."""
        self.create_test_tables()
        where = {
            "op": None,
            "boolean_terms": {
                "op": None,
                "boolean_factors": {
                    "op": None,
                    "boolean_test": {
                        "op": "=",
                        "left_operand": (None, "id"),
                        "right_operand": ("NOBODY",)
                    }
                }
            }
        }
        result = self.dbms.update("students", [("name", "Ghost")], where)
        self.assertEqual(str(result), "'0' row(s) are updated")

    def test_update_on_empty_table(self):
        """UPDATE on empty table should report 0 rows updated."""
        self.dbms.create_table({
            "table_name": "empty_table",
            "column_list": [("id", "int"), ("name", "char(20)")],
            "not_null_key_set": {"id"},
            "primary_key_list": [("id",)],
            "foreign_key_dict": {}
        })
        result = self.dbms.update("empty_table", [("name", "X")], None)
        self.assertEqual(str(result), "'0' row(s) are updated")

    def test_update_no_such_table(self):
        """UPDATE on non-existent table should raise NoSuchTable."""
        with self.assertRaises(NoSuchTable):
            self.dbms.update("nosuchtable", [("col", "val")], None)

    def test_update_null_on_nullable_column(self):
        """Setting a nullable column to NULL should succeed."""
        self.dbms.create_table({
            "table_name": "nullable_table",
            "column_list": [("id", "int"), ("name", "char(20)")],
            "not_null_key_set": {"id"},
            "primary_key_list": [("id",)],
            "foreign_key_dict": {}
        })
        self.dbms.insert({"table_name": "nullable_table", "column_name_list": None},
                         [1, "Alice"])
        result = self.dbms.update("nullable_table", [("name", None)], None)
        self.assertEqual(str(result), "'1' row(s) are updated")


if __name__ == "__main__":
    unittest.main(verbosity=2)
