#!/usr/bin/env python3
"""
Tax Policy Aggregator — concurrent multi-source search with dedup and ranking.

Data source priority:
  1. NPC API (flk.npc.gov.cn) — laws, administrative regulations (highest authority)
  2. chinatax.gov.cn — STA announcements, policy interpretations
  3. AnySearch legal domain — supplementary web results

Usage:
  python tax_aggregator.py "增值税" --size 10
  python tax_aggregator.py "小微企业优惠" --size 10 --json
  python tax_aggregator.py "加计扣除" --sources npc,chinatax  # NPC + chinatax only
"""

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Import sibling modules
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from tax_search import search_tax
from tax_web_search import search_chinatax


def _anysearch_fallback(keyword: str, size: int = 5) -> list:
    """
    Attempt AnySearch via its CLI if available.
    Falls back gracefully if not configured.
    """
    anysearch_dir = Path.home() / ".claude" / "skills" / "anysearch" / "scripts"
    cli_py = anysearch_dir / "anysearch_cli.py"

    if not cli_py.exists():
        return []

    import subprocess
    try:
        result = subprocess.run(
            ["python3", str(cli_py), "search", keyword,
             "--domain", "legal", "--max_results", str(size)],
            capture_output=True, text=True, timeout=20,
            cwd=str(anysearch_dir.parent),
        )
        if result.returncode == 0 and result.stdout.strip():
            # Try to parse the output (it's JSON)
            try:
                data = json.loads(result.stdout)
                return _normalize_anysearch(data, keyword)
            except json.JSONDecodeError:
                # Return raw output as single pseudo-result
                lines = result.stdout.strip().split("\n")[:size]
                return [{"title": l[:100], "url": "", "source": "AnySearch"} for l in lines if l.strip()]
    except Exception:
        pass

    return []


def _normalize_anysearch(data: dict, keyword: str) -> list:
    """Normalize AnySearch output to standard format."""
    results = []
    items = data.get("results", data.get("data", []))
    if isinstance(items, list):
        for item in items[:10]:
            results.append({
                "title": item.get("title", item.get("name", str(item)[:80])),
                "url": item.get("url", item.get("link", "")),
                "snippet": item.get("snippet", item.get("summary", "")),
                "source": "AnySearch",
            })
    return results


def _jaccard_similarity(s1: str, s2: str) -> float:
    """Simple Jaccard similarity on character trigrams for title dedup."""
    if not s1 or not s2:
        return 0.0

    def trigrams(s):
        s = s.lower().strip()
        return {s[i:i+3] for i in range(len(s) - 2)} if len(s) >= 3 else {s}

    t1 = trigrams(s1)
    t2 = trigrams(s2)
    if not t1 or not t2:
        return 0.0

    intersection = len(t1 & t2)
    union = len(t1 | t2)
    return intersection / union if union > 0 else 0.0


def deduplicate(results: list, threshold: float = 0.7) -> list:
    """Remove near-duplicate results based on title similarity."""
    deduped = []
    for item in results:
        title = item.get("title", "")
        is_dup = False
        for existing in deduped:
            sim = _jaccard_similarity(title, existing.get("title", ""))
            if sim >= threshold:
                is_dup = True
                break
        if not is_dup:
            deduped.append(item)
    return deduped


