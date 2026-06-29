#!/usr/bin/env python3
"""End-to-end tests for tax-policy-search skill."""
import json
import os
import sys
import time
from pathlib import Path

# Fix Windows console encoding
os.environ["PYTHONIOENCODING"] = "utf-8"

SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from tax_search import search_tax, search_tax_full, resolve_tax_type, detect_intent
from tax_detail import fetch_detail
from tax_web_search import search_chinatax
from tax_formatter import format_search_response

PASS = "PASS"
FAIL = "FAIL"

def test_detect_intent():
    """Test intent classifier."""
    tests = [
        ("增值税税率多少", "policy_lookup"),
        ("怎么申报企业所得税汇算清缴", "filing_guide"),
        ("金税四期会查什么风险", "risk_check"),
        ("我公司能享受小微企业优惠吗", "eligibility"),
        ("增值税专用发票丢了怎么办", "invoice"),
        ("研发费用加计扣除比例", "policy_lookup"),
        ("会不会被税务稽查", "risk_check"),
    ]
    passed = 0
    for query, expected in tests:
        result = detect_intent(query)
        ok = result == expected
        status = PASS if ok else f"{FAIL} (expected {expected})"
        print(f"  [{status}] '{query}' -> {result}")
        if ok:
            passed += 1
    return passed, len(tests)


def test_resolve_tax_type():
    """Test tax type resolver."""
    tests = [
        ("增值税的一般税率是多少", "增值税"),
        ("企业所得税汇算清缴", "企业所得税"),
        ("个人所得税专项附加扣除怎么报", "个人所得税"),
        ("小微企业有什么税收优惠", "企业所得税"),
        ("房产税怎么计算", "房产税"),
        ("发票丢失怎么处理", "税收征管"),
    ]
    passed = 0
    for query, expected in tests:
        result = resolve_tax_type(query)
        ok = result and result["type"] == expected
        got = result['type'] if result else 'None'
        status = PASS if ok else f"{FAIL} (got {got}, expected {expected})"
        print(f"  [{status}] '{query}' -> {got}")
        if ok:
            passed += 1
    return passed, len(tests)


def test_search_title():
    """Test title search with NPC API."""
    print("\n[Test] Title search: VAT")
    result = search_tax("增值税", scope="title", status=3, size=5)
    assert result["total"] > 0, f"Expected >0 results, got {result['total']}"
    assert result["keyword"] == "增值税"
    assert result["scope"] == "title"
    assert result["searched_at"]
    assert len(result["results"]) > 0
    item = result["results"][0]
    assert "id" in item
    assert "title" in item
    assert "status_code" in item
    assert "status" in item
    assert "publish_date" in item
    print(f"  [PASS] Total: {result['total']}, searched_at: {result['searched_at']}")
    return result


def test_search_fulltext():
    """Test fulltext search."""
    print("\n[Test] Fulltext search: tax preference")
    result = search_tax("税收优惠", scope="fulltext", status=3, size=5)
    assert result["total"] > 0, "Expected >0 results"
    print(f"  [PASS] Total: {result['total']}")
    return result


def test_search_exact():
    """Test exact title search."""
    print("\n[Test] Exact search: VAT Law")
    result = search_tax("中华人民共和国增值税法", scope="title", search_type=1, status=3, size=5)
    assert result["total"] > 0, "Exact search should find VAT law"
    print(f"  [PASS] Found {result['total']} matches")
    return result


def test_search_date_range():
    """Test search with date range filter."""
    print("\n[Test] Date range: CIT 2024-2026")
    result = search_tax("企业所得税", scope="fulltext", status=3,
                        date_from="2024-01-01", date_to="2026-12-31", size=5)
    assert result["total"] > 0
    for item in result["results"]:
        if item["publish_date"]:
            assert item["publish_date"] >= "2024-01-01", f"Date out of range: {item['publish_date']}"
    print(f"  [PASS] Total in 2024-2026: {result['total']}")
    return result


