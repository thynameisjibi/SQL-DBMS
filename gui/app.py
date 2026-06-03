"""Flask web GUI for the SQL DBMS."""

import sys
import os
from pathlib import Path

# Add parent directory to path to import dbms modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from lark import Lark

from dbms import DBMS
from messages import *
from sql_transformer import SQLTransformer
from db_model import DB

app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)

# Single shared DBMS instance
dbms = DBMS()

# Load SQL parser once at startup
parser_path = Path(__file__).parent.parent / 'grammar.lark'
with open(parser_path) as file:
    sql_parser = Lark(file.read(), start="command", lexer="basic")


def parse_query_sequence(input_query_sequence: str):
    """Parses the input query sequence and returns a list of queries."""
    while True:
        input_query_sequence = input_query_sequence.rstrip()
        if input_query_sequence.endswith(";"):
            break
        else:
            input_query_sequence += " " + input()
    query_list = input_query_sequence.split(";")
    return [query.strip() + ';' for query in query_list if query.strip()]


def parse_query(sql_parser: Lark, sql_transformer, query):
    """Parses the query and returns the transformed parse tree."""
    try:
        parsed = sql_parser.parse(query)
    except:
        raise SyntaxError()
    else:
        transformed = sql_transformer.transform(parsed)
        return transformed


@app.route('/')
def index():
    """Render main interface."""
    return render_template('index.html')


@app.route('/api/execute', methods=['POST'])
def execute_query():
    """Execute SQL query and return results."""
    if not request.is_json:
        return jsonify({'success': False, 'message': 'Content-Type must be application/json'}), 400

    query = request.json.get('query', '').strip()
    if not query:
        return jsonify({'success': False, 'message': 'Query is required'}), 400

    try:
        sql_transformer = SQLTransformer()
        statement, table, record, tables, select_columns, where, index = parse_query(
            sql_parser, sql_transformer, query
        )

        if statement == 'exit':
            return jsonify({
                'success': True,
                'data': {
                    'statement': 'exit',
                    'message': 'Goodbye!'
                }
            })

        elif statement == "create table":
            success = dbms.create_table(table)
            return jsonify({
                'success': True,
                'data': {
                    'statement': 'create_table',
                    'message': str(success)
                }
            })

        elif statement == "drop table":
            success = dbms.drop_table(table["table_name"])
            return jsonify({
                'success': True,
                'data': {
                    'statement': 'drop_table',
                    'message': str(success)
                }
            })

        elif statement in ("explain", "describe", "desc"):
            table_obj = dbms.explain_describe_desc(table["table_name"])
            return jsonify({
                'success': True,
                'data': {
                    'statement': statement,
                    'message': str(table_obj)
                }
            })

        elif statement == "show tables":
            output = dbms.show_tables()
            return jsonify({
                'success': True,
                'data': {
                    'statement': 'show_tables',
                    'message': output
                }
            })

        elif statement == "insert":
            result = dbms.insert(table, record)
            return jsonify({
                'success': True,
                'data': {
                    'statement': 'insert',
                    'message': str(result)
                }
            })

        elif statement == "delete":
            result, extra = dbms.delete(table["table_name"], where)
            messages = [str(result)]
            if extra:
                messages.append(str(extra))
            return jsonify({
                'success': True,
                'data': {
                    'statement': 'delete',
                    'message': '\n'.join(messages)
                }
            })

        elif statement == "select":
            output = dbms.select(tables, select_columns, where)
            # Parse the formatted output into structured data
            headers, rows = parse_select_output(output)
            return jsonify({
                'success': True,
                'data': {
                    'statement': 'select',
                    'headers': headers,
                    'rows': rows,
                    'message': 'Query executed successfully'
                }
            })

        elif statement == "create index":
            result = dbms.create_index(
                table["table_name"],
                index["index_name"],
                index["column_name"]
            )
            return jsonify({
                'success': True,
                'data': {
                    'statement': 'create_index',
                    'message': str(result)
                }
            })

        elif statement == "drop index":
            result = dbms.drop_index(
                table["table_name"],
                index["index_name"]
            )
            return jsonify({
                'success': True,
                'data': {
                    'statement': 'drop_index',
                    'message': str(result)
                }
            })

        else:
            return jsonify({
                'success': False,
                'message': f'Unsupported statement: {statement}'
            }), 400

    except (SyntaxError, NoSuchTable, DuplicateColumnDefError, DuplicatePrimaryKeyDefError,
            ReferenceTypeError, ReferenceNonPrimaryKeyError, ReferenceColumnExistenceError, ReferenceTableExistenceError,
            NonExistingColumnDefError, TableExistenceError, CharLengthError, DropReferencedTableError,
            InsertTypeMismatchError, InsertColumnExistenceError, InsertColumnNonNullableError,
            InsertDuplicatePrimaryKeyError, InsertReferentialIntegrityError,
            SelectTableExistenceError, SelectColumnResolveError,
            WhereIncomparableError, WhereTableNotSpecified, WhereColumnNotExist, WhereAmbiguousReference,
            DuplicateIndexError, NoSuchIndexError, IndexExistenceError) as e:
        error_type = type(e).__name__
        return jsonify({
            'success': False,
            'message': str(e),
            'error_type': error_type
        }), 400

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Internal error: {str(e)}',
            'error_type': type(e).__name__
        }), 500


def parse_select_output(output: str):
    """Parse the formatted SELECT output into headers and rows."""
    lines = output.strip().split('\n')
    headers = []
    rows = []

    for line in lines:
        line = line.strip()
        if not line or line.startswith('+-'):
            continue
        if line.startswith('| '):
            cells = [cell.strip() for cell in line.split('|')[1:-1]]
            if not headers:
                headers = [cell.lower() for cell in cells]
            else:
                row = {}
                for i, cell in enumerate(cells):
                    if i < len(headers):
                        # Try to convert to int if possible
                        try:
                            row[headers[i]] = int(cell)
                        except ValueError:
                            row[headers[i]] = cell
                rows.append(row)

    return headers, rows


@app.route('/api/tables', methods=['GET'])
def get_tables():
    """Get list of all tables."""
    try:
        dbms.meta_db.open_db()
        tables = []
        for key in dbms.meta_db.keys():
            table_name = key.decode()
            tables.append(table_name)
        dbms.meta_db.close_db()
        return jsonify({'success': True, 'tables': tables})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/schema/<table_name>', methods=['GET'])
def get_schema(table_name):
    """Get schema for a table."""
    try:
        table = dbms.explain_describe_desc(table_name)
        return jsonify({
            'success': True,
            'data': {
                'schema': str(table)
            }
        })
    except NoSuchTable:
        return jsonify({'success': False, 'message': 'Table not found'}), 404
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/transaction', methods=['POST'])
def transaction():
    """Transaction management endpoint."""
    if not request.is_json:
        return jsonify({'success': False, 'message': 'Content-Type must be application/json'}), 400

    action = request.json.get('action', '').upper()
    if not action:
        return jsonify({'success': False, 'message': 'Action is required'}), 400

    if action not in ('BEGIN', 'COMMIT', 'ROLLBACK'):
        return jsonify({'success': False, 'message': f'Invalid transaction action: {action}'}), 400

    # Note: The current DBMS implementation does not support explicit transactions.
    # This endpoint returns a success message for API compatibility.
    # Future implementations should integrate proper transaction state management.
    messages = {
        'BEGIN': 'Transaction started',
        'COMMIT': 'Transaction committed',
        'ROLLBACK': 'Transaction rolled back'
    }

    return jsonify({
        'success': True,
        'data': {
            'action': action,
            'message': messages[action]
        }
    })


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
