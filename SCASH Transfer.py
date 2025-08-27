import requests
from bs4 import BeautifulSoup
import re
import sys
import sqlite3
import os
from datetime import datetime
import time
from config import BLOCK_HEIGHT, THRESHOLD, BASE_URL, CSV_FILE, ADDRESS_BALANCE_FILE, SHOW_RESULT, SCAN_INTERVAL, DB_FILE
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        # 區塊表：block_height 主鍵，txids 為 JSON 字串
        c.execute('''CREATE TABLE IF NOT EXISTS block (
            block_height INTEGER PRIMARY KEY,
            txids TEXT
        )''')
        # 交易表：每一筆 address/amount/transfer_time 都是一列
        c.execute('''CREATE TABLE IF NOT EXISTS tx (
            txid TEXT,
            block_height INTEGER,
            address TEXT,
            amount REAL,
            transfer_time TEXT,
            PRIMARY KEY (txid, address),
            FOREIGN KEY (block_height) REFERENCES block(block_height)
        )''')
        # 地址餘額表
        c.execute('''CREATE TABLE IF NOT EXISTS scash_address_balances (
            address TEXT PRIMARY KEY,
            balance REAL,
            scan_time TEXT,
            update_time TEXT,
            update_count INTEGER,
            change_str TEXT
        )''')
        conn.commit()


def fetch_html(url, retries=10, retry_interval=3):
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            resp.encoding = 'utf-8'
            return BeautifulSoup(resp.text, 'html.parser')
        except requests.RequestException as e:
            print(f"HTTP 請求失敗: {e} (第 {attempt} 次)")
            if attempt < retries:
                time.sleep(retry_interval)
            else:
                sys.exit(1)

def get_timestamp(soup):
    time_div = soup.find("div", class_="fw-bold", string="Time")
    if not time_div:
        print("找不到時間區塊")
        return None
    parent_div = time_div.find_parent("div", class_="ms-2 me-auto")
    if not parent_div:
        print("找不到時間父區塊")
        return None
    text = parent_div.get_text(separator=" ", strip=True)
    return text.replace("Time", "", 1).strip()

def get_total_output_amount(soup):
    elem = soup.find(string=re.compile("Total amount in all outputs"))
    if not elem:
        print("無法找到總輸出金額")
        sys.exit(1)
    parent = elem.find_parent("li")
    div = parent.find("div", class_="ms-2 me-auto") if parent else None
    if not div:
        print("無法找到金額區塊")
        sys.exit(1)
    match = re.search(r"([\d'\.]+)\s*SCASH", div.get_text(separator=" ", strip=True))
    if not match:
        print("無法解析 SCASH 數值")
        sys.exit(1)
    return float(match.group(1).replace("'", ""))

def find_txids_by_amount(soup, total_amount):
    """
    優先找整數位相同的轉帳txid，再找所有大於閾值的轉帳txid，回傳所有txid(不重複，優先順序)。
    """
    list_items = [
        li for li in soup.find_all("li", class_="list-group-item")
        if not (
            (div := li.find("div", class_="text-truncate")) and
            div.get_text(strip=True).startswith("1.")
        )
    ]
    txids = []
    seen = set()
    # 1. 優先找整數位相同的轉帳
    total_int = int(total_amount)
    for li in list_items:
        badge = li.find("span", class_=lambda x: x and "badge" in x and "bg-primary" in x)
        if not badge:
            continue
        match = re.search(r"([\d\.]+)\s*SCASH", badge.get_text(strip=True))
        if not match:
            continue
        amount = float(match.group(1))
        if abs(amount - 50) < 1e-6:
            continue
        if int(amount) == total_int and amount >= THRESHOLD:
            txid_a = li.find("a", href=re.compile(r"^/tx/"))
            if txid_a:
                txid = txid_a.get_text(strip=True)
                if txid not in seen:
                    txids.append(txid)
                    seen.add(txid)
    # 2. 其他大於閾值的轉帳
    for li in list_items:
        badge = li.find("span", class_=lambda x: x and "badge" in x and "bg-primary" in x)
        if not badge:
            continue
        match = re.search(r"([\d\.]+)\s*SCASH", badge.get_text(strip=True))
        if not match:
            continue
        amount = float(match.group(1))
        if abs(amount - 50) < 1e-6:
            continue
        if amount >= THRESHOLD:
            a_tag = li.find("a", href=re.compile(r"^/tx/"))
            if a_tag:
                txid = a_tag.get_text(strip=True)
                if txid not in seen:
                    txids.append(txid)
                    seen.add(txid)
    if not txids:
        print(f"找不到任何大於閾值 {THRESHOLD} SCASH 的轉帳")
    return txids

