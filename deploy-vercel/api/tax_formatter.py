#!/usr/bin/env python3
"""
Tax Policy Formatter — structure API results into standardized markdown output.

Four-section template:
  1. Core Conclusion (one sentence)
  2. Policy Basis (law name + document number + date + status badge)
  3. Applicable Conditions (bullet list)
  4. Risk Advisory (warnings)

Output always includes:
  - Query timestamp
  - Data source provenance
  - Legal disclaimer
"""

import json
import sys
import time
from typing import Optional

STATUS_ICONS = {1: "🔴 已废止", 2: "🟡 已修改", 3: "🟢 现行有效", 4: "🔵 尚未生效"}

DISCLAIMER = (
    "> ⚠️ **免责声明**：本内容仅供参考。税收政策以国家税务总局官网 (chinatax.gov.cn)、"
    "财政部官网 (mof.gov.cn)、主管税务机关的最新公告为准。"
    "涉及具体税务处理，请咨询专业税务人员。"
)

INTENT_HEADERS = {
    "policy_lookup": "政策解读",
    "filing_guide": "申报指南",
    "risk_check": "合规风险提示",
    "eligibility": "资格判定",
    "invoice": "发票处理指引",
}


def format_source_tag(source: str, searched_at: str) -> str:
    """Generate a source provenance tag."""
    return f"> 🔍 **数据来源**: {source} | 查询时间: {searched_at}"


def format_result_card(item: dict, source: str = "NPC 国家法律法规数据库",
                       intent: str = "policy_lookup") -> str:
    """Format a single search result as a structured card."""
    icon = STATUS_ICONS.get(item.get("status_code", 0), "❓")
    header = INTENT_HEADERS.get(intent, "查询结果")

    lines = [
        f"## {item['title']} — {header}",
        "",
        f"**时效性**: {icon}",
    ]

    if item.get("publish_date"):
        lines.append(f"**公布日期**: {item['publish_date']}")
    if item.get("effective_date"):
        lines.append(f"**施行日期**: {item['effective_date']}")
    if item.get("issuing_authority"):
        lines.append(f"**发布机关**: {item['issuing_authority']}")
    if item.get("category"):
        lines.append(f"**法规分类**: {item['category']}")

    lines.append("")
    lines.append(f"> 📄 NPC 法规 ID: `{item['id']}`")
    lines.append("")

    return "\n".join(lines)


def format_search_response(results: dict, intent: str = "policy_lookup",
                           source: str = "NPC 国家法律法规数据库") -> str:
    """Format a complete search response with all results."""

    searched_at = results.get("searched_at", time.strftime("%Y-%m-%d %H:%M:%S"))
    cache_tag = " ⚡缓存数据" if results.get("_from_cache") else ""

    lines = [
        format_source_tag(source, searched_at + cache_tag),
        "",
        f"**搜索结果**: \"{results['keyword']}\" — "
        f"共 {results['total']} 条法规",
        f"**搜索范围**: {results['scope']} ({results['search_type']})",
        "",
        "---",
        "",
    ]

    for i, item in enumerate(results.get("results", []), 1):
        if i > 10:
            lines.append(f"> ... 还有 {len(results['results']) - 10} 条结果，请缩小搜索范围")
            break
        lines.append(format_result_card(item, source, intent))
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("### 📝 如何使用本结果")
    lines.append("")
    lines.append(f"获取法规详情: `python scripts/tax_detail.py --info <法规ID>`")
    lines.append(f"下载法规全文: `python scripts/tax_detail.py --download <法规ID>`")
    lines.append(f"缩小搜索范围: `python scripts/tax_search.py \"关键词\" --exact --status 3`")
    lines.append("")
    lines.append(DISCLAIMER)

    return "\n".join(lines)


def merge_aggregated_response(npc_results: dict, chinatax_results: list,
                              anysearch_results: list, keyword: str,
                              intent: str = "policy_lookup") -> str:
    """Format aggregated results from multiple data sources."""

    searched_at = time.strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"> 🔍 **多源实时查询** | {searched_at}",
        f"> 数据源: NPC 国家法规库 | 国家税务总局 | 网页补充",
        "",
        f"## \"{keyword}\" — {INTENT_HEADERS.get(intent, '查询结果')}",
        "",
    ]

    # NPC results (primary)
    if npc_results and npc_results.get("total", 0) > 0:
        lines.append("### 📜 法律/行政法规（NPC 国家法规库）")
        lines.append("")
        for item in npc_results.get("results", [])[:5]:
            icon = STATUS_ICONS.get(item.get("status_code", 0), "❓")
            lines.append(f"- {icon} **{item['title']}**")
            lines.append(f"  公布: {item['publish_date']} | `{item['id']}`")
        lines.append(f"")
        lines.append(f"> 共 {npc_results['total']} 条，向上按权威度排序")
        lines.append("")

    # chinatax results (secondary)
    if chinatax_results:
        lines.append("### 🏛️ 部门规章/公告（国家税务总局）")
        lines.append("")
        for item in chinatax_results[:5]:
            lines.append(f"- 📋 **{item.get('title', '')}**")
            if item.get("date"):
                lines.append(f"  日期: {item['date']}")
            if item.get("url"):
                lines.append(f"  链接: {item['url']}")
        lines.append("")

    # anysearch results (supplementary)
    if anysearch_results:
        lines.append("### 🌐 相关网页/行业解读")
        lines.append("")
        for item in anysearch_results[:3]:
            lines.append(f"- {item.get('title', '')}")
            if item.get("url"):
                lines.append(f"  {item['url']}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("> ⚠️ 多源结果可能包含不同层级的法规（法律、行政法规、部门规章、地方性法规）。")
    lines.append("> 请优先参考 **NPC 国家法规库** 的法律和行政法规层级结果。")
    lines.append("")
    lines.append(DISCLAIMER)

    return "\n".join(lines)


# ── CLI ─────────────────────────────────────────────────────────────────────
def main():
    """Read JSON from stdin and format to markdown."""
    import argparse
    p = argparse.ArgumentParser(description="Format tax search results as markdown")
    p.add_argument("--intent", choices=list(INTENT_HEADERS.keys()),
                   default="policy_lookup")
    p.add_argument("--source", default="NPC 国家法律法规数据库")
    p.add_argument("--mode", choices=["single", "aggregated"], default="single",
                   help="single: one data source; aggregated: multi-source merge")
    args = p.parse_args()

    raw = sys.stdin.read()
    data = json.loads(raw)

    if args.mode == "aggregated":
        output = merge_aggregated_response(
            npc_results=data.get("npc"),
            chinatax_results=data.get("chinatax", []),
            anysearch_results=data.get("anysearch", []),
            keyword=data.get("keyword", ""),
            intent=args.intent,
        )
    else:
        output = format_search_response(data, intent=args.intent, source=args.source)

    print(output)


if __name__ == "__main__":
    main()
