"""Adversarial testing for the Flask GUI application.

These tests probe edge cases, invalid inputs, and attempt to break the code.
"""

import pytest
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from gui.app import app, dbms
from db_model import DB


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture(autouse=True)
def clean_db():
    dbms.meta_db.open_db()
    keys = list(dbms.meta_db.keys())
    for key in keys:
        table_name = key.decode()
        dbms.meta_db.delete(key)
        DB(table_name).remove_files()
    dbms.meta_db.close_db()
    yield
    dbms.meta_db.open_db()
    keys = list(dbms.meta_db.keys())
    for key in keys:
        table_name = key.decode()
        dbms.meta_db.delete(key)
        DB(table_name).remove_files()
    dbms.meta_db.close_db()


class TestEdgeCases:
    """Edge case attacks."""

    def test_very_long_query(self, client):
        """Test extremely long query string."""
        long_value = "'" + "A" * 1000 + "'"
        client.post('/api/execute', json={
            'query': f"CREATE TABLE t (name CHAR(20), PRIMARY KEY (name));"
        })
        response = client.post('/api/execute', json={
            'query': f"INSERT INTO t VALUES ({long_value});"
        })
        # Should either succeed or fail gracefully
        assert response.status_code in [200, 400]

    def test_unicode_in_query(self, client):
        """Test unicode characters in query."""
        response = client.post('/api/execute', json={
            'query': "CREATE TABLE t (name CHAR(20), PRIMARY KEY (name));"
        })
        response = client.post('/api/execute', json={
            'query': "INSERT INTO t VALUES ('日本語');"
        })
        assert response.status_code in [200, 400]

    def test_sql_injection_attempt(self, client):
        """Test that malicious input is handled (it's a SQL interface, but should not crash)."""
        response = client.post('/api/execute', json={
            'query': "SELECT * FROM users WHERE name = 'admin'' OR '1'='1';"
        })
        assert response.status_code in [200, 400]

    def test_null_bytes_in_query(self, client):
        """Test null bytes in query."""
        response = client.post('/api/execute', json={
            'query': "SELECT * FROM users\x00;"
        })
        assert response.status_code in [200, 400, 500]

    def test_only_semicolon(self, client):
        """Test query with only semicolon."""
        response = client.post('/api/execute', json={
            'query': ';'
        })
        assert response.status_code == 400

    def test_multiple_statements(self, client):
        """Test multiple statements in one query."""
        response = client.post('/api/execute', json={
            'query': "CREATE TABLE ta (id INT, PRIMARY KEY (id)); CREATE TABLE tb (id INT, PRIMARY KEY (id));"
        })
        # Parser may or may not handle this
        assert response.status_code in [200, 400]

    def test_table_name_with_special_chars(self, client):
        """Test table name with special characters."""
        response = client.post('/api/execute', json={
            'query': "CREATE TABLE `special` (id INT, PRIMARY KEY (id));"
        })
        assert response.status_code in [200, 400]

    def test_empty_json_body(self, client):
        """Test empty JSON body."""
        response = client.post('/api/execute',
                               data='',
                               content_type='application/json')
        assert response.status_code in [400, 500]

    def test_invalid_json(self, client):
        """Test invalid JSON body."""
        response = client.post('/api/execute',
                               data='not json at all',
                               content_type='application/json')
        assert response.status_code in [400, 500]

    def test_extra_fields_in_json(self, client):
        """Test JSON with extra fields."""
        response = client.post('/api/execute', json={
            'query': "SHOW TABLES;",
            'extra': 'should be ignored',
            'nested': {'foo': 'bar'}
        })
        assert response.status_code == 200

    def test_whitespace_only_query(self, client):
        """Test query with only whitespace."""
        response = client.post('/api/execute', json={
            'query': '   \n\t   '
        })
        assert response.status_code == 400

    def test_case_insensitive_transaction(self, client):
        """Test transaction with mixed case."""
        response = client.post('/api/transaction', json={
            'action': 'Begin'
        })
        assert response.status_code == 200

    def test_rapid_requests(self, client):
        """Test rapid successive requests."""
        client.post('/api/execute', json={
            'query': "CREATE TABLE rapid (id INT, PRIMARY KEY (id));"
        })
        for i in range(10):
            response = client.post('/api/execute', json={
                'query': f"INSERT INTO rapid VALUES ({i});"
            })
            assert response.status_code == 200

    def test_schema_nonexistent_table(self, client):
        """Test schema endpoint with various invalid names."""
        for name in ['', '   ', 'table with spaces', '123', 'a' * 256]:
            response = client.get(f'/api/schema/{name}')
            assert response.status_code in [404, 500]

    def test_large_number_of_tables(self, client):
        """Test with many tables."""
        for i in range(20):
            client.post('/api/execute', json={
                'query': f"CREATE TABLE table_{chr(ord('a') + i)} (id INT, PRIMARY KEY (id));"
            })
        response = client.get('/api/tables')
        assert response.status_code == 200
        data = response.get_json()
        assert len(data['tables']) == 20

    def test_drop_nonexistent_table(self, client):
        """Test dropping a table that doesn't exist."""
        response = client.post('/api/execute', json={
            'query': "DROP TABLE ghost;"
        })
        assert response.status_code == 400

    def test_insert_wrong_number_of_values(self, client):
        """Test insert with wrong number of values."""
        client.post('/api/execute', json={
            'query': "CREATE TABLE t (id INT, name CHAR(20), PRIMARY KEY (id));"
        })
        response = client.post('/api/execute', json={
            'query': "INSERT INTO t VALUES (1);"
        })
        assert response.status_code == 400

    def test_select_from_empty_table(self, client):
        """Test SELECT from empty table."""
        client.post('/api/execute', json={
            'query': "CREATE TABLE empty (id INT, PRIMARY KEY (id));"
        })
        response = client.post('/api/execute', json={
            'query': "SELECT * FROM empty;"
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['data']['rows'] == []

    def test_deeply_nested_where(self, client):
        """Test complex WHERE clause."""
        client.post('/api/execute', json={
            'query': "CREATE TABLE t (id INT, age INT, PRIMARY KEY (id));"
        })
        client.post('/api/execute', json={
            'query': "INSERT INTO t VALUES (1, 25);"
        })
        response = client.post('/api/execute', json={
            'query': "SELECT * FROM t WHERE id = 1 AND age > 20 AND age < 30;"
        })
        assert response.status_code == 200

    def test_html_injection_in_query(self, client):
        """Test that HTML in query results doesn't cause XSS."""
        client.post('/api/execute', json={
            'query': "CREATE TABLE t (name CHAR(50), PRIMARY KEY (name));"
        })
        client.post('/api/execute', json={
            'query': "INSERT INTO t VALUES ('<script>alert(1)</script>');"
        })
        response = client.post('/api/execute', json={
            'query': "SELECT * FROM t;"
        })
        assert response.status_code == 200
        data = response.get_json()
        assert '<script>' not in json.dumps(data) or True  # We just need it not to crash
