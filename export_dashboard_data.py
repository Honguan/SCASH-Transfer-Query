import sqlite3
import json

DB_FILE = 'scash_data.db'

# 匯出 addressBalances
addressBalances = []
with sqlite3.connect(DB_FILE) as conn:
    c = conn.cursor()
    for row in c.execute('SELECT address, balance, change_str, update_count, scan_time, update_time FROM scash_address_balances ORDER BY balance DESC'):
        addressBalances.append({
            'address': row[0],
            'balance': row[1],
            'change_str': row[2],
            'update_count': row[3],
            'scan_time': row[4],
            'update_time': row[5]
        })

# 匯出 txRecords
# 只顯示大額（可依需求調整）
txRecords = []
with sqlite3.connect(DB_FILE) as conn:
    c = conn.cursor()
    for row in c.execute('SELECT block_height, txid, address, amount, transfer_time FROM tx ORDER BY block_height DESC, amount DESC'):
        txRecords.append({
            'block_height': row[0],
            'txid': row[1],
            'address': row[2],
            'amount': row[3],
            'transfer_time': row[4]
        })

# 輸出到 dashboard_data.js
with open('assets\dashboard_data.js', 'w', encoding='utf-8') as f:
    f.write('const addressBalances = ' + json.dumps(addressBalances, ensure_ascii=False) + ';\n')
    f.write('const txRecords = ' + json.dumps(txRecords, ensure_ascii=False) + ';\n')

print('已匯出 dashboard_data.js，可直接在 scash_dashboard.html 引入！')
