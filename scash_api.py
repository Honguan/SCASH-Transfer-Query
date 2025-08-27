from flask import Flask, jsonify
import sqlite3
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

def get_db_connection():
    conn = sqlite3.connect('scash_data.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/api/address_balances')
def address_balances():
    conn = get_db_connection()
    rows = conn.execute('SELECT * FROM scash_address_balances ORDER BY balance DESC LIMIT 100').fetchall()
    conn.close()
    data = [dict(row) for row in rows]
    return jsonify(data)

@app.route('/api/tx_records')
def tx_records():
    conn = get_db_connection()
    rows = conn.execute('SELECT * FROM tx ORDER BY block_height DESC, txid DESC LIMIT 100').fetchall()
    conn.close()
    data = [dict(row) for row in rows]
    return jsonify(data)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
