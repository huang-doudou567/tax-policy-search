#!/usr/bin/env python3
"""
Tax Web Search — scrape chinatax.gov.cn as fallback for department-level regulations.

chinatax.gov.cn hosts State Taxation Administration (STA) announcements, policy
interpretations, and operational guides that are NOT in the NPC law database.

Usage:
  python tax_web_search.py "增值税" --size 10
  python tax_web_search.py "小微企业优惠" --size 10 --json
"""

import argparse
import json
import re
import sys
import time
from typing import Optional
from urllib.parse import quote, urljoin

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://www.chinatax.gov.cn"
# chinatax uses WAS (Web Application Server) search engine
SEARCH_URL = f"{BASE_URL}/was5/web/search"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}
TIMEOUT = 15


def search_chinatax(keyword: str, page: int = 1, size: int = 10) -> dict:
    """
    Search chinatax.gov.cn for tax policy documents via WAS search engine.

    Returns a dict with the same structure as tax_search.search_tax().
    """
    from urllib.parse import quote

    # chinatax uses WAS5 search: /was5/web/search
    params = {
        "searchword": keyword,
        "keyword": keyword,
        "perpage": str(size),
        "page": str(page),
        "orderby": "-crtime",  # newest first
    }

    url = f"{SEARCH_URL}?{'&'.join(f'{k}={quote(str(v))}' for k, v in params.items())}"
    results = []

    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code != 200:
            # Fallback: try Baidu site-search (some chinatax pages use this)
            return _baidu_site_search(keyword, size)

        html = r.text

        # --- Tolerant HTML parsing ---
        # Strategy: extract all <a> tags with href containing "chinatax.gov.cn"
        # that appear in search result blocks. Uses regex to survive site redesigns.

        # Pattern 1: Search result links (typical format)
        link_pattern = re.compile(
            r'<a[^>]*href="([^"]*chinatax\.gov\.cn[^"]*)"[^>]*>'
            r'(.*?)</a>',
            re.DOTALL | re.IGNORECASE
        )
        # Pattern 2: Date extraction (various formats)
        date_pattern = re.compile(
            r'(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)'
        )

        # Extract result blocks — typically <li> or <div class="result">
        blocks = re.findall(
            r'<(?:li|div)[^>]*(?:class="[^"]*result[^"]*"|class="[^"]*item[^"]*")[^>]*>'
            r'(.*?)</(?:li|div)>',
            html, re.DOTALL | re.IGNORECASE
        )

        if not blocks:
            # Fallback: look for any <li> or <div> with links
            blocks = re.findall(
                r'<(?:li|div)[^>]*>(.*?)</(?:li|div)>',
                html, re.DOTALL
            )
            # Filter to blocks containing chinatax.gov.cn links
            blocks = [b for b in blocks if "chinatax.gov.cn" in b]

        seen_urls = set()
        for block in blocks:
            links = link_pattern.findall(block)
            for href, title_raw in links:
                href = urljoin(BASE_URL, href.strip())
                if href in seen_urls:
                    continue
                seen_urls.add(href)

                # Clean title — remove HTML tags
                title = re.sub(r"<[^>]+>", "", title_raw).strip()
                if len(title) < 5:
                    continue

                # Extract date
                date_match = date_pattern.search(block)
                date_str = date_match.group(1) if date_match else ""
                date_str = date_str.replace("年", "-").replace("月", "-").replace("日", "")

                # Extract document number (e.g., 国家税务总局公告2024年第1号)
                doc_num = ""
                doc_match = re.search(
                    r'(国家税务总局公告\d{4}年第\d+号|'
                    r'财税\[\d{4}\]\d+号|'
                    r'税总发\[\d{4}\]\d+号|'
                    r'财政部税务总局\d{4}年第\d+号)',
                    block
                )
                if doc_match:
                    doc_num = doc_match.group(1)

                results.append({
                    "title": title,
                    "url": href,
                    "date": date_str,
                    "document_number": doc_num,
                    "source": "chinatax.gov.cn",
                })

                if len(results) >= size:
                    break
            if len(results) >= size:
                break

    except requests.RequestException as e:
        return _empty_result(keyword, str(e))

    return {
        "keyword": keyword,
        "total": len(results),
        "results": results,
        "searched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": "chinatax.gov.cn",
        "_from_cache": False,
    }


def _empty_result(keyword: str, error: str = "") -> dict:
    return {
        "keyword": keyword,
        "total": 0,
        "results": [],
        "searched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "source": "chinatax.gov.cn",
        "_error": error,
        "_from_cache": False,
    }


def _baidu_site_search(keyword: str, size: int = 10) -> dict:
    """Fallback: use Baidu site search for chinatax.gov.cn."""
    from urllib.parse import quote
    baidu_url = f"https://www.baidu.com/s?wd=site%3Achinatax.gov.cn+{quote(keyword)}&rn={size}"
    try:
        r = requests.get(baidu_url, headers={**HEADERS, "Accept-Language": "zh-CN,zh;q=0.9"},
                         timeout=TIMEOUT)
        if r.status_code != 200:
            return _empty_result(keyword, f"Baidu fallback HTTP {r.status_code}")

        html = r.text
        results = []
        # Baidu search result parsing — tolerant regex
        link_pattern = re.compile(
            r'<a[^>]*href="(https?://[^"]*chinatax\.gov\.cn[^"]*)"[^>]*>'
            r'(.*?)</a>',
            re.DOTALL | re.IGNORECASE
        )
        seen = set()
        for href, title_raw in link_pattern.findall(html):
            if href in seen:
                continue
            seen.add(href)
            title = re.sub(r"<[^>]+>", "", title_raw).strip()
            if len(title) < 5:
                continue
            results.append({"title": title, "url": href, "source": "chinatax.gov.cn (Baidu)"})
            if len(results) >= size:
                break

        return {
            "keyword": keyword,
            "total": len(results),
            "results": results,
            "searched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "source": "chinatax.gov.cn (Baidu)",
            "_from_cache": False,
        }
    except requests.RequestException as e:
        return _empty_result(keyword, str(e))


# ── CLI ─────────────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(
        description="Search chinatax.gov.cn for tax policy documents"
    )
    p.add_argument("keyword", help="Search keyword")
    p.add_argument("--size", type=int, default=10)
    p.add_argument("--json", action="store_true", help="Output JSON")

    args = p.parse_args()
    result = search_chinatax(args.keyword, size=args.size)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print(f"🔍 chinatax.gov.cn 搜索 \"{args.keyword}\" | {result['searched_at']}")
    if result.get("_error"):
        print(f"⚠️  {result['_error']}")
    print(f"共 {result['total']} 条")
    print()

    for item in result.get("results", []):
        print(f"  📋 {item['title']}")
        if item.get("document_number"):
            print(f"     文号: {item['document_number']}")
        if item.get("date"):
            print(f"     日期: {item['date']}")
        print(f"     {item['url']}")
        print()


if __name__ == "__main__":
    main()