def get_tx_outputs(txid):
    tx_url = f"{BASE_URL}/tx/{txid}"
    tx_soup = fetch_html(tx_url)
    outputs = []
    total_outputs_li = tx_soup.find("div", class_="fw-bold", string=re.compile(r"Total outputs"))
    if total_outputs_li:
        parent_li = total_outputs_li.find_parent("li")
        if parent_li:
            amount_div = parent_li.find("div", class_="ms-2 me-auto")
            if amount_div:
                match = re.search(r"([\d'\.]+)\s*SCASH", amount_div.get_text(separator=" ", strip=True))
                if match and float(match.group(1).replace("'", "")) >= THRESHOLD:
                    for item in tx_soup.find_all("li", class_="list-group-item"):
                        addr_a = item.find("a", href=re.compile(r"^/\?&search=scash1"))
                        if addr_a:
                            address = re.search(r"search=(scash1[0-9a-zA-Z]+)", addr_a['href'])
                            full_address = address.group(1) if address else addr_a.get_text(strip=True)
                            amount_span = item.find("span", class_="text-muted")
                            if amount_span:
                                amount_match = re.search(r"([\d'\.]+)\s*SCASH", amount_span.get_text(strip=True))
                                if amount_match:
                                    amount = float(amount_match.group(1).replace("'", ""))
                                    outputs.append((full_address, amount))
    return outputs

def get_address_balance(address):
    url = f"{BASE_URL}/?search={address}&utxolookup=1"
    soup = fetch_html(url)
    total_div = soup.find("div", class_="totalamount")
    if not total_div:
        print("找不到總餘額區塊")
        return None
    match = re.search(r"Total unspent SCASH:\s*([\d\.]+)", total_div.get_text())
    if not match:
        print("無法解析總餘額")
        return None
    return float(match.group(1))


def write_transfer_db(rows):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        for row in rows:
            c.execute('''INSERT INTO scash_transfer_records (block_height, txid, address, amount, transfer_time)
                         VALUES (?, ?, ?, ?, ?)''', row)
        conn.commit()


def write_address_balance_db(address, balance, conn=None):
    if balance < THRESHOLD:
        return
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    close_conn = False
    if conn is None:
        conn = sqlite3.connect(DB_FILE)
        close_conn = True
    c = conn.cursor()
    c.execute('SELECT balance, scan_time, update_time, update_count FROM scash_address_balances WHERE address=?', (address,))
    row = c.fetchone()
    if row:
        last_balance, scan_time, update_time, update_count = row
        diff = balance - last_balance if last_balance is not None else 0
        if abs(diff) > 1e-8:
            # diff > 0 顯示 +，diff < 0 顯示 -
            if diff > 0:
                change_str = f"+{diff:.8f}"
            else:
                change_str = f"{diff:.8f}"
            update_time = now_str
            update_count = (update_count or 0) + 1
            c.execute('''UPDATE scash_address_balances SET balance=?, update_time=?, update_count=?, change_str=? WHERE address=?''',
                      (balance, update_time, update_count, change_str, address))
    else:
        # 新增
        c.execute('''INSERT INTO scash_address_balances (address, balance, scan_time, update_time, update_count, change_str)
                     VALUES (?, ?, ?, ?, ?, ?)''',
                  (address, balance, now_str, '', 0, ''))
    if close_conn:
        conn.commit()
        conn.close()

def record_address_balance(address, address_balance_set, conn=None):
    """查詢並記錄唯一地址餘額。"""
    if address_balance_set is not None and address not in address_balance_set:
        balance = get_address_balance(address)
        if balance is not None and balance >= THRESHOLD:
            address_balance_set.add(address)
            write_address_balance_db(address, balance, conn)

