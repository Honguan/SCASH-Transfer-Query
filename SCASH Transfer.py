import requests
from bs4 import BeautifulSoup
import re
import sys  # 新增


# 設定要監控的區塊高度或交易ID
block_height = 89876
threshold = 10  # SCASH 大額轉帳閾值，單位 SCASH

# SCASH 區塊資訊 API
block_url = f"https://scash.one/?search={block_height}"

response = requests.get(block_url)
if response.status_code != 200:
    print(f"HTTP 請求失敗，狀態碼: {response.status_code}")
    sys.exit()
response.encoding = 'utf-8'

soup = BeautifulSoup(response.text, 'html.parser')

## 解析 HTML 內容，尋找總輸出金額
# 從 HTML 中尋找 "Total amount in all outputs" 的 SCASH 數值
total_amount_elem = soup.find(string=re.compile("Total amount in all outputs"))
if not total_amount_elem:
    print("無法找到總輸出金額")
    sys.exit()

# 往上找到包含數值的父元素，然後往下找 SCASH 數值
parent = total_amount_elem.find_parent("li")
if not parent:
    print("無法找到包含總輸出金額的 li 元素")
    sys.exit()
# 在 div 內尋找包含金額的文字（去除標籤與 SCASH 字樣）
div = parent.find("div", class_="ms-2 me-auto")
if not div:
    print("無法找到金額區塊")
    sys.exit()
# 取得 div 內所有文字，過濾出數字
text = div.get_text(separator=" ", strip=True)
match = re.search(r"([\d\.]+)\s*SCASH", text)
if not match:
    print("無法解析 SCASH 數值")
    sys.exit()
scash_value_elem = match

total_amount = scash_value_elem.group(1)

print(f"找到總輸出金額: {total_amount} SCASH")


## 使用 SCASH，尋找 txid
# 尋找所有包含 SCASH 金額的 badge
total_amount_float = float(total_amount)
scash_badges = soup.find_all("span", class_=lambda x: x and "badge" in x and "bg-primary" in x)
found = False
for badge in scash_badges:
    scash_text = badge.get_text(strip=True)
    scash_match = re.search(r"([\d\.]+)\s*SCASH", scash_text)
    if scash_match:
        scash_amount = float(scash_match.group(1))
        # 比較金額是否等於 total_amount
        if abs(scash_amount - total_amount_float) < 1e-8:
            found = True
            # 往上找到 li
            li = badge.find_parent("li")
            if not li:
                continue
            # 在 li 內尋找 txid 的 a 標籤
            txid_a = li.find("a", href=re.compile(r"^/tx/"))
            if not txid_a:
                continue
            txid = txid_a.get_text(strip=True)
            print(f"定位到總輸出金額對應的 TxID: {txid}  金額: {scash_amount} SCASH")
    else:
        print(f"無法解析 badge 內的 SCASH 數值: {scash_text}")

if not found:
    print("找不到 <span class=\"badge bg-primary me-1\">{total_amount} SCASH</span>")

## 使用 txid，尋找地址 
# 取得 txid 後，請求該交易詳情頁面
if txid is not None and txid:
    tx_url = f"https://scash.one/tx/{txid}"
    tx_response = requests.get(tx_url)
    if tx_response.status_code != 200:
        print(f"無法取得交易詳情頁面，狀態碼: {tx_response.status_code}")
        sys.exit()
    tx_response.encoding = 'utf-8'
    tx_soup = BeautifulSoup(tx_response.text, 'html.parser')

    # 尋找所有 list-group-item，解析地址與金額
    tx_items = tx_soup.find_all("li", class_="list-group-item")
    for item in tx_items:
        # 尋找地址
        addr_a = item.find("a", href=re.compile(r"^/\?&search=scash1"))
        if addr_a:
            # 取得完整地址（不截斷）
            address = addr_a['href']
            # 從 href 取得 search 參數值
            match = re.search(r"search=(scash1[0-9a-zA-Z]+)", address)
            if match:
                full_address = match.group(1)
            else:
                full_address = addr_a.get_text(strip=True)
            # 尋找金額
            amount_span = item.find("span", class_="text-muted spent")
            if amount_span:
                amount_text = amount_span.get_text(strip=True)
                amount_match = re.search(r"([\d\.]+)\s*SCASH", amount_text)
                if amount_match:
                    amount = amount_match.group(1)
                    print(f"地址: {full_address}  轉帳金額: {amount} SCASH")
else:
    print("未找到對應的 txid，無法查詢地址")

## 查詢地址目前持有的 SCASH 數量
def get_address_balance(address):
    url = f"https://scash.one/?search={address}&utxolookup=1"
    resp = requests.get(url)
    if resp.status_code != 200:
        print(f"查詢地址失敗，狀態碼: {resp.status_code}")
        return None
    resp.encoding = 'utf-8'
    soup = BeautifulSoup(resp.text, 'html.parser')
    total_div = soup.find("div", class_="totalamount")
    if not total_div:
        print("找不到總餘額區塊")
        return None
    match = re.search(r"Total unspent SCASH:\s*([\d\.]+)", total_div.get_text())
    if not match:
        print("無法解析總餘額")
        return None
    return match.group(1)

# 範例：查詢 full_address 的餘額
if 'full_address' in locals():
    balance = get_address_balance(full_address)
    if balance is not None:
        print(f"地址 {full_address} 目前持有 SCASH: {balance}")
