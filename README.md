## 專案簡介

SCASH Transfer Query 是一個用於查詢 SCASH 區塊鏈資料、篩選大額轉帳，並自動產生可視化 Dashboard 的 Python 專案。資料會儲存於 SQLite 資料庫，並自動匯出為 dashboard_data.js，供前端儀表板即時展示。

## 功能

- 查詢並篩選大額 SCASH 區塊鏈轉帳記錄。
- 資料自動儲存於 SQLite 資料庫，並可匯出為 dashboard_data.js。
- 提供自動化排程，定時更新 dashboard 資料。
- 前端 Dashboard（index.html）可即時載入最新資料，支援 GitHub Pages 靜態部署。
- 現代化深色主題、圓餅圖、可摺疊排行榜、轉帳紀錄表格。

## 安裝與使用


### 1. 環境需求

- Python 3.10 或以上版本
- 已安裝以下 Python 套件：
  - `requests`
  - `beautifulsoup4`

安裝所需套件：

```bash
pip3 install beautifulsoup4 flask flask_cors

```


### 2. 設定檔

在 `config.py` 中可調整以下參數：

- `BLOCK_HEIGHT`: 查詢起始區塊高度
- `THRESHOLD`: 大額轉帳的閾值（單位：SCASH）
- `BASE_URL`: SCASH 區塊鏈的基礎 URL
- `DB_FILE`: 資料儲存用 SQLite 檔案名稱
- `SHOW_RESULT`: 是否顯示查詢結果
- `SCAN_INTERVAL`: 自動查詢間隔秒數


### 3. 執行主程式

在終端機中執行：

```bash
python3 SCASH\ Transfer.py
```

依照指示選擇自動查詢或手動查詢模式。


## 資料儲存與匯出

- `scash_data.db`：所有區塊、交易、地址餘額等資料皆儲存於 SQLite 資料庫。
- `export_dashboard_data.py`：將資料庫內容匯出為 `dashboard_data.js`，供前端儀表板載入。
- `dashboard_data.js`：自動產生，包含 addressBalances 與 txRecords 兩個 JS 變數。


## 前端 Dashboard

- `index.html`：主儀表板頁面，建議搭配 GitHub Pages 或其他靜態網頁伺服器部署。
- `assets/dashboard.css`：所有樣式皆集中於此。
- `assets/dashboard_data.js`：由 export_dashboard_data.py 產生，務必與 index.html 同目錄或 assets 目錄下。

### 自動化與部署

- 建議將 `export_dashboard_data.py` 以排程（如 Windows 工作排程、Linux crontab）每 10 分鐘執行一次，確保 dashboard 資料即時更新。
- 若部署於 GitHub Pages，請確保 `index.html` 為首頁，且 `assets/dashboard_data.js` 會隨資料更新自動覆蓋。


## 貢獻

歡迎提交問題、建議或 Pull Request。


## 授權

本專案採用 MIT 授權條款。

---

## 支持本專案

SCASH 捐贈地址：

`scash1qxz7d3gf9yhequz4v9h0tqkcrrlv5a4nps9dlzn`

![SCASH 捐贈地址](assets/scash.png)
