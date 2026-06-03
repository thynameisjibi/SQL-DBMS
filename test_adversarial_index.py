"""Adversarial tests for CREATE INDEX / DROP INDEX."""
import unittest
from pathlib import Path
import shutil
from lark import Lark

from run import parse_query
from sql_transformer import SQLTransformer
from dbms import DBMS
from messages import *


class TestIndexAdversarial(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open('grammar.lark') as f:
            cls.sql_parser = Lark(f.read(), start="command", lexer="basic")

    def setUp(self):
        self.test_dir = Path("./test_adv_index")
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir(exist_ok=True)
        self.dbms = DBMS()
        self.dbms.db_dir = self.test_dir

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def _run(self, sql):
        t = SQLTransformer()
        stmt, table, record, tables, sel_cols, where, idx = parse_query(
            self.sql_parser, t, sql
        )
        if stmt == "create table":
            return self.dbms.create_table(table)
        elif stmt == "create index":
            return self.dbms.create_index(table["table_name"], idx["index_name"], idx["column_name"])
        elif stmt == "drop index":
            return self.dbms.drop_index(table["table_name"], idx["index_name"])
        elif stmt == "insert":
            return self.dbms.insert(table, record)
        elif stmt == "delete":
            result, _ = self.dbms.delete(table["table_name"], where)
            return result
        elif stmt == "drop table":
            return self.dbms.drop_table(table["table_name"])
        return stmt

    @unittest.expectedFailure  # Grammar LETTER token is ASCII-only
    def test_unicode_index_name(self):
        """Unicode characters in index name — grammar limitation."""
        self._run("CREATE TABLE t (id INT, name CHAR(20), PRIMARY KEY (id));")
        self._run("CREATE INDEX idx_ñame ON t (name);")
        table = self.dbms.explain_describe_desc("t")
        self.assertTrue(table.has_index_name("idx_ñame"))

    def test_very_long_index_name(self):
        """Very long index name should still work."""
        long_name = "idx_" + "a" * 200
        self._run("CREATE TABLE t (id INT, col INT, PRIMARY KEY (id));")
        self._run(f"CREATE INDEX {long_name} ON t (col);")
        table = self.dbms.explain_describe_desc("t")
        self.assertTrue(table.has_index_name(long_name))

    def test_same_index_name_different_tables(self):
        """Same index name on different tables is allowed."""
        self._run("CREATE TABLE ta (id INT, col INT, PRIMARY KEY (id));")
        self._run("CREATE TABLE tb (id INT, col INT, PRIMARY KEY (id));")
        self._run("CREATE INDEX idx_col ON ta (col);")
        self._run("CREATE INDEX idx_col ON tb (col);")

    def test_drop_recreate_reindex(self):
        """Drop table with index, recreate, re-index."""
        self._run("CREATE TABLE tc (id INT, col INT, PRIMARY KEY (id));")
        self._run("INSERT INTO tc VALUES (1, 100);")
        self._run("CREATE INDEX idx_tc ON tc (col);")
        self._run("DROP TABLE tc;")
        self._run("CREATE TABLE tc (id INT, col INT, PRIMARY KEY (id));")
        self._run("INSERT INTO tc VALUES (1, 100);")
        result = self._run("CREATE INDEX idx_tc ON tc (col);")
        self.assertIn("created", str(result).lower())

    def test_rapid_create_drop_create(self):
        """Rapid create/drop/create of same index."""
        self._run("CREATE TABLE td (id INT, col INT, PRIMARY KEY (id));")
        self._run("CREATE INDEX idx_rapid ON td (col);")
        self._run("DROP INDEX idx_rapid ON td;")
        result = self._run("CREATE INDEX idx_rapid ON td (col);")
        self.assertIn("created", str(result).lower())

    def test_double_drop_raises(self):
        """Double drop should raise NoSuchIndexError."""
        self._run("CREATE TABLE te (id INT, col INT, PRIMARY KEY (id));")
        self._run("CREATE INDEX idx_te ON te (col);")
        self._run("DROP INDEX idx_te ON te;")
        with self.assertRaises(NoSuchIndexError):
            self._run("DROP INDEX idx_te ON te;")

    def test_index_on_primary_key_column(self):
        """Creating index on PK column is allowed."""
        self._run("CREATE TABLE tf (id INT, name CHAR(10), PRIMARY KEY (id));")
        result = self._run("CREATE INDEX idx_pk ON tf (id);")
        self.assertIn("created", str(result).lower())

    def test_case_insensitive_index_names(self):
        """Index names are case-insensitive (stored lowercase)."""
        self._run("CREATE TABLE tg (id INT, col INT, PRIMARY KEY (id));")
        self._run("CREATE INDEX MyIndex ON tg (col);")
        # Should fail because myindex already exists
        with self.assertRaises(DuplicateIndexError):
            self._run("CREATE INDEX myindex ON tg (col);")

    def test_drop_index_case_insensitive(self):
        """Drop index with different case works."""
        self._run("CREATE TABLE th (id INT, col INT, PRIMARY KEY (id));")
        self._run("CREATE INDEX idx_th ON th (col);")
        result = self._run("DROP INDEX IDX_TH ON th;")
        self.assertIn("dropped", str(result).lower())

    def test_multiple_concurrent_indexes_same_table(self):
        """Many indexes on same table."""
        self._run("CREATE TABLE ti (id INT, a INT, b INT, c INT, d INT, PRIMARY KEY (id));")
        for col in ["a", "b", "c", "d"]:
            self._run(f"CREATE INDEX idx_{col} ON ti ({col});")
        table = self.dbms.explain_describe_desc("ti")
        self.assertEqual(len(table.index_definitions), 4)

    def test_delete_all_with_index(self):
        """Delete all records from indexed table."""
        self._run("CREATE TABLE tj (id INT, col INT, PRIMARY KEY (id));")
        self._run("CREATE INDEX idx_tj ON tj (col);")
        for i in range(5):
            self._run(f"INSERT INTO tj VALUES ({i}, {i * 10});")
        self._run("DELETE FROM tj;")
        im = self.dbms._get_index_manager("tj")
        self.assertEqual(len(im.search("col", 10)), 0)


if __name__ == "__main__":
    unittest.main()
