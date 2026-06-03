/**
 * SQL DBMS Web GUI - Client-Side JavaScript
 */

// API Base URL (relative to current host)
const API_BASE = '/api';

// DOM Elements
const queryInput = document.getElementById('query-input');
const btnExecute = document.getElementById('btn-execute');
const btnClear = document.getElementById('btn-clear');
const btnFormat = document.getElementById('btn-format');
const btnBegin = document.getElementById('btn-begin');
const btnCommit = document.getElementById('btn-commit');
const btnRollback = document.getElementById('btn-rollback');
const resultsContent = document.getElementById('results-content');
const resultsMeta = document.getElementById('results-meta');
const tableListContainer = document.getElementById('table-list-container');
const transactionStatus = document.getElementById('transaction-status');
const messageArea = document.getElementById('message-area');

// State
let isTransactionActive = false;
let currentQuery = '';

// Initialize
 document.addEventListener('DOMContentLoaded', () => {
    loadTables();
    setupEventListeners();
});

/**
 * Setup all event listeners
 */
function setupEventListeners() {
    btnExecute.addEventListener('click', executeQuery);
    btnClear.addEventListener('click', clearEditor);
    btnFormat.addEventListener('click', formatQuery);

    btnBegin.addEventListener('click', () => handleTransaction('BEGIN'));
    btnCommit.addEventListener('click', () => handleTransaction('COMMIT'));
    btnRollback.addEventListener('click', () => handleTransaction('ROLLBACK'));

    queryInput.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key === 'Enter') {
            e.preventDefault();
            executeQuery();
        }
    });
}

/**
 * Execute SQL query
 */
async function executeQuery() {
    const query = queryInput.value.trim();
    if (!query) {
        showMessage('Please enter a query', 'warning');
        return;
    }

    setLoading(true);
    currentQuery = query;

    try {
        const response = await fetch(`${API_BASE}/execute`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ query })
        });

        const data = await response.json();

        if (data.success) {
            displayResults(data.data);
            showMessage(data.data.message || 'Query executed successfully', 'success');

            // Refresh tables list after DDL operations
            const statement = data.data.statement;
            if (['create_table', 'drop_table'].includes(statement)) {
                loadTables();
            }
        } else {
            displayError(data.message, data.error_type);
            showMessage(data.message, 'error');
        }
    } catch (error) {
        displayError('Network error: ' + error.message);
        showMessage('Network error: ' + error.message, 'error');
    } finally {
        setLoading(false);
    }
}

/**
 * Display query results
 */
function displayResults(data) {
    const statement = data.statement;

    if (statement === 'select') {
        displayTableResults(data.headers, data.rows);
        resultsMeta.textContent = `${data.rows.length} row(s) returned`;
    } else if (statement === 'show_tables') {
        displayRawOutput(data.message);
        resultsMeta.textContent = 'Tables listed';
    } else if (statement === 'create_table') {
        displayRawOutput(data.message);
        resultsMeta.textContent = 'Table created';
    } else if (statement === 'drop_table') {
        displayRawOutput(data.message);
        resultsMeta.textContent = 'Table dropped';
    } else if (statement === 'insert') {
        displayRawOutput(data.message);
        resultsMeta.textContent = 'Row inserted';
    } else if (statement === 'delete') {
        displayRawOutput(data.message);
        resultsMeta.textContent = 'Rows deleted';
    } else if (statement === 'explain' || statement === 'describe' || statement === 'desc') {
        displaySchema(data.message);
        resultsMeta.textContent = 'Schema displayed';
    } else {
        displayRawOutput(data.message || JSON.stringify(data, null, 2));
        resultsMeta.textContent = 'Query executed';
    }
}

/**
 * Display SELECT results as a table
 */
function displayTableResults(headers, rows) {
    if (!headers || headers.length === 0) {
        resultsContent.innerHTML = '<p class="placeholder-text">No results returned.</p>';
        return;
    }

    let html = '<table class="results-table"><thead><tr>';
    headers.forEach(header => {
        html += `<th>${escapeHtml(header.toUpperCase())}</th>`;
    });
    html += '</tr></thead><tbody>';

    rows.forEach(row => {
        html += '<tr>';
        headers.forEach(header => {
            const value = row[header];
            const displayValue = value === null || value === undefined ? 'NULL' : escapeHtml(String(value));
            html += `<td>${displayValue}</td>`;
        });
        html += '</tr>';
    });

    html += '</tbody></table>';
    resultsContent.innerHTML = html;
}

/**
 * Display raw text output
 */
function displayRawOutput(text) {
    resultsContent.innerHTML = `<pre class="raw-output">${escapeHtml(text)}</pre>`;
}

/**
 * Display table schema
 */
function displaySchema(text) {
    resultsContent.innerHTML = `<pre class="schema-display">${escapeHtml(text)}</pre>`;
}

/**
 * Display error message
 */
function displayError(message, errorType = '') {
    const typeLabel = errorType ? `[${errorType}] ` : '';
    resultsContent.innerHTML = `
        <div class="message error">
            <span>${escapeHtml(typeLabel + message)}</span>
        </div>
    `;
    resultsMeta.textContent = 'Error';
}