def auto_query_mode(start_height, end_height=None):
    height = start_height
    address_balance_set = set()
    while True:
        try:
            if end_height is not None and height > end_height:
                print("已達結束區塊高度，結束自動查詢模式。")
                break
            print(f"\n查詢區塊高度: {height}")
            result = process_and_record_block(height, address_balance_set)
            if result:
                height += 1
                time.sleep(SCAN_INTERVAL)
            else:
                print("查詢失敗或查不到，10分鐘後重試本區塊...")
                for i in range(10*60, 0, -1):
                    print(f"  等待 {i//60:02d}:{i%60:02d} 後重試...", end='\r')
                    time.sleep(1)
                print("\n重新嘗試掃描本區塊...")
        except KeyboardInterrupt:
            print("\n偵測到中斷 (Ctrl+C)，將完成本區塊查詢與寫入後詢問是否終止...")
            while True:
                user_choice = input("是否終止程序？(Y/n): ").strip().lower()
                if user_choice == '' or user_choice == 'y':
                    print("程式已終止。")
                    return
                elif user_choice == 'n':
                    print("繼續查詢...")
                    break
                else:
                    print("請輸入 Y 或 n。直接 Enter 預設為 Y。")

def process_and_record_block(block_height, address_balance_set):
    """查詢區塊、記錄轉帳與地址餘額，回傳True/False代表是否繼續。"""
    import json
    import traceback
    try:
        block_url = f"{BASE_URL}/?search={block_height}"
        soup = fetch_html(block_url)
        total_amount = get_total_output_amount(soup)
        time_str = get_timestamp(soup)
        if total_amount < THRESHOLD:
            if SHOW_RESULT:
                print(f"總轉帳金額 {total_amount} SCASH 未達閾值 {THRESHOLD} SCASH，跳過後續查詢。")
            return True
        if SHOW_RESULT:
            print(f"區塊高度: {block_height}")
        txids = find_txids_by_amount(soup, total_amount)
        if not txids:
            if SHOW_RESULT:
                print("未找到對應的 txid，無法查詢地址")
            return True
        # 寫入 block、tx、address_balance 都共用同一個 conn
        with sqlite3.connect(DB_FILE) as conn:
            c = conn.cursor()
            c.execute('INSERT OR REPLACE INTO block (block_height, txids) VALUES (?, ?)', (block_height, json.dumps(txids)))
            for txid in txids:
                if SHOW_RESULT:
                    print(f"轉帳 TxID: {txid}")
                outputs = get_tx_outputs(txid)
                for address, amount in outputs:
                    if amount < THRESHOLD:
                        continue
                    record_address_balance(address, address_balance_set, conn)
                    c.execute('''INSERT OR REPLACE INTO tx (txid, block_height, address, amount, transfer_time)
                                 VALUES (?, ?, ?, ?, ?)''',
                              (txid, block_height, address, amount, time_str))
            conn.commit()
        return True
    except Exception as e:
        print(f"查詢區塊 {block_height} 發生錯誤: {e}")
        traceback.print_exc()
        return False


def manual_query_mode():
    address_balance_set = set()
    while True:
        user_input = input("\n請輸入區塊高度、地址或TxID (輸入 exit 結束): ").strip()
        if user_input.lower() == "exit":
            break
        if user_input.isdigit():
            process_and_record_block(int(user_input), address_balance_set)
        elif user_input.startswith("scash1"):
            record_address_balance(user_input, address_balance_set, None)
            process_address(user_input)
        elif re.fullmatch(r"[0-9a-fA-F]{64}", user_input):
            process_txid(user_input)
        else:
            print("輸入格式錯誤，請重新輸入。")

def process_block(block_height, address_balance_set=None):
    try:
        block_url = f"{BASE_URL}/?search={block_height}"
        soup = fetch_html(block_url)
        total_amount = get_total_output_amount(soup)
        time_str = get_timestamp(soup)
        if total_amount < THRESHOLD:
            if SHOW_RESULT:
                print(f"總轉帳金額 {total_amount} SCASH 未達閾值 {THRESHOLD} SCASH，跳過後續查詢。")
            return True
        if SHOW_RESULT:
            print(f"區塊高度: {block_height}")
        txids = find_txids_by_amount(soup, total_amount)
        if not txids:
            if SHOW_RESULT:
                print("未找到對應的 txid，無法查詢地址")
            return True
        all_rows_to_write = []
        for txid in txids:
            if SHOW_RESULT:
                print(f"轉帳 TxID: {txid}")
            outputs = get_tx_outputs(txid)
            rows_to_write = []
            for address, amount in outputs:
                if amount < THRESHOLD:
                    continue
                # 查詢地址餘額並記錄唯一地址
                if address_balance_set is not None:
                    if address not in address_balance_set:
                        balance = get_address_balance(address)
                        if balance is not None and balance >= THRESHOLD:
                            address_balance_set.add(address)
                            write_address_balance_db(address, balance)
                # 寫入轉帳紀錄
                rows_to_write.append([
                    block_height, txid, address, amount, time_str
                ])
            all_rows_to_write.extend(rows_to_write)
        if all_rows_to_write:
            write_transfer_db(all_rows_to_write)
        else:
            if SHOW_RESULT:
                print("沒有符合條件的地址，未寫入任何資料。")
        return True
    except Exception as e:
        print(f"查詢區塊 {block_height} 發生錯誤: {e}")
        return False

