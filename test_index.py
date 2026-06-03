import unittest
from pathlib import Path
import shutil
import sys

from index import HashIndex, IndexManager


class TestHashIndex(unittest.TestCase):
    
    def setUp(self):
        self.index = HashIndex("test_column")
    
    def test_insert_and_search(self):
        """Test basic insert and search functionality."""
        self.index.insert(42, b"key1")
        result = self.index.search(42)
        self.assertEqual(result, {b"key1"})
    
    def test_multiple_values_same_key(self):
        """Test that multiple records can have the same indexed value."""
        self.index.insert(42, b"key1")
        self.index.insert(42, b"key2")
        self.index.insert(42, b"key3")
        result = self.index.search(42)
        self.assertEqual(result, {b"key1", b"key2", b"key3"})
    
    def test_delete_single_entry(self):
        """Test deleting a single entry from the index."""
        self.index.insert(42, b"key1")
        self.index.delete(42, b"key1")
        result = self.index.search(42)
        self.assertEqual(result, set())
    
    def test_delete_one_of_many(self):
        """Test deleting one entry when multiple exist for same value."""
        self.index.insert(42, b"key1")
        self.index.insert(42, b"key2")
        self.index.delete(42, b"key1")
        result = self.index.search(42)
        self.assertEqual(result, {b"key2"})
    
    def test_delete_nonexistent(self):
        """Test deleting a non-existent entry doesn't raise an error."""
        self.index.delete(42, b"nonexistent")
        result = self.index.search(42)
        self.assertEqual(result, set())
    
    def test_search_nonexistent_value(self):
        """Test searching for a value that doesn't exist returns empty set."""
        result = self.index.search(999)
        self.assertEqual(result, set())
    
    def test_range_search(self):
        """Test range search functionality."""
        for i in range(10):
            self.index.insert(i, f"key{i}".encode())
        result = self.index.range_search(3, 6)
        self.assertEqual(len(result), 4)  # keys for values 3, 4, 5, 6
        self.assertEqual(result, {b"key3", b"key4", b"key5", b"key6"})
    
    def test_range_search_no_match(self):
        """Test range search with no matching values."""
        for i in range(5):
            self.index.insert(i, f"key{i}".encode())
        result = self.index.range_search(10, 20)
        self.assertEqual(result, set())
    
    def test_null_value_handling(self):
        """Test that NULL values can be indexed."""
        self.index.insert(None, b"key1")
        result = self.index.search(None)
        self.assertEqual(result, {b"key1"})
    
    def test_string_values(self):
        """Test indexing string values."""
        self.index.insert("alice", b"key1")
        self.index.insert("bob", b"key2")
        result = self.index.search("alice")
        self.assertEqual(result, {b"key1"})
    
    def test_len(self):
        """Test the __len__ method returns correct count of unique values."""
        self.assertEqual(len(self.index), 0)
        self.index.insert(1, b"key1")
        self.index.insert(2, b"key2")
        self.index.insert(1, b"key3")  # Same value as first
        self.assertEqual(len(self.index), 2)  # Two unique values