def test_search_with_cache():
    """Test cache functionality."""
    print("\n[Test] Cache: two sequential searches")
    import tax_search
    from tax_search import _CacheManager

    # Clear any residual cache first
    _CacheManager(enabled=True).clear()
    tax_search._cache = _CacheManager(enabled=True)

    result1 = search_tax("契税", scope="title", status=3, size=3)
    assert not result1.get("_from_cache"), "First search should not be from cache"

    result2 = search_tax("契税", scope="title", status=3, size=3)
    assert result2.get("_from_cache"), "Second search should be from cache"

    tax_search._cache = _CacheManager(enabled=False)
    print(f"  [PASS] Cache works: first={result1['searched_at']}, second={result2['searched_at']}")
    return result2


def test_fetch_detail():
    """Test fetching law detail."""
    print("\n[Test] Fetch detail for a known law")
    result = search_tax("中华人民共和国增值税法", scope="title", search_type=1, status=3, size=1)
    assert len(result["results"]) > 0
    law_id = result["results"][0]["id"]

    detail = fetch_detail(law_id)
    assert detail["title"], "Detail should have a title"
    print(f"  [PASS] Detail: {detail['title'][:50]} | {detail.get('status', '?')}")
    return detail


def test_chinatax_search():
    """Test chinatax.gov.cn WebFetch."""
    print("\n[Test] chinatax.gov.cn search: VAT")
    result = search_chinatax("增值税", size=5)
    assert "keyword" in result
    assert "results" in result
    print(f"  [PASS] Total: {result['total']}, searched_at: {result['searched_at']}")
    if result.get("_error"):
        print(f"  [WARN] Chinatax error (non-fatal): {result['_error']}")
    if result["results"]:
        print(f"  First: {result['results'][0]['title'][:60]}")
    return result


def test_formatter():
    """Test formatting search results."""
    print("\n[Test] Format search results to markdown")
    result = search_tax("增值税", scope="title", status=3, size=3)
    md = format_search_response(result, intent="policy_lookup")
    assert "增值税" in md
    assert "免责声明" in md
    assert "searched_at" in result
    assert len(md) > 200
    print(f"  [PASS] Output {len(md)} chars, contains disclaimer and timestamp")
    return md


def test_two_phase():
    """Test two-phase search (title-first, fulltext fallback)."""
    print("\n[Test] Two-phase search")
    result = search_tax_full("增值税", status=3, size=5)
    assert result["total"] > 0
    print(f"  [PASS] Two-phase found: {result['total']} results, scope={result['scope']}")
    return result


def main():
    print("=" * 60)
    print("tax-policy-search: End-to-End Tests")
    print("=" * 60)

    tests = [
        ("Intent Detection", test_detect_intent),
        ("Tax Type Resolution", test_resolve_tax_type),
        ("Title Search (NPC API)", test_search_title),
        ("Fulltext Search (NPC API)", test_search_fulltext),
        ("Exact Search", test_search_exact),
        ("Date Range Filter", test_search_date_range),
        ("Cache", test_search_with_cache),
        ("Fetch Detail", test_fetch_detail),
        ("chinatax.gov.cn WebFetch", test_chinatax_search),
        ("Markdown Formatter", test_formatter),
        ("Two-Phase Search", test_two_phase),
    ]

    all_passed = 0
    all_total = 0

    for name, fn in tests:
        try:
            print(f"\n{'─' * 50}")
            print(f"> {name}")
            result = fn()
            if isinstance(result, tuple) and len(result) == 2:
                p, t = result
                all_passed += p
                all_total += t
            else:
                all_passed += 1
                all_total += 1
        except Exception as e:
            print(f"  [FAIL] {e}")
            all_total += 1
            import traceback
            traceback.print_exc()

    print(f"\n{'=' * 60}")
    print(f"Results: {all_passed}/{all_total} passed")
    print(f"{'=' * 60}")

    return 0 if all_passed == all_total else 1


if __name__ == "__main__":
    sys.exit(main())
