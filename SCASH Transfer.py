import requests
from bs4 import BeautifulSoup
import re
import sys
import csv
import os
from datetime import datetime
import time

BLOCK_HEIGHT = 1  # 指定區塊高度
THRESHOLD = 500  # SCASH 大額轉帳閾值，單位 SCASH
BASE_URL = "https://scash.one"
CSV_FILE = "scash_transfer_records.csv"

def fetch_html(url):
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        resp.encoding = 'utf-8'
        return BeautifulSoup(resp.text, 'html.parser')
    except requests.RequestException as e:
        print(f"HTTP 請求失敗: {e}")
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

def find_txid_by_amount(soup, total_amount):
    list_items = [
        li for li in soup.find_all("li", class_="list-group-item")
        if not (
            (div := li.find("div", class_="text-truncate")) and
            div.get_text(strip=True).startswith("1.")
        )
    ]
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
        if abs(amount - total_amount) < 1e-8:
            txid_a = li.find("a", href=re.compile(r"^/tx/"))
            if txid_a:
                return txid_a.get_text(strip=True)
    print(f"找不到 {total_amount} SCASH，改用閾值 {THRESHOLD} 查詢")
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
                print(f"找到大於閾值的轉帳: {amount} SCASH, TxID: {a_tag.get_text(strip=True)}")
                return a_tag.get_text(strip=True)
    print(f"找不到任何大於閾值 {THRESHOLD} SCASH 的轉帳")
    return None

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

def write_to_csv(rows, file_exists):
    with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "Block Height", "TxID", "Total Amount", "Address", "Balance", "Transfer Time", "Write Time"
            ])
        writer.writerows(rows)

def auto_query_mode(start_height, interval=1):
    height = start_height
    while True:
        print(f"\n查詢區塊高度: {height}")
        result = process_block(height)
        if result is False:
            print("查詢失敗或無法繼續，結束自動查詢模式。")
            break
        height += 1
        time.sleep(interval)

def manual_query_mode():
    while True:
        user_input = input("\n請輸入區塊高度、地址或TxID (輸入 exit 結束): ").strip()
        if user_input.lower() == "exit":
            break
        if user_input.isdigit():
            process_block(int(user_input))
        elif user_input.startswith("scash1"):
            process_address(user_input)
        elif re.fullmatch(r"[0-9a-fA-F]{64}", user_input):
            process_txid(user_input)
        else:
            print("輸入格式錯誤，請重新輸入。")

def process_block(block_height):
    try:
        block_url = f"{BASE_URL}/?search={block_height}"
        soup = fetch_html(block_url)
        total_amount = get_total_output_amount(soup)
        time_str = get_timestamp(soup)
        if total_amount < THRESHOLD:
            print(f"總轉帳金額 {total_amount} SCASH 未達閾值 {THRESHOLD} SCASH，跳過後續查詢。")
            return True
        print(f"區塊高度: {block_height}")
        txid = find_txid_by_amount(soup, total_amount)
        if not txid:
            print("未找到對應的 txid，無法查詢地址")
            return True
        print(f"轉帳 TxID: {txid}  金額: {total_amount} SCASH")
        outputs = get_tx_outputs(txid)
        file_exists = os.path.isfile(CSV_FILE)
        rows_to_write = []
        write_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for address, amount in outputs:
            balance = get_address_balance(address)
            if balance is not None and balance >= THRESHOLD:
                print(f"地址 {address} 目前持有 SCASH: {balance}")
                rows_to_write.append([
                    block_height, txid, total_amount, address, balance, time_str, write_time
                ])
        if rows_to_write:
            write_to_csv(rows_to_write, file_exists)
        else:
            print("沒有符合條件的地址，未寫入任何資料。")
        return True
    except Exception as e:
        print(f"查詢區塊 {block_height} 發生錯誤: {e}")
        return False

def process_address(address):
    balance = get_address_balance(address)
    if balance is not None:
        print(f"地址 {address} 目前持有 SCASH: {balance}")
    else:
        print("查詢失敗，請確認地址正確。")

def process_txid(txid):
    outputs = get_tx_outputs(txid)
    if not outputs:
        print("此TxID無大額轉帳。")
        return
    print(f"TxID: {txid} 的輸出地址與金額：")
    for address, amount in outputs:
        print(f"  地址: {address}  金額: {amount} SCASH")

def main():
    print("選擇模式：")
    print("1. 自動查詢模式 (從起始區塊開始，直到查詢失敗自動結束)")
    print("2. 手動查詢模式 (輸入區塊高度/地址/TxID)")
    mode = input("請輸入模式編號 (1/2): ").strip()
    if mode == "1":
        start = input("請輸入起始區塊高度 (預設 1): ").strip()
        interval = input("請輸入查詢間隔秒數 (預設 1): ").strip()
        start_height = int(start) if start.isdigit() else 1
        interval_sec = int(interval) if interval.isdigit() else 1
        auto_query_mode(start_height, interval_sec)
    elif mode == "2":
        manual_query_mode()
    else:
        print("輸入錯誤，請重新執行。")

if __name__ == "__main__":
    main()
