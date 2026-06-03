"""
Adversarial tests for UPDATE statement (Issue #3).
Run with: python -m pytest test_adversarial_update.py -v
"""

import shutil
import sys
import os
import unittest
from pathlib import Path
from uuid import uuid4

from lark import Lark

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dbms import DBMS
from sql_transformer import SQLTransformer
from messages import *
import db_model


class UpdateAdversarialTest(unittest.TestCase):
    """Hostile QA: try to break UPDATE."""

    def setUp(self):
        self.db_dir = Path(f"./DB_ADV_UPDATE_{uuid4().hex[:8]}")
        self.db_dir.mkdir(exist_ok=True)
        db_model.DB.db_dir = self.db_dir
        original_db_init = db_model.DB.__init__
        def patched_init(self, db_name):
            self.db_dir = db_model.DB.db_dir
            self.db_dir.mkdir(exist_ok=True)
            self.db_name = db_name
            self.db_file = self.db_dir / (self.db_name + ".db")
            self.DB = None
        db_model.DB.__init__ = patched_init
        self._original_db_init = original_db_init
        self.dbms = DBMS()
        self.dbms.db_dir = self.db_dir
        self.dbms.meta_db.db_dir = self.db_dir
        self.dbms.meta_db.db_file = self.db_dir / (self.dbms.meta_db.db_name + ".db")

    def tearDown(self):
        try:
            self.dbms.meta_db.close_db()
        except Exception:
            pass
        db_model.DB.__init__ = self._original_db_init
        if self.db_dir.exists():
            shutil.rmtree(self.db_dir, ignore_errors=True)
        default_db = Path("./DB")
        if default_db.exists():
            shutil.rmtree(default_db, ignore_errors=True)

    def test_update_very_long_string(self):
        """UPDATE with a very long string should be truncated for char columns."""
        self.dbms.create_table({
            "table_name": "t",
            "column_list": [("id", "int"), ("name", "char(5)")],
            "not_null_key_set": {"id"},
            "primary_key_list": [("id",)],
            "foreign_key_dict": {}
        })
        self.dbms.insert({"table_name": "t", "column_name_list": None}, [1, "AB"])
        result = self.dbms.update("t", [("name", "VERYLONGSTRING")], None)
        self.assertEqual(str(result), "'1' row(s) are updated")
        # Verify truncation
        table_db = db_model.DB("t")
        table_db.open_db()
        record = table_db.get(table_db.create_key_from_value((1,)))
        table_db.close_db()
        self.assertEqual(record.data["name"], "VERYL")  # truncated to 5 chars

    def test_update_empty_string(self):
        """UPDATE to empty string on char column should succeed."""
        self.dbms.create_table({
            "table_name": "t",
            "column_list": [("id", "int"), ("name", "char(5)")],
            "not_null_key_set": {"id"},
            "primary_key_list": [("id",)],
            "foreign_key_dict": {}
        })
        self.dbms.insert({"table_name": "t", "column_name_list": None}, [1, "AB"])
        result = self.dbms.update("t", [("name", "")], None)
        self.assertEqual(str(result), "'1' row(s) are updated")

    def test_update_unicode_in_char(self):
        """UPDATE with unicode characters should work in char columns."""
        self.dbms.create_table({
            "table_name": "t",
            "column_list": [("id", "int"), ("name", "char(20)")],
            "not_null_key_set": {"id"},
            "primary_key_list": [("id",)],
            "foreign_key_dict": {}
        })
        self.dbms.insert({"table_name": "t", "column_name_list": None}, [1, "AB"])
        result = self.dbms.update("t", [("name", "Hello \u4e16\u754c")], None)
        self.assertEqual(str(result), "'1' row(s) are updated")

    def test_update_negative_int(self):
        """UPDATE with negative int should work."""
        self.dbms.create_table({
            "table_name": "t",
            "column_list": [("id", "int"), ("val", "int")],
            "not_null_key_set": {"id"},
            "primary_key_list": [("id",)],
            "foreign_key_dict": {}
        })
        self.dbms.insert({"table_name": "t", "column_name_list": None}, [1, 10])
        result = self.dbms.update("t", [("val", -999)], None)
        self.assertEqual(str(result), "'1' row(s) are updated")

    def test_update_zero_rows_where(self):
        """UPDATE with WHERE matching 0 rows should report 0."""
        self.dbms.create_table({
            "table_name": "t",
            "column_list": [("id", "int"), ("name", "char(5)")],
            "not_null_key_set": {"id"},
            "primary_key_list": [("id",)],
            "foreign_key_dict": {}
        })
        self.dbms.insert({"table_name": "t", "column_name_list": None}, [1, "A"])
        where = {
            "op": None,
            "boolean_terms": {
                "op": None,
                "boolean_factors": {
                    "op": None,
                    "boolean_test": {
                        "op": "=",
                        "left_operand": (None, "id"),
                        "right_operand": (999,)
                    }
                }
            }
        }
        result = self.dbms.update("t", [("name", "X")], where)
        self.assertEqual(str(result), "'0' row(s) are updated")

    def test_update_pk_to_same_value(self):
        """UPDATE PK to its current value should succeed (no duplicate)."""
        self.dbms.create_table({
            "table_name": "t",
            "column_list": [("id", "int"), ("name", "char(5)")],
            "not_null_key_set": {"id"},
            "primary_key_list": [("id",)],
            "foreign_key_dict": {}
        })
        self.dbms.insert({"table_name": "t", "column_name_list": None}, [1, "A"])
        result = self.dbms.update("t", [("id", 1)], None)
        self.assertEqual(str(result), "'1' row(s) are updated")

    def test_update_multiple_rows_pk(self):
        """UPDATE PK on multiple rows should raise on duplicate."""
        self.dbms.create_table({
            "table_name": "t",
            "column_list": [("id", "int"), ("name", "char(5)")],
            "not_null_key_set": {"id"},
            "primary_key_list": [("id",)],
            "foreign_key_dict": {}
        })
        self.dbms.insert({"table_name": "t", "column_name_list": None}, [1, "A"])
        self.dbms.insert({"table_name": "t", "column_name_list": None}, [2, "B"])
        with self.assertRaises(UpdatePrimaryKeyError):
            self.dbms.update("t", [("id", 3)], None)

    def test_update_fk_to_same_value(self):
        """UPDATE FK to its current value should succeed."""
        self.dbms.create_table({
            "table_name": "dept",
            "column_list": [("dept_name", "char(20)")],
            "not_null_key_set": {"dept_name"},
            "primary_key_list": [("dept_name",)],
            "foreign_key_dict": {}
        })
        self.dbms.create_table({
            "table_name": "emp",
            "column_list": [("id", "int"), ("dept_name", "char(20)")],
            "not_null_key_set": {"id"},
            "primary_key_list": [("id",)],
            "foreign_key_dict": {"dept_name": ("dept", "dept_name")}
        })
        self.dbms.insert({"table_name": "dept", "column_name_list": None}, ["CS"])
        self.dbms.insert({"table_name": "emp", "column_name_list": None}, [1, "CS"])
        result = self.dbms.update("emp", [("dept_name", "CS")], None)
        self.assertEqual(str(result), "'1' row(s) are updated")

    def test_update_referenced_by_blocks_pk_change(self):
        """UPDATE PK when record is referenced by another table should fail."""
        self.dbms.create_table({
            "table_name": "dept",
            "column_list": [("dept_name", "char(20)")],
            "not_null_key_set": {"dept_name"},
            "primary_key_list": [("dept_name",)],
            "foreign_key_dict": {}
        })
        self.dbms.create_table({
            "table_name": "emp",
            "column_list": [("id", "int"), ("dept_name", "char(20)")],
            "not_null_key_set": {"id"},
            "primary_key_list": [("id",)],
            "foreign_key_dict": {"dept_name": ("dept", "dept_name")}
        })
        self.dbms.insert({"table_name": "dept", "column_name_list": None}, ["CS"])
        self.dbms.insert({"table_name": "emp", "column_name_list": None}, [1, "CS"])
        with self.assertRaises(UpdateReferentialIntegrityError):
            self.dbms.update("dept", [("dept_name", "EE")], None)

    def test_update_all_columns(self):
        """UPDATE all columns in a row should work."""
        self.dbms.create_table({
            "table_name": "t",
            "column_list": [("a", "int"), ("b", "char(5)")],
            "not_null_key_set": set(),
            "primary_key_list": [],
            "foreign_key_dict": {}
        })
        self.dbms.insert({"table_name": "t", "column_name_list": None}, [1, "X"])
        result = self.dbms.update("t", [("a", 99), ("b", "YYY")], None)
        self.assertEqual(str(result), "'1' row(s) are updated")

    def test_update_date_value(self):
        """UPDATE with a valid date value should succeed."""
        self.dbms.create_table({
            "table_name": "t",
            "column_list": [("id", "int"), ("d", "date")],
            "not_null_key_set": {"id"},
            "primary_key_list": [("id",)],
            "foreign_key_dict": {}
        })
        self.dbms.insert({"table_name": "t", "column_name_list": None}, [1, "2023-01-01"])
        result = self.dbms.update("t", [("d", "2024-12-25")], None)
        self.assertEqual(str(result), "'1' row(s) are updated")

    def test_update_invalid_date(self):
        """UPDATE with invalid date format should raise type mismatch."""
        self.dbms.create_table({
            "table_name": "t",
            "column_list": [("id", "int"), ("d", "date")],
            "not_null_key_set": {"id"},
            "primary_key_list": [("id",)],
            "foreign_key_dict": {}
        })
        self.dbms.insert({"table_name": "t", "column_name_list": None}, [1, "2023-01-01"])
        with self.assertRaises(UpdateTypeMismatchError):
            self.dbms.update("t", [("d", "not-a-date")], None)

    def test_update_where_with_null_comparison(self):
        """UPDATE with WHERE comparing NULL should use UNKNOWN semantics."""
        self.dbms.create_table({
            "table_name": "t",
            "column_list": [("id", "int"), ("name", "char(5)")],
            "not_null_key_set": set(),
            "primary_key_list": [("id",)],
            "foreign_key_dict": {}
        })
        self.dbms.insert({"table_name": "t", "column_name_list": None}, [1, None])
        where = {
            "op": None,
            "boolean_terms": {
                "op": None,
                "boolean_factors": {
                    "op": None,
                    "boolean_test": {
                        "op": "=",
                        "left_operand": (None, "name"),
                        "right_operand": ("X",)
                    }
                }
            }
        }
        result = self.dbms.update("t", [("id", 99)], where)
        self.assertEqual(str(result), "'0' row(s) are updated")


if __name__ == "__main__":
    unittest.main(verbosity=2)
