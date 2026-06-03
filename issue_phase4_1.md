# Phase 4.1: Web-Based GUI

## Overview
Create a Flask-based web interface for the SQL DBMS that allows users to execute queries, view results, browse schema, and manage transactions through a browser.

## Current State
CLI-only interface via `run.py`. No web interface exists.

## Tasks

### 1. Create GUI Module Structure
```
gui/
├── app.py              # Flask application
├── templates/
│   └── index.html      # Single-page interface
├── static/
│   ├── style.css       # Styling
│   └── app.js          # Client-side logic
└── requirements.txt    # Flask dependencies
```

### 2. Flask Application (gui/app.py)

#### Main Routes
```python
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from dbms import DBMS

app = Flask(__name__)
CORS(app)
dbms = DBMS()  # Single shared instance

@app.route('/')
def index():
    """Render main interface."""
    return render_template('index.html')

@app.route('/api/execute', methods=['POST'])
def execute_query():
    """Execute SQL query and return results."""
    query = request.json.get('query', '').strip()
    try:
        result = execute_single_query(dbms, query)
        return jsonify({'success': True, 'data': result})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 400

@app.route('/api/tables', methods=['GET'])
def get_tables():
    """Get list of all tables."""
    tables = dbms.show_tables()
    return jsonify({'success': True, 'tables': parse_tables(tables)})

@app.route('/api/schema/<table_name>', methods=['GET'])
def get_schema(table_name):
    """Get schema for a table."""
    try:
        table = dbms.explain_describe_desc(table_name)
        return jsonify({'success': True, 'schema': str(table)})
    except NoSuchTable:
        return jsonify({'success': False, 'message': 'Table not found'}), 404

@app.route('/api/transaction', methods=['POST'])
def transaction_action():
    """Handle BEGIN/COMMIT/ROLLBACK."""
    action = request.json.get('action', '').upper()
    if action == 'BEGIN':
        result = dbms.begin()
    elif action == 'COMMIT':
        result = dbms.commit()
    elif action == 'ROLLBACK':
        result = dbms.rollback()
    return jsonify({'success': True, 'message': result})

@app.route('/api/status', methods=['GET'])
def get_status():
    """Get transaction status."""
    return jsonify({
        'auto_commit': dbms.auto_commit,
        'has_active_transaction': dbms.current_transaction is not None
    })
```

### 3. HTML Interface (templates/index.html)

#### Key Sections
- **Query Editor:** Textarea with syntax highlighting (optional: CodeMirror)
- **Results Panel:** Tabular display of query results
- **Schema Browser:** List of tables with expandable schema details
- **Transaction Controls:** BEGIN/COMMIT/ROLLBACK buttons
- **Status Bar:** Connection status and transaction state

### 4. Client-Side JavaScript (static/app.js)

#### Key Functions
```javascript
// Execute query
async function executeQuery() {
    const response = await fetch('/api/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
    });
    const data = await response.json();
    displayResults(data);
}

// Load tables
async function loadTables() {
    const response = await fetch('/api/tables');
    const data = await response.json();
    displayTables(data.tables);
}

// Transaction actions
async function transactionAction(action) {
    await fetch('/api/transaction', {
        method: 'POST',
        body: JSON.stringify({ action })
    });
    updateTransactionStatus();
}

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        executeQuery();  // Ctrl+Enter to execute
    }
});
```

### 5. CSS Styling (static/style.css)

#### Design Requirements
- Clean, modern interface
- Responsive layout (works on desktop and tablet)
- Clear visual distinction between success/error results
- Monospace font for query editor and results
- Color-coded transaction status (green=auto-commit, orange=active transaction)

### 6. Requirements File (requirements.txt)
```
flask==3.0.0
flask-cors==4.0.0
```

## Acceptance Criteria
- [ ] Web UI loads at http://localhost:5000
- [ ] Query editor accepts SQL input
- [ ] Results displayed in tabular format
- [ ] Errors displayed with clear messages
- [ ] Schema browser shows tables and columns
- [ ] Transaction controls (BEGIN/COMMIT/ROLLBACK) work
- [ ] Status bar shows transaction state
- [ ] Keyboard shortcut (Ctrl+Enter) executes query
- [ ] Responsive design works on different screen sizes

## Test Cases
```sql
-- Test all SQL commands through UI
CREATE TABLE test (id int, name char(50));
INSERT INTO test VALUES (1, 'Test');
SELECT * FROM test;
UPDATE test SET name = 'Updated' WHERE id = 1;
DELETE FROM test WHERE id = 1;
DROP TABLE test;

-- Test transactions
BEGIN;
INSERT INTO test VALUES (1, 'Transaction Test');
ROLLBACK;
-- Row should not exist

-- Test error handling
SELECT * FROM nonexistent_table;  -- Should show error
INSERT INTO test VALUES ('not_an_int', 'Test');  -- Should show type error
```

## Files to Create
- **NEW:** `gui/app.py`
- **NEW:** `gui/templates/index.html`
- **NEW:** `gui/static/style.css`
- **NEW:** `gui/static/app.js`
- **NEW:** `gui/requirements.txt`

## Dependencies
- **Blocked by:** Phase 1 (all SQL commands must work)
- **Blocked by:** Phase 3 (transaction support for UI controls)

## Implementation Notes

### Running the GUI
```bash
cd gui
pip install -r requirements.txt
python app.py
# Open http://localhost:5000
```

### Security Considerations
- **Development only:** Flask debug mode enabled
- **No authentication:** Anyone with access can run arbitrary SQL
- **CORS enabled:** Allows cross-origin requests (for development)
- **Production deployment:** Requires authentication, rate limiting, HTTPS

### Error Handling
The UI should display helpful error messages:
```javascript
const ERROR_SUGGESTIONS = {
    'NoSuchTable': 'Table does not exist. Use SHOW TABLES to see available tables.',
    'ActiveTransactionError': 'A transaction is already active. Use COMMIT or ROLLBACK first.',
    'NoActiveTransactionError': 'No active transaction. Use BEGIN to start one.',
    'InsertTypeMismatchError': 'Value type does not match column type.',
    'SyntaxError': 'Check your SQL syntax. Make sure to end with a semicolon.'
};
```

### Live Query Preview (Bonus)
For SELECT queries, implement debounced auto-execution:
```javascript
// Auto-execute SELECT queries 1 second after typing stops
document.getElementById('query-input').addEventListener('input', (e) => {
    const query = e.target.value.trim();
    if (query.toUpperCase().startsWith('SELECT') && query.endsWith(';')) {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => executeQuerySilent(query), 1000);
    }
});
```

## References
- IMPLEMENTATION_PLAN.md Phase 4.1
- Flask documentation: https://flask.palletsprojects.com/
