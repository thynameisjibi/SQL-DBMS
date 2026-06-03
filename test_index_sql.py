"""End-to-end SQL tests for CREATE INDEX / DROP INDEX."""
import unittest
from pathlib import Path
import shutil
from lark import Lark

from run import parse_query
from sql_transformer import SQLTransformer
from dbms import DBMS
from messages import *


class TestIndexSQL(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open('grammar.lark') as f:
            cls.sql_parser = Lark(f.read(), start="command", lexer="basic")

    def setUp(self):
        self.test_dir = Path("./test_db_sql_index")
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir(exist_ok=True)
        self.dbms = DBMS()
        self.dbms.db_dir = self.test_dir

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def _run_sql(self, sql):
        transformer = SQLTransformer()
        statement, table, record, tables, select_columns, where, index = parse_query(
            self.sql_parser, transformer, sql
        )
        if statement == "create index":
            return self.dbms.create_index(table["table_name"], index["index_name"], index["column_name"])
        elif statement == "drop index":
            return self.dbms.drop_index(table["table_name"], index["index_name"])
        elif statement == "create table":
            return self.dbms.create_table(table)
        elif statement == "insert":
            return self.dbms.insert(table, record)
        elif statement == "delete":
            result, extra = self.dbms.delete(table["table_name"], where)
            return result
        elif statement == "select":
            return self.dbms.select(tables, select_columns, where)
        elif statement == "drop table":
            return self.dbms.drop_table(table["table_name"])
        else:
            raise ValueError(f"Unknown statement: {statement}")

    def test_create_index_sql(self):
        self._run_sql("CREATE TABLE t (id INT, name CHAR(20), PRIMARY KEY (id));")
        result = self._run_sql("CREATE INDEX idx_name ON t (name);")
        self.assertIn("created", str(result).lower())

    def test_drop_index_sql(self):
        self._run_sql("CREATE TABLE t (id INT, name CHAR(20), PRIMARY KEY (id));")
        self._run_sql("CREATE INDEX idx_name ON t (name);")
        result = self._run_sql("DROP INDEX idx_name ON t;")
        self.assertIn("dropped", str(result).lower())

    def test_insert_updates_index(self):
        self._run_sql("CREATE TABLE t (id INT, name CHAR(20), PRIMARY KEY (id));")
        self._run_sql("CREATE INDEX idx_name ON t (name);")
        self._run_sql("INSERT INTO t VALUES (1, 'Alice');")
        self._run_sql("INSERT INTO t VALUES (2, 'Bob');")
        self._run_sql("INSERT INTO t VALUES (3, 'Alice');")
        im = self.dbms._get_index_manager("t")
        self.assertEqual(len(im.search("name", "Alice")), 2)

    def test_delete_updates_index(self):
        self._run_sql("CREATE TABLE t (id INT, name CHAR(20), PRIMARY KEY (id));")
        self._run_sql("CREATE INDEX idx_name ON t (name);")
        self._run_sql("INSERT INTO t VALUES (1, 'Alice');")
        self._run_sql("INSERT INTO t VALUES (2, 'Bob');")
        self._run_sql("DELETE FROM t WHERE id = 1;")
        im = self.dbms._get_index_manager("t")
        self.assertEqual(len(im.search("name", "Alice")), 0)
        self.assertEqual(len(im.search("name", "Bob")), 1)

    def test_range_search(self):
        self._run_sql("CREATE TABLE t (id INT, score INT, PRIMARY KEY (id));")
        self._run_sql("CREATE INDEX idx_score ON t (score);")
        for i in range(10):
            self._run_sql(f"INSERT INTO t VALUES ({i}, {i*10});")
        im = self.dbms._get_index_manager("t")
        result = im.range_search("score", 30, 60)
        self.assertEqual(len(result), 4)  # 30,40,50,60

    def test_persistence_across_restart(self):
        self._run_sql("CREATE TABLE t (id INT, tag CHAR(10), PRIMARY KEY (id));")
        self._run_sql("CREATE INDEX idx_tag ON t (tag);")
        self._run_sql("INSERT INTO t VALUES (1, 'red');")
        self._run_sql("INSERT INTO t VALUES (2, 'blue');")

        dbms2 = DBMS()
        dbms2.db_dir = self.test_dir
        im = dbms2._get_index_manager("t")
        self.assertTrue(im.has_index("tag"))
        self.assertEqual(len(im.search("tag", "red")), 1)

    def test_duplicate_index_error(self):
        self._run_sql("CREATE TABLE t (id INT, name CHAR(20), PRIMARY KEY (id));")
        self._run_sql("CREATE INDEX idx_name ON t (name);")
        with self.assertRaises(DuplicateIndexError):
            self._run_sql("CREATE INDEX idx_name ON t (name);")

    def test_index_on_nonexistent_column(self):
        self._run_sql("CREATE TABLE t (id INT, PRIMARY KEY (id));")
        with self.assertRaises(NonExistingColumnDefError):
            self._run_sql("CREATE INDEX idx ON t (nonexistent);")

    def test_index_on_nonexistent_table(self):
        with self.assertRaises(NoSuchTable):
            self._run_sql("CREATE INDEX idx ON nonexistent (col);")

    def test_drop_nonexistent_index(self):
        self._run_sql("CREATE TABLE t (id INT, PRIMARY KEY (id));")
        with self.assertRaises(NoSuchIndexError):
            self._run_sql("DROP INDEX idx ON t;")

    def test_drop_table_cleans_index(self):
        self._run_sql("CREATE TABLE t (id INT, name CHAR(20), PRIMARY KEY (id));")
        self._run_sql("CREATE INDEX idx_name ON t (name);")
        self._run_sql("INSERT INTO t VALUES (1, 'Alice');")
        self._run_sql("DROP TABLE t;")
        index_file = self.test_dir / "t_indexes.idx"
        self.assertFalse(index_file.exists())

    def test_column_already_indexed_error(self):
        """Test creating a different-named index on same column fails."""
        self._run_sql("CREATE TABLE t (id INT, name CHAR(20), PRIMARY KEY (id));")
        self._run_sql("CREATE INDEX idx1 ON t (name);")
        with self.assertRaises(IndexExistenceError):
            self._run_sql("CREATE INDEX idx2 ON t (name);")

    def test_describe_shows_index(self):
        """Test that EXPLAIN/DESCRIBE shows index information."""
        self._run_sql("CREATE TABLE t (id INT, name CHAR(20), PRIMARY KEY (id));")
        self._run_sql("CREATE INDEX idx_name ON t (name);")
        table = self.dbms.explain_describe_desc("t")
        self.assertIn("name", table.indexed_columns)

    def test_multiple_indexes_different_columns(self):
        """Test creating indexes on different columns."""
        self._run_sql("CREATE TABLE t (id INT, name CHAR(20), age INT, PRIMARY KEY (id));")
        self._run_sql("CREATE INDEX idx_name ON t (name);")
        self._run_sql("CREATE INDEX idx_age ON t (age);")
        self._run_sql("INSERT INTO t VALUES (1, 'Alice', 25);")
        im = self.dbms._get_index_manager("t")
        self.assertEqual(len(im.search("name", "Alice")), 1)
        self.assertEqual(len(im.search("age", 25)), 1)

    def test_index_name_scoped_per_table(self):
        """Test same index name can exist on different tables."""
        self._run_sql("CREATE TABLE t1 (id INT, name CHAR(20), PRIMARY KEY (id));")
        self._run_sql("CREATE TABLE t2 (id INT, name CHAR(20), PRIMARY KEY (id));")
        self._run_sql("CREATE INDEX idx_name ON t1 (name);")
        result = self._run_sql("CREATE INDEX idx_name ON t2 (name);")
        self.assertIn("created", str(result).lower())


if __name__ == "__main__":
    unittest.main()
