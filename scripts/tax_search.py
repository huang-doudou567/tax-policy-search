#!/usr/bin/env python3
"""
Tax Policy Search — search China tax laws/regulations via NPC API (flk.npc.gov.cn).

Usage:
  # Title search (default)
  python tax_search.py "增值税" --size 20
  # Full-text search, effective only
  python tax_search.py "小微企业优惠" --scope fulltext --status 3
  # Exact title search
  python tax_search.py "中华人民共和国增值税法" --exact
  # Date range + sort by publish date
  python tax_search.py "企业所得税" --scope fulltext --status 3 --from 2024-01-01 --sort date
  # Verbose output (includes article snippets)
  python tax_search.py "加计扣除" --scope fulltext --status 3 --verbose
  # Enable cache (5min TTL)
  python tax_search.py "增值税" --cache
  # JSON output for piping
  python tax_search.py "个人所得税" --json
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

# Fix Windows console encoding
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ── Constants ───────────────────────────────────────────────────────────────
BASE_URL = "https://flk.npc.gov.cn"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://flk.npc.gov.cn/",
    "Accept": "application/json, text/plain, */*",
}
VERIFY_SSL = os.getenv("TAX_SEARCH_VERIFY_SSL", "0") == "1"

# Status code mapping
SXX_MAP = {1: "已废止", 2: "已修改", 3: "现行有效", 4: "尚未生效"}
SXX_REVERSE = {v: k for k, v in SXX_MAP.items()}

# ── Cache (disabled by default, short TTL when enabled) ─────────────────────
class _CacheManager:
    """Lightweight JSON file cache. Disabled by default."""
    def __init__(self, enabled: bool = False):
        self._enabled = enabled
        self.dir = Path.home() / ".cache" / "tax-policy-search"

    def _key(self, *parts: str) -> str:
        raw = "|".join(str(p) for p in parts)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _path(self, key: str) -> Path:
        return self.dir / f"{key}.json"

    def get(self, key: str, max_age: float = 300) -> Optional[dict]:
        if not self._enabled:
            return None
        p = self._path(key)
        if not p.exists():
            return None
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if time.time() - data.get("_cached_at", 0) > max_age:
                return None
            return data.get("payload")
        except Exception:
            return None

    def set(self, key: str, payload: dict) -> None:
        if not self._enabled:
            return
        self.dir.mkdir(parents=True, exist_ok=True)
        p = self._path(key)
        p.write_text(
            json.dumps({"_cached_at": time.time(), "payload": payload}, ensure_ascii=False),
            encoding="utf-8"
        )

    def clear(self) -> None:
        if self.dir.exists():
            for f in self.dir.glob("*.json"):
                f.unlink()
            return True
        return False

    def stats(self) -> dict:
        if not self.dir.exists():
            return {"entries": 0, "size_kb": 0}
        files = list(self.dir.glob("*.json"))
        return {
            "entries": len(files),
            "size_kb": round(sum(f.stat().st_size for f in files) / 1024, 1)
        }

_cache = _CacheManager(enabled=False)


# ── 18 Tax Types → Search Keyword Mapping ───────────────────────────────────
TAX_TYPE_KEYWORDS = {
    # 流转税
    "增值税": {
        "aliases": ["增值税", "VAT", "进项税", "销项税", "留抵退税", "增值税专用发票", "增值税普通发票"],
        "parent_law": "中华人民共和国增值税法",
        "priority": 1,
    },
    "消费税": {
        "aliases": ["消费税", "卷烟", "成品油", "汽车消费税"],
        "parent_law": "中华人民共和国消费税法",
        "priority": 2,
    },
    "关税": {
        "aliases": ["关税", "进出口税", "反倾销税", "保税", "海关"],
        "parent_law": "中华人民共和国关税法",
        "priority": 3,
    },
    # 所得税
    "企业所得税": {
        "aliases": ["企业所得税", "应税所得", "税前扣除", "加计扣除", "高新技术企业", "小微企业", "西部大开发"],
        "parent_law": "中华人民共和国企业所得税法",
        "priority": 1,
    },
    "个人所得税": {
        "aliases": ["个人所得税", "综合所得", "专项附加扣除", "年度汇算", "劳务报酬", "经营所得"],
        "parent_law": "中华人民共和国个人所得税法",
        "priority": 1,
    },
    # 财产行为税
    "房产税": {
        "aliases": ["房产税", "房地产税", "房屋租赁税"],
        "parent_law": "中华人民共和国房产税暂行条例",
        "priority": 4,
    },
    "土地增值税": {
        "aliases": ["土地增值税", "土增税", "清算"],
        "parent_law": "中华人民共和国土地增值税暂行条例",
        "priority": 4,
    },
    "契税": {
        "aliases": ["契税", "不动产登记"],
        "parent_law": "中华人民共和国契税法",
        "priority": 4,
    },
    "城镇土地使用税": {
        "aliases": ["城镇土地使用税", "土地使用税"],
        "parent_law": "中华人民共和国城镇土地使用税暂行条例",
        "priority": 4,
    },
    "车船税": {
        "aliases": ["车船税", "车辆购置税"],
        "parent_law": "中华人民共和国车船税法",
        "priority": 5,
    },
    "印花税": {
        "aliases": ["印花税", "合同印花税", "账簿印花税"],
        "parent_law": "中华人民共和国印花税法",
        "priority": 4,
    },
    "城市维护建设税": {
        "aliases": ["城市维护建设税", "城建税", "教育费附加", "地方教育附加"],
        "parent_law": "中华人民共和国城市维护建设税法",
        "priority": 4,
    },
    # 资源环境税
    "资源税": {
        "aliases": ["资源税", "水资源税", "矿产资源税"],
        "parent_law": "中华人民共和国资源税法",
        "priority": 4,
    },
    "环境保护税": {
        "aliases": ["环境保护税", "环保税", "排污税"],
        "parent_law": "中华人民共和国环境保护税法",
        "priority": 4,
    },
    # 其他
    "税收征管": {
        "aliases": ["税收征收管理", "税务登记", "纳税申报", "发票管理", "发票", "税务稽查", "金税四期"],
        "parent_law": "中华人民共和国税收征收管理法",
        "priority": 1,
    },
    "税收优惠": {
        "aliases": ["税收优惠", "减免税", "退税", "即征即退", "先征后退", "免税"],
        "parent_law": None,
        "priority": 1,
    },
}

TAX_RISK_KEYWORDS = [
    "虚开发票", "骗取留抵退税", "骗取出口退税", "偷税", "逃税", "避税",
    "关联交易", "转让定价", "税收风险", "税务合规", "金税四期指标",
    "两税收入差异", "长亏不倒", "税负率异常", "资金闭环回流",
    "进销项不匹配", "四流合一", "私户收款", "账外经营",
]

INVOICE_KEYWORDS = [
    "增值税发票", "专用发票", "普通发票", "电子发票", "全电发票",
    "发票管理办法", "发票领购", "发票开具", "发票红冲", "发票遗失",
    "发票抵扣", "发票认证", "数电票",
]


def resolve_tax_type(query: str) -> dict:
    """Resolve user query to best-matching tax type."""
    q = query.strip()
    best = None
    best_len = 0
    for tax_type, info in TAX_TYPE_KEYWORDS.items():
        for alias in info["aliases"]:
            if alias in q and len(alias) > best_len:
                best = {"type": tax_type, "matched_alias": alias, **info}
                best_len = len(alias)
    return best


def detect_intent(query: str) -> str:
    """
    Classify user intent to determine search strategy.
    Returns: 'policy_lookup' | 'filing_guide' | 'risk_check' | 'eligibility' | 'invoice'
    """
    q = query.strip()

    # Invoice-related
    if any(kw in q for kw in ["发票", "开票", "红冲", "抵扣认证", "发票遗失"]):
        return "invoice"

    # Risk check
    risk_signals = ["风险", "会不会被查", "预警", "金税", "合规", "稽查", "会被罚款", "合规吗", "违规"]
    if any(kw in q for kw in risk_signals):
        return "risk_check"

    # Filing guide
    filing_signals = ["申报", "汇算清缴", "截止日期", "怎么申报", "年度汇算", "预缴", "报送", "备案"]
    if any(kw in q for kw in filing_signals):
        return "filing_guide"

    # Eligibility check
    eligibility_signals = ["符合条件", "能不能享受", "符不符合", "是否适用",
                           "可以抵扣吗", "适用吗", "资格", "能享受", "可以享受"]
    if any(kw in q for kw in eligibility_signals):
        return "eligibility"

    # Default: policy lookup
    return "policy_lookup"


# ── NPC API Client ──────────────────────────────────────────────────────────
def _request(method: str, url: str, **kwargs) -> requests.Response:
    """Wrapper with retry for 429."""
    max_retries = 3
    for attempt in range(max_retries):
        r = requests.request(method, url, verify=VERIFY_SSL, headers=HEADERS, timeout=15, **kwargs)
        if r.status_code == 429:
            wait = 2 ** (attempt + 1)
            time.sleep(wait)
            continue
        if r.status_code in {500, 502, 503} and attempt < max_retries - 1:
            time.sleep(1)
            continue
        return r
    return r


def search_tax(keyword: str, *,
               scope: str = "title",
               search_type: int = 2,
               status: Optional[int] = 3,
               date_from: Optional[str] = None,
               date_to: Optional[str] = None,
               page: int = 1,
               size: int = 20,
               sort: str = "relevance") -> dict:
    """
    Search tax policies via NPC API.

    Args:
        keyword: search term
        scope: 'title' (searchRange=1) or 'fulltext' (searchRange=2)
        search_type: 1=exact, 2=fuzzy
        status: None=all, 3=effective, or any sxx code
        date_from: ISO date string e.g. '2024-01-01'
        date_to: ISO date string e.g. '2026-12-31'
        page: page number
        size: results per page (max 100)
        sort: 'relevance' or 'date'
    """
    search_range = 1 if scope == "title" else 2
    sxx = [status] if status is not None else []
    gbrq = []
    if date_from and date_to:
        gbrq = [date_from, date_to]
    elif date_from:
        gbrq = [date_from, "2099-12-31"]

    sort_param = {"order": "", "sort": ""}
    if sort == "date":
        sort_param = {"order": "-1", "sort": "gbrq"}

    cache_key = _cache._key(
        "search", keyword, str(search_range), str(search_type),
        str(status), str(date_from), str(date_to), str(page), str(size), sort
    )
    cached = _cache.get(cache_key, max_age=300)
    if cached:
        cached["_from_cache"] = True
        return cached

    payload = {
        "searchRange": search_range,
        "searchType": search_type,
        "searchContent": keyword,
        "pageNum": page,
        "pageSize": min(size, 100),
        "orderByParam": sort_param,
        "flfgCodeId": [],
        "zdjgCodeId": [],
        "sxx": sxx,
        "gbrq": gbrq,
        "sxrq": [],
        "gbrqYear": [],
        "xgzlSearch": False,
    }

    r = _request("POST", f"{BASE_URL}/law-search/search/list", json=payload)
    r.raise_for_status()
    data = r.json()
    outer = data.get("data", data)
    total = outer.get("total", 0)
    rows = outer.get("rows", outer.get("list", []))

    # Clean HTML tags from names
    _clean_re = re.compile(r"<[^>]+>")
    def clean_html(s):
        return _clean_re.sub("", s) if s else ""

    results = []
    for item in rows:
        sxx_code = item.get("sxx", 0)
        results.append({
            "id": item.get("bbbs", ""),
            "title": clean_html(item.get("flfgname", item.get("title", ""))),
            "publish_date": item.get("gbrq", ""),
            "effective_date": item.get("sxrq", ""),
            "status_code": sxx_code,
            "status": SXX_MAP.get(sxx_code, f"未知({sxx_code})"),
            "issuing_authority": item.get("zdjgName", ""),
            "category": item.get("flxz", ""),
        })

    result = {
        "keyword": keyword,
        "scope": scope,
        "search_type": "exact" if search_type == 1 else "fuzzy",
        "total": total,
        "page": page,
        "page_size": size,
        "results": results,
        "searched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "_from_cache": False,
    }

    _cache.set(cache_key, result)
    return result


def search_tax_full(keyword: str, **kwargs) -> dict:
    """Two-phase search: title-first, fallback to fulltext if insufficient."""
    title_kwargs = {**kwargs, "scope": "title", "size": min(kwargs.get("size", 20), 20)}
    result = search_tax(keyword, **title_kwargs)
    if result["total"] == 0:
        fulltext_kwargs = {**kwargs, "scope": "fulltext"}
        return search_tax(keyword, **fulltext_kwargs)
    return result


# ── CLI ─────────────────────────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Search China tax policies via NPC National Laws Database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tax_search.py "增值税" --size 20
  python tax_search.py "小微企业优惠" --scope fulltext --status 3
  python tax_search.py "中华人民共和国增值税法" --exact
  python tax_search.py "企业所得税" --scope fulltext --from 2024-01-01 --sort date
  python tax_search.py "研发费用加计扣除" --verbose --json
  python tax_search.py "增值税" --cache
  python tax_search.py --cache-clear
  python tax_search.py --cache-stats
        """
    )
    p.add_argument("keyword", nargs="?", help="Search keyword")
    p.add_argument("--scope", choices=["title", "fulltext"], default="title",
                   help="Search scope (default: title)")
    p.add_argument("--exact", action="store_true",
                   help="Exact title match (default: fuzzy)")
    p.add_argument("--status", type=int, default=3,
                   help="Status filter: 1=abolished, 2=amended, 3=effective, 4=pending. Omit for all.")
    p.add_argument("--from", dest="date_from", help="Publish date from (YYYY-MM-DD)")
    p.add_argument("--to", dest="date_to", help="Publish date to (YYYY-MM-DD)")
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--size", type=int, default=20)
    p.add_argument("--sort", choices=["relevance", "date"], default="relevance")
    p.add_argument("--json", action="store_true", help="Output JSON")
    p.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    p.add_argument("--cache", action="store_true", help="Enable cache (5min TTL)")
    p.add_argument("--no-cache", action="store_true", help="Disable cache")
    p.add_argument("--cache-stats", action="store_true", help="Show cache stats")
    p.add_argument("--cache-clear", action="store_true", help="Clear cache")
    p.add_argument("--two-phase", action="store_true",
                   help="Title-first, fallback to fulltext if no results")
    return p


