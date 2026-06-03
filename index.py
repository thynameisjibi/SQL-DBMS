from typing import Dict, Set, Any, Optional
from pathlib import Path
import pickle


class HashIndex:
    """Hash-based index for O(1) average-case lookups."""
    
    def __init__(self, column_name: str, ascending: bool = True):
        self.column_name = column_name
        self.ascending = ascending  # Stored for API compatibility, not used in hash index
        self.index: Dict[Any, Set[bytes]] = {}  # value -> set of record_keys
    
    def insert(self, value: Any, record_key: bytes):
        """Add value->key mapping. O(1) average."""
        if value not in self.index:
            self.index[value] = set()
        self.index[value].add(record_key)
    
    def delete(self, value: Any, record_key: bytes):
        """Remove value->key mapping. O(1) average."""
        if value in self.index:
            self.index[value].discard(record_key)
            if not self.index[value]:  # Clean up empty sets
                del self.index[value]
    
    def search(self, value: Any) -> Set[bytes]:
        """Return matching record_keys. O(1) average."""
        return self.index.get(value, set()).copy()
    
    def range_search(self, low: Any, high: Any) -> Set[bytes]:
        """Return keys in range [low, high]. O(n) - hash indexes are NOT optimized for ranges."""
        result = set()
        for value, keys in self.index.items():
            if low <= value <= high:
                result.update(keys)
        return result
    
    def __len__(self):
        """Return number of indexed unique values."""
        return len(self.index)


class IndexManager:
    """Manages indexes for a single table with disk persistence."""
    
    def __init__(self, table_name: str, db_dir: Path = None):
        self.table_name = table_name
        self.db_dir = db_dir or Path("./DB")
        self.indexes: Dict[str, HashIndex] = {}
        self.index_file = self.db_dir / f"{table_name}_indexes.idx"
        self.load_indexes()
    
    def create_index(self, column_name: str) -> bool:
        """Create index on column. Returns False if already exists."""
        if column_name in self.indexes:
            return False
        self.indexes[column_name] = HashIndex(column_name)
        self.save_indexes()
        return True
    
    def drop_index(self, column_name: str) -> bool:
        """Drop index on column. Returns False if doesn't exist."""
        if column_name not in self.indexes:
            return False
        del self.indexes[column_name]
        self.save_indexes()
        return True
    
    def get_index(self, column_name: str) -> Optional[HashIndex]:
        """Get index for column. Returns None if doesn't exist."""
        return self.indexes.get(column_name)
    
    def has_index(self, column_name: str) -> bool:
        """Check if index exists on column."""
        return column_name in self.indexes
    
    def insert(self, column_name: str, value: Any, record_key: bytes):
        """Insert into a specific column index if it exists."""
        if column_name in self.indexes:
            self.indexes[column_name].insert(value, record_key)
            self.save_indexes()
    
    def delete(self, column_name: str, value: Any, record_key: bytes):
        """Delete from a specific column index if it exists."""
        if column_name in self.indexes:
            self.indexes[column_name].delete(value, record_key)
            self.save_indexes()
    
    def search(self, column_name: str, value: Any) -> Set[bytes]:
        """Search a specific column index if it exists."""
        if column_name in self.indexes:
            return self.indexes[column_name].search(value)
        return set()
    
    def save_indexes(self):
        """Persist indexes to disk using pickle."""
        self.db_dir.mkdir(exist_ok=True)
        with open(self.index_file, 'wb') as f:
            pickle.dump(self.indexes, f)
    
    def load_indexes(self):
        """Load indexes from disk if they exist."""
        if self.index_file.exists():
            try:
                with open(self.index_file, 'rb') as f:
                    self.indexes = pickle.load(f)
            except (pickle.UnpicklingError, EOFError, KeyError, AttributeError):
                # Corrupted or incompatible index file - rebuild
                self.indexes = {}
    
    def rebuild_index(self, column_name: str, records: list):
        """Rebuild index from scratch using provided records.
        
        Args:
            column_name: Column to index
            records: List of (value, record_key) tuples
        """
        self.indexes[column_name] = HashIndex(column_name)
        for value, record_key in records:
            self.indexes[column_name].insert(value, record_key)
        self.save_indexes()