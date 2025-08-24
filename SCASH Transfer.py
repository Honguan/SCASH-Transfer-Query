import requests
from bs4 import BeautifulSoup
import re
import sys
import csv
import os

BLOCK_HEIGHT = 32186  # 指定區塊高度
THRESHOLD = 10  # SCASH 大額轉帳閾值，單位 SCASH
BASE_URL = "https://scash.one"

def fetch_html(url):
    resp = requests.get(url)
    if resp.status_code != 200:
        print(f"HTTP 請求失敗，狀態碼: {resp.status_code}")
        sys.exit()
    resp.encoding = 'utf-8'
    return BeautifulSoup(resp.text, 'html.parser')

def get_total_output_amount(soup):
    elem = soup.find(string=re.compile("Total amount in all outputs"))
    if not elem:
        print("無法找到總輸出金額")
        sys.exit()
    parent = elem.find_parent("li")
    if not parent:
        print("無法找到包含總輸出金額的 li 元素")
        sys.exit()
    div = parent.find("div", class_="ms-2 me-auto")
    if not div:
        print("無法找到金額區塊")
        sys.exit()
    text = div.get_text(separator=" ", strip=True)
    match = re.search(r"([\d'\.]+)\s*SCASH", text)
    if not match:
        print("無法解析 SCASH 數值")
        sys.exit()
    number_str = match.group(1).replace("'", "")  # 移除千分位撇號
    return float(number_str)

def find_txid_by_amount(soup, total_amount):
    # 取得所有交易 <li>
    list_items = soup.find_all("li", class_="list-group-item")
    # 移除所有以 "1.&nbsp;" 開頭的 <li>（通常是區塊獎勵或非轉帳項）
    list_items = [
        li for li in list_items
        if not (
            li.find("div", class_="text-truncate") and
            li.find("div", class_="text-truncate").get_text(strip=True).startswith("1.")
        )
    ]

    for li in list_items:
        badge = li.find("span", class_=lambda x: x and "badge" in x and "bg-primary" in x)
        if not badge:
            continue
        scash_text = badge.get_text(strip=True)
        match = re.search(r"([\d\.]+)\s*SCASH", scash_text)
        if match:
            amount = float(match.group(1))
            # 剃除整數剛好50的轉帳
            if abs(amount - 50) < 1e-8:
                continue
            if abs(amount - total_amount) < 1e-8:
                txid_a = li.find("a", href=re.compile(r"^/tx/"))
                if txid_a:
                    return txid_a.get_text(strip=True)

    # 若找不到，改用 THRESHOLD 查詢所有大於 THRESHOLD 的轉帳
    print(f"找不到 {total_amount} SCASH，改用閾值 {THRESHOLD} 查詢")
    for li in list_items:
        a_tag = li.find("a", href=re.compile(r"^/tx/"))
        if not a_tag:
            continue
        # 檢查 <a> 標籤的父 div 是否以 "1.\xa0" 開頭（即 1.&nbsp;），只跳過這一種
        parent_div = a_tag.find_parent("div", class_="text-truncate")
        if parent_div and parent_div.get_text(strip=True).startswith("1.\xa0"):
            continue  # 跳過只有 1.&nbsp; 開頭的
        badge = li.find("span", class_=lambda x: x and "badge" in x and "bg-primary" in x)
        if not badge:
            continue
        scash_text = badge.get_text(strip=True)
        match = re.search(r"([\d\.]+)\s*SCASH", scash_text)
        if match:
            amount = float(match.group(1))
            # 剃除金額在 50±1e-6 之間的轉帳
            if abs(amount - 50) < 1e-6:
                continue
            if amount >= THRESHOLD:
                print(f"找到大於閾值的轉帳: {amount} SCASH, TxID: {a_tag.get_text(strip=True)}")
                return a_tag.get_text(strip=True)
    print(f"找不到任何大於閾值 {THRESHOLD} SCASH 的轉帳")
    return None

def get_tx_outputs(txid):
    tx_url = f"{BASE_URL}/tx/{txid}"
    tx_soup = fetch_html(tx_url)
    outputs = []
    for item in tx_soup.find_all("li", class_="list-group-item"):
        addr_a = item.find("a", href=re.compile(r"^/\?&search=scash1"))
        if addr_a:
            address = addr_a['href']
            match = re.search(r"search=(scash1[0-9a-zA-Z]+)", address)
            full_address = match.group(1) if match else addr_a.get_text(strip=True)
            amount_span = item.find("span", class_="text-muted spent")
            if amount_span:
                amount_text = amount_span.get_text(strip=True)
                amount_match = re.search(r"([\d\.]+)\s*SCASH", amount_text)
                if amount_match:
                    outputs.append((full_address, float(amount_match.group(1))))
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

def main():
    block_url = f"{BASE_URL}/?search={BLOCK_HEIGHT}"
    soup = fetch_html(block_url)
    total_amount = get_total_output_amount(soup)
    if total_amount < THRESHOLD:
        print(f"總輸出金額 {total_amount} SCASH 未達閾值 {THRESHOLD} SCASH，跳過後續查詢。")
        return
    else:
        print(f"區塊高度: {BLOCK_HEIGHT}")
        txid = find_txid_by_amount(soup, total_amount)
        if not txid:
            print("未找到對應的 txid，無法查詢地址")
            return
        print(f"轉帳 TxID: {txid}  金額: {total_amount} SCASH")
        outputs = get_tx_outputs(txid)
        csv_file = "scash_transfer_records.csv"
        file_exists = os.path.isfile(csv_file)
        rows_to_write = []
        for address, amount in outputs:
            balance = get_address_balance(address)
            if balance is not None and balance >= THRESHOLD:
                print(f"地址 {address} 目前持有 SCASH: {balance}")
                rows_to_write.append([BLOCK_HEIGHT, txid, total_amount, address, balance])
        if rows_to_write:
            with open(csv_file, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(["Block Height", "TxID", "Total Amount", "Address", "Balance"])
                writer.writerows(rows_to_write)
        else:
            print("沒有符合條件的地址，未寫入任何資料。")

if __name__ == "__main__":
    main()