def main():
    parser = build_parser()
    args = parser.parse_args()

    global _cache

    # Cache management
    if args.cache:
        _cache = _CacheManager(enabled=True)
    elif args.no_cache:
        _cache = _CacheManager(enabled=False)

    if args.cache_stats:
        s = _cache.stats()
        print(json.dumps({"cache": s}, ensure_ascii=False, indent=2))
        return
    if args.cache_clear:
        _cache.clear()
        print("Cache cleared.")
        return

    if not args.keyword:
        parser.print_help()
        return

    search_fn = search_tax_full if args.two_phase else search_tax
    result = search_fn(
        args.keyword,
        scope=args.scope if not args.exact else "title",
        search_type=1 if args.exact else 2,
        status=args.status,
        date_from=args.date_from,
        date_to=args.date_to,
        page=args.page,
        size=args.size,
        sort=args.sort,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # Human-readable output
    status_icon = {1: "🔴", 2: "🟡", 3: "🟢", 4: "🔵"}
    cache_tag = " [缓存]" if result.get("_from_cache") else ""
    print(f"🔍 搜索 \"{args.keyword}\" | {args.scope}/{result['search_type']} | "
          f"共 {result['total']} 条 | {result['searched_at']}{cache_tag}")
    print()

    for item in result["results"]:
        icon = status_icon.get(item["status_code"], "❓")
        print(f"  {icon} [{item['status']}] {item['title']}")
        if args.verbose:
            print(f"     公布: {item['publish_date']}  施行: {item['effective_date']}")
            print(f"     发布机关: {item['issuing_authority']}")
            print(f"     分类: {item['category']}   ID: {item['id']}")
        else:
            print(f"     公布: {item['publish_date']}  ID: {item['id']}")
        print()

    if result["total"] > args.size:
        total_pages = (result["total"] + args.size - 1) // args.size
        print(f"  📄 第 {args.page}/{total_pages} 页，共 {result['total']} 条")


if __name__ == "__main__":
    main()
