"""Integration tests for DBMS with Hash Index support."""
import unittest
from pathlib import Path
import shutil
import sys

from dbms import DBMS
from db_model import Table, Record, DB, MetaDB
from messages import *


class TestDBMSIndexIntegration(unittest.TestCase):
    """Test DBMS integration with hash indexes."""
    
    @classmethod
    def setUpClass(cls):
        cls.test_db_dir = Path("./test_db_integration")
        cls.original_db_dir = Path("./DB")
        # We'll use a temporary DB directory for each test
        
    def setUp(self):
        # Clean up and prepare test environment
        if self.test_db_dir.exists():
            shutil.rmtree(self.test_db_dir)
        self.test_db_dir.mkdir(exist_ok=True)
        
        # Temporarily change DB directory for testing
        self.dbms = DBMS()
        self.dbms.db_dir = self.test_db_dir
        self.dbms.db_dir.mkdir(exist_ok=True)
        
    def tearDown(self):
        # Clean up test DB
        if self.test_db_dir.exists():
            shutil.rmtree(self.test_db_dir, ignore_errors=True)
    
    def test_create_index_and_metadata(self):
        """Test creating an index updates table metadata."""
        # Create table
        table_dict = {
            "table_name": "employees",
            "column_list": [("id", "int"), ("name", "char(20)")],
            "not_null_key_set": {"id"},
            "primary_key_list": [("id",)],
            "foreign_key_dict": {}
        }
        self.dbms.create_table(table_dict)
        
        # Insert some data
        self.dbms.insert({"table_name": "employees", "column_name_list": None}, [1, "Alice"])
        self.dbms.insert({"table_name": "employees", "column_name_list": None}, [2, "Bob"])
        
        # Create index
        result = self.dbms.create_index("employees", "idx_name", "name")
        self.assertIn("created", str(result).lower())
        
        # Verify metadata was updated
        table = self.dbms.explain_describe_desc("employees")
        self.assertTrue(table.is_indexed("name"))
        self.assertFalse(table.is_indexed("id"))
    
    def test_drop_index_and_metadata(self):
        """Test dropping an index updates table metadata."""
        # Create table and index
        table_dict = {
            "table_name": "products",
            "column_list": [("sku", "char(10)"), ("price", "int")],
            "not_null_key_set": {"sku"},
            "primary_key_list": [("sku",)],
            "foreign_key_dict": {}
        }
        self.dbms.create_table(table_dict)
        self.dbms.insert({"table_name": "products", "column_name_list": None}, ["ABC123", 100])
        self.dbms.create_index("products", "idx_price", "price")
        
        # Verify index exists
        table = self.dbms.explain_describe_desc("products")
        self.assertTrue(table.is_indexed("price"))
        
        # Drop index
        result = self.dbms.drop_index("products", "idx_price")
        self.assertIn("dropped", str(result).lower())
        
        # Verify metadata was updated
        table = self.dbms.explain_describe_desc("products")
        self.assertFalse(table.is_indexed("price"))
    
    def test_insert_updates_index(self):
        """Test that inserting records updates the index."""
        # Create table and index
        table_dict = {
            "table_name": "users",
            "column_list": [("id", "int"), ("email", "char(50)")],
            "not_null_key_set": {"id", "email"},
            "primary_key_list": [("id",)],
            "foreign_key_dict": {}
        }
        self.dbms.create_table(table_dict)
        self.dbms.create_index("users", "idx_email", "email")
        
        # Insert records
        self.dbms.insert({"table_name": "users", "column_name_list": None}, [1, "alice@test.com"])
        self.dbms.insert({"table_name": "users", "column_name_list": None}, [2, "bob@test.com"])
        self.dbms.insert({"table_name": "users", "column_name_list": None}, [3, "alice@test.com"])  # Duplicate email
        
        # Verify index entries
        index_manager = self.dbms._get_index_manager("users")
        result = index_manager.search("email", "alice@test.com")
        self.assertEqual(len(result), 2)  # Two users with same email
        
        result = index_manager.search("email", "bob@test.com")
        self.assertEqual(len(result), 1)
        
        result = index_manager.search("email", "unknown@test.com")
        self.assertEqual(len(result), 0)
    
    def test_delete_updates_index(self):
        """Test that deleting records updates the index."""
        # Create table and index
        table_dict = {
            "table_name": "inventory",
            "column_list": [("item_id", "int"), ("category", "char(20)")],
            "not_null_key_set": {"item_id"},
            "primary_key_list": [("item_id",)],
            "foreign_key_dict": {}
        }
        self.dbms.create_table(table_dict)
        self.dbms.create_index("inventory", "idx_category", "category")
        
        # Insert records
        self.dbms.insert({"table_name": "inventory", "column_name_list": None}, [1, "Electronics"])
        self.dbms.insert({"table_name": "inventory", "column_name_list": None}, [2, "Electronics"])
        self.dbms.insert({"table_name": "inventory", "column_name_list": None}, [3, "Clothing"])
        
        # Verify initial index state
        index_manager = self.dbms._get_index_manager("inventory")
        self.assertEqual(len(index_manager.search("category", "Electronics")), 2)
        
        # Delete one Electronics item
        self.dbms.delete("inventory", None)  # Delete all (where_clause=None is handled as True)
        
        # Verify index is updated
        self.assertEqual(len(index_manager.search("category", "Electronics")), 0)
        self.assertEqual(len(index_manager.search("category", "Clothing")), 0)
    
    def test_create_index_rebuilds_from_existing_data(self):
        """Test creating an index on existing data populates the index."""
        # Create table and insert data
        table_dict = {
            "table_name": "orders",
            "column_list": [("order_id", "int"), ("status", "char(10)")],
            "not_null_key_set": {"order_id"},
            "primary_key_list": [("order_id",)],
            "foreign_key_dict": {}
        }
        self.dbms.create_table(table_dict)
        self.dbms.insert({"table_name": "orders", "column_name_list": None}, [1, "pending"])
        self.dbms.insert({"table_name": "orders", "column_name_list": None}, [2, "shipped"])
        self.dbms.insert({"table_name": "orders", "column_name_list": None}, [3, "pending"])
        
        # Create index on existing data
        self.dbms.create_index("orders", "idx_status", "status")
        
        # Verify index was populated
        index_manager = self.dbms._get_index_manager("orders")
        self.assertEqual(len(index_manager.search("status", "pending")), 2)
        self.assertEqual(len(index_manager.search("status", "shipped")), 1)
    
    def test_create_index_on_nonexistent_column(self):
        """Test creating an index on a non-existent column raises error."""
        table_dict = {
            "table_name": "items",
            "column_list": [("id", "int")],
            "not_null_key_set": {"id"},
            "primary_key_list": [("id",)],
            "foreign_key_dict": {}
        }
        self.dbms.create_table(table_dict)
        
        with self.assertRaises(NonExistingColumnDefError):
            self.dbms.create_index("items", "idx_bad", "nonexistent_column")
    
    def test_create_index_on_nonexistent_table(self):
        """Test creating an index on a non-existent table raises error."""
        with self.assertRaises(NoSuchTable):
            self.dbms.create_index("nonexistent_table", "idx_col", "column1")
    
    def test_drop_table_cleans_up_index(self):
        """Test that dropping a table removes its index file."""
        table_dict = {
            "table_name": "temp_table",
            "column_list": [("id", "int"), ("value", "char(10)")],
            "not_null_key_set": {"id"},
            "primary_key_list": [("id",)],
            "foreign_key_dict": {}
        }
        self.dbms.create_table(table_dict)
        self.dbms.insert({"table_name": "temp_table", "column_name_list": None}, [1, "A"])
        self.dbms.create_index("temp_table", "idx_value", "value")
        
        # Verify index file exists
        index_file = self.test_db_dir / "temp_table_indexes.idx"
        self.assertTrue(index_file.exists())
        
        # Drop table
        self.dbms.drop_table("temp_table")
        
        # Verify index file is removed
        self.assertFalse(index_file.exists())
    
    def test_duplicate_index_creation_fails(self):
        """Test creating the same index twice fails."""
        table_dict = {
            "table_name": "test_dup",
            "column_list": [("id", "int"), ("col", "char(10)")],
            "not_null_key_set": {"id"},
            "primary_key_list": [("id",)],
            "foreign_key_dict": {}
        }
        self.dbms.create_table(table_dict)
        self.dbms.create_index("test_dup", "idx_col", "col")
        
        with self.assertRaises(DuplicateIndexError) as ctx:
            self.dbms.create_index("test_dup", "idx_col", "col")
        self.assertIn("already exists", str(ctx.exception))
    
    def test_drop_nonexistent_index_fails(self):
        """Test dropping a non-existent index fails."""
        table_dict = {
            "table_name": "test_drop",
            "column_list": [("id", "int")],
            "not_null_key_set": {"id"},
            "primary_key_list": [("id",)],
            "foreign_key_dict": {}
        }
        self.dbms.create_table(table_dict)
        
        with self.assertRaises(NoSuchIndexError) as ctx:
            self.dbms.drop_index("test_drop", "nonexistent")
        self.assertIn("does not exist", str(ctx.exception))
    
    def test_index_persists_across_dbms_instances(self):
        """Test that indexes persist when DBMS is restarted."""
        # Create table, data, and index
        table_dict = {
            "table_name": "persistent",
            "column_list": [("id", "int"), ("tag", "char(10)")],
            "not_null_key_set": {"id"},
            "primary_key_list": [("id",)],
            "foreign_key_dict": {}
        }
        self.dbms.create_table(table_dict)
        self.dbms.insert({"table_name": "persistent", "column_name_list": None}, [1, "red"])
        self.dbms.insert({"table_name": "persistent", "column_name_list": None}, [2, "blue"])
        self.dbms.create_index("persistent", "idx_tag", "tag")
        
        # Create new DBMS instance (simulates restart)
        dbms2 = DBMS()
        dbms2.db_dir = self.test_db_dir
        dbms2.db_dir.mkdir(exist_ok=True)
        
        # Verify index is loaded
        index_manager = dbms2._get_index_manager("persistent")
        self.assertTrue(index_manager.has_index("tag"))
        self.assertEqual(len(index_manager.search("tag", "red")), 1)
        self.assertEqual(len(index_manager.search("tag", "blue")), 1)


if __name__ == "__main__":
    unittest.main()