class TestIndexManager(unittest.TestCase):
    
    def setUp(self):
        self.test_dir = Path("./test_db_index")
        # Clean up any leftover test directory
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir(exist_ok=True)
        self.manager = IndexManager("test_table", self.test_dir)
    
    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_create_index(self):
        """Test creating a new index."""
        result = self.manager.create_index("column1")
        self.assertTrue(result)
        self.assertTrue(self.manager.has_index("column1"))
    
    def test_create_duplicate_index(self):
        """Test creating an index that already exists returns False."""
        self.manager.create_index("column1")
        result = self.manager.create_index("column1")
        self.assertFalse(result)
    
    def test_drop_existing_index(self):
        """Test dropping an existing index."""
        self.manager.create_index("column1")
        result = self.manager.drop_index("column1")
        self.assertTrue(result)
        self.assertFalse(self.manager.has_index("column1"))
    
    def test_drop_nonexistent_index(self):
        """Test dropping an index that doesn't exist returns False."""
        result = self.manager.drop_index("column1")
        self.assertFalse(result)
    
    def test_get_index(self):
        """Test retrieving an index object."""
        self.manager.create_index("column1")
        index = self.manager.get_index("column1")
        self.assertIsNotNone(index)
        self.assertIsInstance(index, HashIndex)
        self.assertEqual(index.column_name, "column1")
    
    def test_get_nonexistent_index(self):
        """Test retrieving an index that doesn't exist returns None."""
        index = self.manager.get_index("column1")
        self.assertIsNone(index)
    
    def test_insert_into_index(self):
        """Test inserting data into an index."""
        self.manager.create_index("column1")
        self.manager.insert("column1", 42, b"key1")
        result = self.manager.search("column1", 42)
        self.assertEqual(result, {b"key1"})
    
    def test_delete_from_index(self):
        """Test deleting data from an index."""
        self.manager.create_index("column1")
        self.manager.insert("column1", 42, b"key1")
        self.manager.delete("column1", 42, b"key1")
        result = self.manager.search("column1", 42)
        self.assertEqual(result, set())
    
    def test_persistence(self):
        """Test that indexes persist to disk and can be reloaded."""
        self.manager.create_index("column1")
        self.manager.insert("column1", 42, b"key1")
        self.manager.insert("column1", 43, b"key2")
        
        # Create new manager pointing to same directory (simulates restart)
        manager2 = IndexManager("test_table", self.test_dir)
        self.assertTrue(manager2.has_index("column1"))
        result = manager2.search("column1", 42)
        self.assertEqual(result, {b"key1"})
        result = manager2.search("column1", 43)
        self.assertEqual(result, {b"key2"})
    
    def test_rebuild_index(self):
        """Test rebuilding an index from existing records."""
        self.manager.create_index("column1")
        records = [
            (10, b"key1"),
            (20, b"key2"),
            (10, b"key3"),  # Duplicate value
        ]
        self.manager.rebuild_index("column1", records)
        result = self.manager.search("column1", 10)
        self.assertEqual(result, {b"key1", b"key3"})
        result = self.manager.search("column1", 20)
        self.assertEqual(result, {b"key2"})
    
    def test_insert_without_index(self):
        """Test insert doesn't fail when no index exists for column."""
        # Should not raise any exception
        self.manager.insert("nonexistent_column", 42, b"key1")
    
    def test_delete_without_index(self):
        """Test delete doesn't fail when no index exists for column."""
        # Should not raise any exception
        self.manager.delete("nonexistent_column", 42, b"key1")
    
    def test_corrupted_index_recovery(self):
        """Test graceful recovery from corrupted index file."""
        # Create a corrupted index file
        index_file = self.test_dir / "test_table_indexes.idx"
        with open(index_file, 'wb') as f:
            f.write(b"this is not valid pickle data")
        
        # Creating a new manager should handle the corrupted file
        manager = IndexManager("test_table", self.test_dir)
        self.assertEqual(len(manager.indexes), 0)  # Should start fresh


class TestIndexManagerMultipleIndexes(unittest.TestCase):
    
    def setUp(self):
        self.test_dir = Path("./test_db_multi")
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir(exist_ok=True)
        self.manager = IndexManager("test_table", self.test_dir)
    
    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_multiple_indexes(self):
        """Test managing multiple indexes on different columns."""
        self.manager.create_index("column1")
        self.manager.create_index("column2")
        
        self.manager.insert("column1", 42, b"key1")
        self.manager.insert("column2", "alice", b"key1")
        
        result1 = self.manager.search("column1", 42)
        result2 = self.manager.search("column2", "alice")
        
        self.assertEqual(result1, {b"key1"})
        self.assertEqual(result2, {b"key1"})
    
    def test_multiple_indexes_persistence(self):
        """Test that all indexes persist correctly."""
        self.manager.create_index("column1")
        self.manager.create_index("column2")
        self.manager.insert("column1", 42, b"key1")
        self.manager.insert("column2", "alice", b"key1")
        
        # Simulate restart
        manager2 = IndexManager("test_table", self.test_dir)
        self.assertTrue(manager2.has_index("column1"))
        self.assertTrue(manager2.has_index("column2"))
        self.assertEqual(manager2.search("column1", 42), {b"key1"})
        self.assertEqual(manager2.search("column2", "alice"), {b"key1"})


if __name__ == "__main__":
    unittest.main()