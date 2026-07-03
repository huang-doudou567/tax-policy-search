#!/usr/bin/env python3
"""
Fetch tax law search results from NPC API for 12 tax types.
Saves JSON to docs/data/ for GitHub Pages to serve statically.
"""
import json
import os
import sys
import time
import requests
import urllib3
urllib3.disable_warnings()

BASE_URL = "https://flk.npc.gov.cn"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://flk.npc.gov.cn/",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
}

TAX_SEARCHES = [
    {"keyword": "增值税", "type": "增值税"},
    {"keyword": "企业所得税", "type": "企业所得税"},
    {"keyword": "个人所得税", "type": "个人所得税"},
    {"keyword": "消费税", "type": "消费税"},
    {"keyword": "关税", "type": "关税"},
    {"keyword": "房产税", "type": "房产税"},
    {"keyword": "印花税", "type": "印花税"},
    {"keyword": "契税", "type": "契税"},
    {"keyword": "土地增值税", "type": "土地增值税"},
    {"keyword": "税收优惠", "type": "税收优惠"},
    {"keyword": "发票管理办法", "type": "发票管理"},
    {"keyword": "税收征收管理法", "type": "税收征管"},
]

# Additional detailed topic searches (fulltext)
TOPIC_SEARCHES = [
    {"keyword": "小微企业 企业所得税 优惠", "type": "小微企业优惠", "scope": "fulltext"},
    {"keyword": "高新技术企业 企业所得税 优惠", "type": "高新技术企业优惠", "scope": "fulltext"},
    {"keyword": "研发费用 加计扣除", "type": "研发费用加计扣除", "scope": "fulltext"},
    {"keyword": "虚开发票 风险", "type": "虚开发票风险", "scope": "fulltext"},
    {"keyword": "留抵退税", "type": "留抵退税", "scope": "fulltext"},
    {"keyword": "出口退税", "type": "出口退税", "scope": "fulltext"},
    {"keyword": "个人 专项附加扣除", "type": "专项附加扣除", "scope": "fulltext"},
    {"keyword": "金税四期 风险指标", "type": "金税四期风险", "scope": "fulltext"},
]

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "data")
os.makedirs(DATA_DIR, exist_ok=True)

idx = {"updated": time.strftime("%Y-%m-%d %H:%M:%S"), "searches": {}}

def search_npc(keyword, scope="title", size=30, status=3):
    """Call NPC API and return results."""
    search_range = 2 if scope == "fulltext" else 1
    sxx = [status] if status is not None else []
    payload = {
        "searchRange": search_range,
        "searchType": 2,  # fuzzy
        "searchContent": keyword,
        "pageNum": 1,
        "pageSize": min(size, 50),
        "orderByParam": {"order": "", "sort": ""},
        "flfgCodeId": [],
        "zdjgCodeId": [],
        "sxx": sxx,
        "gbrq": [],
        "sxrq": [],
        "gbrqYear": [],
        "xgzlSearch": False,
    }
    r = requests.post(f"{BASE_URL}/law-search/search/list",
                      json=payload, headers=HEADERS, timeout=20)
    r.raise_for_status()
    data = r.json()
    outer = data.get("data", data)
    rows = outer.get("rows", outer.get("list", []))
    results = []
    for item in rows:
        results.append({
            "id": item.get("bbbs", ""),
            "title": (item.get("flfgname", item.get("title", "")) or "").replace("<em>", "").replace("</em>", ""),
            "publish_date": item.get("gbrq", ""),
            "effective_date": item.get("sxrq", ""),
            "status_code": item.get("sxx", 0),
            "issuing_authority": item.get("zdjgName", ""),
            "category": item.get("flxz", ""),
        })
    return {"total": outer.get("total", 0), "results": results}

# Fetch title searches for 12 tax types
print("Fetching 12 tax type searches...")
for i, item in enumerate(TAX_SEARCHES):
    key = f"tax_{item['type']}"
    try:
        print(f"  [{i+1}/{len(TAX_SEARCHES)}] {item['keyword']}...", end=" ")
        data = search_npc(item['keyword'], size=30)
        print(f"{data['total']} results")
        idx["searches"][key] = {
            "keyword": item['keyword'],
            "type": item['type'],
            "scope": "title",
            **data,
        }
    except Exception as e:
        print(f"FAILED: {e}")
        idx["searches"][key] = {"error": str(e)}
    time.sleep(0.5)

# Fetch full-text topic searches
print("\nFetching 8 topic searches...")
for i, item in enumerate(TOPIC_SEARCHES):
    key = f"topic_{item['type']}"
    try:
        print(f"  [{i+1}/{len(TOPIC_SEARCHES)}] {item['keyword']}...", end=" ")
        data = search_npc(item['keyword'], scope=item.get("scope", "fulltext"), size=30)
        print(f"{data['total']} results")
        idx["searches"][key] = {
            "keyword": item['keyword'],
            "type": item['type'],
            "scope": item.get("scope", "fulltext"),
            **data,
        }
    except Exception as e:
        print(f"FAILED: {e}")
        idx["searches"][key] = {"error": str(e)}
    time.sleep(0.5)

# Write index file
index_path = os.path.join(DATA_DIR, "index.json")
with open(index_path, "w", encoding="utf-8") as f:
    json.dump(idx, f, ensure_ascii=False, indent=2)
print(f"\nWrote: {index_path} ({os.path.getsize(index_path)} bytes)")

# Write individual files for faster loading
for key, val in idx["searches"].items():
    fpath = os.path.join(DATA_DIR, f"{key}.json")
    with open(fpath, "w", encoding="utf-8") as f:
        json.dump({"updated": idx["updated"], **val}, f, ensure_ascii=False, indent=2)
    print(f"  {fpath}: {os.path.getsize(fpath)} bytes")

print("\nDone!")
