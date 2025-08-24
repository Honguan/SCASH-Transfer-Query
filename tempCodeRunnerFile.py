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
