"""Tests for the Flask GUI application."""

import pytest
import sys
import os

# Add parent directory to path to import dbms modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from gui.app import app, dbms
from db_model import DB


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture(autouse=True)
def clean_db():
    """Clean up the database before each test."""
    # Clear any existing tables
    dbms.meta_db.open_db()
    keys = list(dbms.meta_db.keys())
    for key in keys:
        table_name = key.decode()
        dbms.meta_db.delete(key)
        DB(table_name).remove_files()
    dbms.meta_db.close_db()
    yield
    # Clean up after test
    dbms.meta_db.open_db()
    keys = list(dbms.meta_db.keys())
    for key in keys:
        table_name = key.decode()
        dbms.meta_db.delete(key)
        DB(table_name).remove_files()
    dbms.meta_db.close_db()


class TestIndexRoute:
    """Tests for the main page route."""

    def test_index_returns_html(self, client):
        """Test that the index route returns HTML."""
        response = client.get('/')
        assert response.status_code == 200
        assert b'<!DOCTYPE html>' in response.data
        assert b'SQL DBMS' in response.data


class TestExecuteRoute:
    """Tests for the /api/execute endpoint."""

    def test_create_table(self, client):
        """Test executing a CREATE TABLE query."""
        response = client.post('/api/execute', json={
            'query': "CREATE TABLE users (id INT, name CHAR(20), PRIMARY KEY (id));"
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'users' in data['data']['message']

    def test_insert_and_select(self, client):
        """Test INSERT and SELECT queries."""
        # Create table
        client.post('/api/execute', json={
            'query': "CREATE TABLE users (id INT, name CHAR(20), PRIMARY KEY (id));"
        })
        # Insert record
        response = client.post('/api/execute', json={
            'query': "INSERT INTO users VALUES (1, 'John');"
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

        # Select records
        response = client.post('/api/execute', json={
            'query': "SELECT * FROM users;"
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['data']['statement'] == 'select'
        assert 'id' in data['data']['headers']
        assert 'name' in data['data']['headers']
        assert len(data['data']['rows']) == 1
        assert data['data']['rows'][0]['id'] == 1
        assert data['data']['rows'][0]['name'] == 'John'

    def test_empty_query(self, client):
        """Test that empty query returns appropriate error."""
        response = client.post('/api/execute', json={
            'query': ''
        })
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False

    def test_missing_query_field(self, client):
        """Test that missing query field returns error."""
        response = client.post('/api/execute', json={})
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False

    def test_syntax_error(self, client):
        """Test that malformed SQL returns syntax error."""
        response = client.post('/api/execute', json={
            'query': "SELECT FROM;"
        })
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'syntax' in data['message'].lower()

    def test_no_such_table(self, client):
        """Test querying non-existent table returns error."""
        response = client.post('/api/execute', json={
            'query': "SELECT * FROM nonexistent;"
        })
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'does not exist' in data['message'].lower()

    def test_show_tables(self, client):
        """Test SHOW TABLES query."""
        # Create a table first
        client.post('/api/execute', json={
            'query': "CREATE TABLE test (id INT, PRIMARY KEY (id));"
        })
        response = client.post('/api/execute', json={
            'query': "SHOW TABLES;"
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'test' in data['data']['message']

    def test_describe_table(self, client):
        """Test DESCRIBE TABLE query."""
        client.post('/api/execute', json={
            'query': "CREATE TABLE users (id INT, name CHAR(20), PRIMARY KEY (id));"
        })
        response = client.post('/api/execute', json={
            'query': "DESC users;"
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'users' in data['data']['message']

    def test_delete_query(self, client):
        """Test DELETE query."""
        client.post('/api/execute', json={
            'query': "CREATE TABLE users (id INT, name CHAR(20), PRIMARY KEY (id));"
        })
        client.post('/api/execute', json={
            'query': "INSERT INTO users VALUES (1, 'John');"
        })
        response = client.post('/api/execute', json={
            'query': "DELETE FROM users WHERE id = 1;"
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'deleted' in data['data']['message'].lower()

    def test_drop_table(self, client):
        """Test DROP TABLE query."""
        client.post('/api/execute', json={
            'query': "CREATE TABLE users (id INT, name CHAR(20), PRIMARY KEY (id));"
        })
        response = client.post('/api/execute', json={
            'query': "DROP TABLE users;"
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'dropped' in data['data']['message'].lower()


class TestTablesRoute:
    """Tests for the /api/tables endpoint."""

    def test_get_tables_empty(self, client):
        """Test getting tables when database is empty."""
        response = client.get('/api/tables')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['tables'] == []

    def test_get_tables_with_data(self, client):
        """Test getting tables after creating some."""
        client.post('/api/execute', json={
            'query': "CREATE TABLE users (id INT, PRIMARY KEY (id));"
        })
        client.post('/api/execute', json={
            'query': "CREATE TABLE orders (id INT, PRIMARY KEY (id));"
        })
        response = client.get('/api/tables')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'users' in data['tables']
        assert 'orders' in data['tables']


class TestSchemaRoute:
    """Tests for the /api/schema/<table_name> endpoint."""

    def test_get_schema_success(self, client):
        """Test getting schema for existing table."""
        client.post('/api/execute', json={
            'query': "CREATE TABLE users (id INT, name CHAR(20), PRIMARY KEY (id));"
        })
        response = client.get('/api/schema/users')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'schema' in data['data']
        assert 'users' in data['data']['schema']

    def test_get_schema_not_found(self, client):
        """Test getting schema for non-existent table."""
        response = client.get('/api/schema/nonexistent')
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False
        assert 'not found' in data['message'].lower()


class TestTransactionRoute:
    """Tests for the /api/transaction endpoint."""

    def test_begin_transaction(self, client):
        """Test BEGIN TRANSACTION."""
        response = client.post('/api/transaction', json={
            'action': 'BEGIN'
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    def test_commit_transaction(self, client):
        """Test COMMIT TRANSACTION."""
        response = client.post('/api/transaction', json={
            'action': 'COMMIT'
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    def test_rollback_transaction(self, client):
        """Test ROLLBACK TRANSACTION."""
        response = client.post('/api/transaction', json={
            'action': 'ROLLBACK'
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

    def test_invalid_transaction_action(self, client):
        """Test invalid transaction action."""
        response = client.post('/api/transaction', json={
            'action': 'INVALID'
        })
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False

    def test_missing_action_field(self, client):
        """Test missing action field returns error."""
        response = client.post('/api/transaction', json={})
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False


class TestErrorHandling:
    """Tests for error handling and edge cases."""

    def test_method_not_allowed_on_execute(self, client):
        """Test that GET is not allowed on /api/execute."""
        response = client.get('/api/execute')
        assert response.status_code == 405

    def test_content_type_json_required(self, client):
        """Test that non-JSON content type is handled."""
        response = client.post('/api/execute', data='not json')
        assert response.status_code in [400, 415, 500]

    def test_special_characters_in_query(self, client):
        """Test queries with special characters."""
        response = client.post('/api/execute', json={
            'query': "CREATE TABLE test (name CHAR(20), PRIMARY KEY (name));"
        })
        assert response.status_code == 200
        response = client.post('/api/execute', json={
            'query': "INSERT INTO test VALUES ('Hello, World!');"
        })
        assert response.status_code == 200
