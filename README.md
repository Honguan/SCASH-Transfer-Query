# SCASH Transfer Query

## 專案簡介

SCASH Transfer Query 是一個用於查詢 SCASH 區塊鏈資料的 Python 腳本。該腳本可以處理區塊資料，篩選大額轉帳，並將結果記錄到 CSV 檔案中。

## 功能

- 支援查詢並篩選大額 SCASH 區塊鏈轉帳記錄。
- 結果自動儲存為 CSV 檔案，方便後續分析。
- 提供彈性設定與錯誤重試機制，提升使用體驗。

## 安裝與使用

### 1. 環境需求

- Python 3.10 或以上版本
- 已安裝以下 Python 套件：

  - `requests`
  - `BeautifulSoup`

安裝所需套件的命令如下：

```bash
pip install requests beautifulsoup4
```

### 2. 設定檔

在 `config.py` 中配置以下參數：

- `BLOCK_HEIGHT`: 指定查詢的區塊高度。
- `THRESHOLD`: 大額轉帳的閾值（單位：SCASH）。
- `BASE_URL`: SCASH 區塊鏈的基礎 URL。
- `CSV_FILE`: 儲存轉帳記錄的檔案名稱。
- `ADDRESS_BALANCE_FILE`: 儲存地址餘額的檔案名稱。
- `SHOW_RESULT`: 是否顯示查詢結果（布林值）。

### 3. 執行腳本

在終端機中執行以下命令：

```bash
python SCASH Transfer.py
```

## 輸出檔案

- `scash_transfer_records.csv`: 儲存篩選後的轉帳記錄。
- `scash_address_balances.csv`: 儲存地址餘額。

## 注意事項

- 如果輸出檔案不存在，腳本會自動生成。
- 請確保網路連線穩定以避免 HTTP 請求失敗。

## 貢獻

歡迎提交問題或功能請求，或直接提交 Pull Request。

## 授權

此專案採用 MIT 授權條款。