def aggregate_search(keyword: str, *,
                     size: int = 10,
                     sources: list = None,
                     status: int = 3,
                     scope: str = "fulltext") -> dict:
    """
    Concurrently search multiple data sources and return deduplicated, ranked results.

    Args:
        keyword: search term
        size: results per source
        sources: list of source names ('npc', 'chinatax', 'anysearch'). Default: all three.
        status: NPC status filter (default: 3 = effective)
        scope: NPC search scope (default: fulltext)
    """
    if sources is None:
        sources = ["npc", "chinatax", "anysearch"]

    results = {}
    errors = {}

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {}

        if "npc" in sources:
            futures["npc"] = pool.submit(
                search_tax, keyword, scope=scope, status=status, size=size
            )
        if "chinatax" in sources:
            futures["chinatax"] = pool.submit(
                search_chinatax, keyword, size=size
            )
        if "anysearch" in sources:
            futures["anysearch"] = pool.submit(
                _anysearch_fallback, keyword, min(size, 5)
            )

        for source, future in futures.items():
            try:
                results[source] = future.result(timeout=20)
            except Exception as e:
                errors[source] = str(e)
                results[source] = None

    # Collect all results
    all_items = []
    source_order = {"npc": 0, "chinatax": 1, "anysearch": 2}

    # NPC results first (highest authority)
    npc_data = results.get("npc")
    if npc_data and npc_data.get("total", 0) > 0:
        for item in npc_data.get("results", []):
            item["_source"] = "npc"
            item["_authority_rank"] = 0
            all_items.append(item)

    # chinatax results second
    chinatax_data = results.get("chinatax")
    if chinatax_data and chinatax_data.get("total", 0) > 0:
        for item in chinatax_data.get("results", []):
            item["_source"] = "chinatax"
            item["_authority_rank"] = 1
            # Normalize: chinatax uses date not publish_date
            if "date" in item and "publish_date" not in item:
                item["publish_date"] = item["date"]
            all_items.append(item)

    # AnySearch results last
    anysearch_data = results.get("anysearch")
    if isinstance(anysearch_data, list) and anysearch_data:
        for item in anysearch_data:
            item["_source"] = "anysearch"
            item["_authority_rank"] = 2
            all_items.append(item)

    # Deduplicate across sources
    all_items = deduplicate(all_items)

    # Sort: authority rank first, then by date
    all_items.sort(key=lambda x: (
        x.get("_authority_rank", 99),
        # Put items with dates before those without
        0 if x.get("publish_date") else 1,
    ))

    return {
        "keyword": keyword,
        "total_sources": len(sources),
        "total_items": len(all_items),
        "items": all_items[:size * 3],  # Cap total results
        "source_summary": {
            "npc": npc_data.get("total", 0) if npc_data else 0,
            "chinatax": chinatax_data.get("total", 0) if chinatax_data else 0,
            "anysearch": len(anysearch_data) if isinstance(anysearch_data, list) else 0,
        },
        "errors": errors,
        "searched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


# ── CLI ─────────────────────────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(
        description="Multi-source tax policy search aggregator",
        epilog="""
Examples:
  python tax_aggregator.py "增值税" --size 10
  python tax_aggregator.py "加计扣除" --sources npc,chinatax --json
        """
    )
    p.add_argument("keyword", help="Search keyword")
    p.add_argument("--size", type=int, default=10)
    p.add_argument("--sources", default="npc,chinatax,anysearch",
                   help="Comma-separated source names (default: npc,chinatax,anysearch)")
    p.add_argument("--status", type=int, default=3,
                   help="NPC status filter (3=effective)")
    p.add_argument("--scope", choices=["title", "fulltext"], default="fulltext")
    p.add_argument("--json", action="store_true")

    args = p.parse_args()
    sources = [s.strip() for s in args.sources.split(",") if s.strip()]

    result = aggregate_search(
        args.keyword,
        size=args.size,
        sources=sources,
        status=args.status,
        scope=args.scope,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print(f"🔍 多源搜索 \"{args.keyword}\" | {result['searched_at']}")
    print(f"   数据源: {', '.join(sources)}")
    print(f"   NPC: {result['source_summary'].get('npc', 0)} 条")
    print(f"   税务总局: {result['source_summary'].get('chinatax', 0)} 条")
    print(f"   网页补充: {result['source_summary'].get('anysearch', 0)} 条")
    if result.get("errors"):
        for src, err in result["errors"].items():
            print(f"   ⚠️ {src}: {err}")
    print()

    source_labels = {"npc": "📜 NPC法规库", "chinatax": "🏛️ 国家税务总局", "anysearch": "🌐 网页补充"}
    for item in result.get("items", [])[:20]:
        src = item.get("_source", "")
        label = source_labels.get(src, "")
        print(f"  {label} {item.get('title', '')[:80]}")
        if item.get("publish_date"):
            print(f"     日期: {item['publish_date']}")
        if item.get("id"):
            print(f"     NPC ID: {item['id']}")
        if item.get("url"):
            print(f"     {item['url']}")
        print()


if __name__ == "__main__":
    main()