def process_address(address):
    balance = get_address_balance(address)
    if SHOW_RESULT:
        if balance is not None:
            print(f"地址 {address} 目前持有 SCASH: {balance}")
        else:
            print("查詢失敗，請確認地址正確。")

def process_txid(txid):
    outputs = get_tx_outputs(txid)
    if SHOW_RESULT:
        if not outputs:
            print("此TxID無大額轉帳。")
            return
        print(f"TxID: {txid} 的輸出地址與金額：")
        for address, amount in outputs:
            print(f"  地址: {address}  金額: {amount} SCASH")

def main():
    init_db()
    while True:
        print("\n選擇模式：")
        print("1. 自動查詢模式 (可指定起始/結束區塊高度，結束高度預設查不到為止)")
        print("2. 手動查詢模式 (輸入區塊高度/地址/TxID)")
        print("3. 設定檔設定模式 (修改 config.py 參數)")
        print("0. 離開")
        mode = input("請輸入模式編號 (1/2/3/0): ").strip()
        if mode == "1":
            start = input("請輸入起始區塊高度 (預設 1): ").strip()
            end = input("請輸入結束區塊高度 (留空則查到失敗為止): ").strip()
            start_height = int(start) if start.isdigit() else 1
            end_height = int(end) if end.isdigit() else None
            auto_query_mode(start_height, end_height)
        elif mode == "2":
            manual_query_mode()
        elif mode == "3":
            config_setting_mode()
        elif mode == "0":
            print("程式結束。")
            break
        else:
            print("輸入錯誤，請重新輸入。")

# 設定檔設定模式
def config_setting_mode():
    import ast
    config_path = os.path.join(os.path.dirname(__file__), 'config.py')
    # 讀取現有設定
    with open(config_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    # 解析現有設定
    config_vars = {}
    for line in lines:
        if '=' in line and not line.strip().startswith('#'):
            key, val = line.split('=', 1)
            key = key.strip()
            val = val.strip().split('#')[0].strip()
            try:
                config_vars[key] = ast.literal_eval(val)
            except Exception:
                config_vars[key] = val.strip('"\'')
    while True:
        print("\n目前設定：")
        for k, v in config_vars.items():
            print(f"{k} = {v}")
        print("\n可修改參數：")
        for idx, k in enumerate(config_vars.keys(), 1):
            print(f"{idx}. {k}")
        print("0. 儲存並返回主選單")
        sel = input("請輸入要修改的參數編號 (或 0 返回): ").strip()
        if sel == "0":
            # 寫回 config.py
            with open(config_path, 'w', encoding='utf-8') as f:
                for line in lines:
                    if '=' in line and not line.strip().startswith('#'):
                        key = line.split('=', 1)[0].strip()
                        if key in config_vars:
                            f.write(f"{key} = {repr(config_vars[key])}\n")
                        else:
                            f.write(line)
                    else:
                        f.write(line)
            print("設定已儲存，返回主選單。\n")
            break
        try:
            idx = int(sel) - 1
            if idx < 0 or idx >= len(config_vars):
                print("參數編號錯誤，請重新輸入。")
                continue
            key = list(config_vars.keys())[idx]
            new_val = input(f"請輸入新的值 ({key}，目前值: {config_vars[key]}): ").strip()
            # 嘗試自動型別轉換
            try:
                config_vars[key] = ast.literal_eval(new_val)
            except Exception:
                config_vars[key] = new_val
        except Exception:
            print("輸入錯誤，請重新輸入。")

if __name__ == "__main__":
    main()
