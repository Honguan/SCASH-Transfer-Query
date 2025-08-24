import requests
from bs4 import BeautifulSoup
import re
import sys

BLOCK_HEIGHT = 89876
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
    match = re.search(r"([\d\.]+)\s*SCASH", text)
    if not match:
        print("無法解析 SCASH 數值")
        sys.exit()
    return float(match.group(1))

def find_txid_by_amount(soup, total_amount):
    badges = soup.find_all("span", class_=lambda x: x and "badge" in x and "bg-primary" in x)
    for badge in badges:
        scash_text = badge.get_text(strip=True)
        match = re.search(r"([\d\.]+)\s*SCASH", scash_text)
        if match and abs(float(match.group(1)) - total_amount) < 1e-8:
            li = badge.find_parent("li")
            if not li:
                continue
            txid_a = li.find("a", href=re.compile(r"^/tx/"))
            if txid_a:
                return txid_a.get_text(strip=True)
    print(f"找不到 <span class=\"badge bg-primary me-1\">{total_amount} SCASH</span>")
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
    print(f"找到總輸出金額: {total_amount} SCASH")
    txid = find_txid_by_amount(soup, total_amount)
    if not txid:
        print("未找到對應的 txid，無法查詢地址")
        return
    print(f"定位到總輸出金額對應的 TxID: {txid}  金額: {total_amount} SCASH")
    outputs = get_tx_outputs(txid)
    for address, amount in outputs:
        print(f"地址: {address}  轉帳金額: {amount} SCASH")
        balance = get_address_balance(address)
        if balance is not None:
            print(f"地址 {address} 目前持有 SCASH: {balance}")

if __name__ == "__main__":
    main()