/**
 * Load and display table list
 */
async function loadTables() {
    try {
        const response = await fetch(`${API_BASE}/tables`);
        const data = await response.json();

        if (data.success) {
            renderTableList(data.tables);
        } else {
            tableListContainer.innerHTML = '<p class="loading-text">Failed to load tables</p>';
        }
    } catch (error) {
        tableListContainer.innerHTML = '<p class="loading-text">Error loading tables</p>';
    }
}

/**
 * Render table list in sidebar
 */
function renderTableList(tables) {
    if (tables.length === 0) {
        tableListContainer.innerHTML = '<p class="loading-text">No tables found</p>';
        return;
    }

    let html = '<ul class="table-list">';
    tables.forEach(tableName => {
        html += `
            <li data-table="${escapeHtml(tableName)}" onclick="showTableSchema('${escapeHtml(tableName)}')">
                <span class="table-icon">📄</span>
                <span>${escapeHtml(tableName)}</span>
            </li>
        `;
    });
    html += '</ul>';
    tableListContainer.innerHTML = html;
}

/**
 * Show table schema
 */
async function showTableSchema(tableName) {
    // Highlight selected table
    document.querySelectorAll('.table-list li').forEach(li => {
        li.classList.remove('active');
    });
    const selected = document.querySelector(`[data-table="${CSS.escape(tableName)}"]`);
    if (selected) selected.classList.add('active');

    // Auto-fill DESCRIBE query
    queryInput.value = `DESC ${tableName};`;

    // Execute the describe query
    try {
        const response = await fetch(`${API_BASE}/execute`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: `DESC ${tableName};` })
        });

        const data = await response.json();
        if (data.success) {
            displayResults(data.data);
            resultsMeta.textContent = `Schema: ${tableName}`;
        }
    } catch (error) {
        showMessage('Failed to load schema', 'error');
    }
}

/**
 * Handle transaction actions
 */
async function handleTransaction(action) {
    try {
        const response = await fetch(`${API_BASE}/transaction`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action })
        });

        const data = await response.json();

        if (data.success) {
            if (action === 'BEGIN') {
                isTransactionActive = true;
                transactionStatus.textContent = 'Transaction Active';
                transactionStatus.classList.add('active');
                btnBegin.disabled = true;
                btnCommit.disabled = false;
                btnRollback.disabled = false;
            } else {
                isTransactionActive = false;
                transactionStatus.textContent = 'No active transaction';
                transactionStatus.classList.remove('active');
                btnBegin.disabled = false;
                btnCommit.disabled = true;
                btnRollback.disabled = true;
            }
            showMessage(data.data.message, 'success');
        } else {
            showMessage(data.message, 'error');
        }
    } catch (error) {
        showMessage('Transaction error: ' + error.message, 'error');
    }
}

/**
 * Clear query editor
 */
function clearEditor() {
    queryInput.value = '';
    queryInput.focus();
}

/**
 * Format query with basic indentation
 */
function formatQuery() {
    let query = queryInput.value;
    if (!query.trim()) return;

    const keywords = ['SELECT', 'FROM', 'WHERE', 'INSERT', 'INTO', 'VALUES', 'UPDATE', 'SET', 'DELETE', 'CREATE', 'TABLE', 'DROP', 'ALTER', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER', 'ON', 'GROUP', 'BY', 'ORDER', 'HAVING', 'LIMIT', 'AND', 'OR', 'NOT', 'NULL', 'PRIMARY', 'KEY', 'FOREIGN', 'REFERENCES'];

    let formatted = query;
    keywords.forEach(keyword => {
        const regex = new RegExp(`\\b${keyword}\\b`, 'gi');
        formatted = formatted.replace(regex, keyword);
    });

    // Add newlines before major clauses
    formatted = formatted
        .replace(/\b(SELECT|INSERT|UPDATE|DELETE|CREATE|DROP)\b/gi, '\n$1')
        .replace(/\b(FROM|WHERE|JOIN|LEFT|RIGHT|INNER|OUTER|GROUP|ORDER|HAVING|LIMIT|VALUES|SET)\b/gi, '\n$1')
        .replace(/\b(AND|OR)\b/gi, '\n  $1')
        .trim();

    queryInput.value = formatted;
}

/**
 * Show toast message
 */
function showMessage(text, type = 'info', duration = 5000) {
    const message = document.createElement('div');
    message.className = `message ${type}`;
    message.innerHTML = `
        <span>${escapeHtml(text)}</span>
        <button class="message-close" onclick="this.parentElement.remove()">&times;</button>
    `;

    messageArea.appendChild(message);

    // Auto-remove after duration
    if (duration > 0) {
        setTimeout(() => {
            if (message.parentElement) {
                message.style.animation = 'slideOut 0.3s ease forwards';
                setTimeout(() => message.remove(), 300);
            }
        }, duration);
    }
}

/**
 * Set loading state
 */
function setLoading(loading) {
    btnExecute.disabled = loading;
    btnExecute.textContent = loading ? '⏳ Executing...' : '▶ Execute Query';
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Initialize transaction buttons state
btnCommit.disabled = true;
btnRollback.disabled = true;
