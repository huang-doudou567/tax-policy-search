#!/usr/bin/env python3
"""Flask API server for tax-policy-search frontend."""
import os
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from tax_search import search_tax, detect_intent, resolve_tax_type
from tax_detail import fetch_detail, get_download_url, SXX_MAP, _parse_docx_from_bytes
from tax_web_search import search_chinatax
from tax_formatter import format_search_response
from tax_aggregator import aggregate_search

from flask import Flask, request, jsonify, send_from_directory
import requests as req
import urllib3
urllib3.disable_warnings()

app = Flask(__name__, static_folder=None)
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

_text_cache = {}
_interp_cache = {}

HEADERS_WEB = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Accept": "text/html,application/xhtml+xml",
}

# ── Interpretation Search Engine ─────────────────────────────────────────

def _search_one_source(site: str, query: str, n: int = 5) -> list[dict]:
    """Search a specific site via Bing for policy interpretations."""
    full_q = f"site:{site} {query}"
    url = f"https://www.bing.com/search?q={quote(full_q)}&count={n}"
    results = []
    try:
        r = req.get(url, headers=HEADERS_WEB, timeout=10)
        if r.status_code != 200:
            return results

        html = r.text
        # Bing uses <h2> for result titles, <cite> for URLs
        # Extract result blocks: each is an <li class="b_algo">
        block_pattern = re.compile(
            r'<li class="b_algo"[^>]*>(.*?)</li>', re.DOTALL
        )
        blocks = block_pattern.findall(html)

        for block in blocks[:n * 2]:
            # Extract title from <h2>
            title_match = re.search(r'<h2[^>]*><a[^>]*href="([^"]*)"[^>]*>(.*?)</a></h2>', block, re.DOTALL)
            if not title_match:
                title_match = re.search(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', block, re.DOTALL)
            if not title_match:
                continue

            href = title_match.group(1)
            title = re.sub(r'<[^>]+>', '', title_match.group(2)).strip()

            # Filter: only keep links containing the target site
            if site.replace("www.", "") not in href.replace("www.", ""):
                continue
            if len(title) < 5:
                continue

            # Extract date from block
            date_str = ""
            dm = re.search(r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})', block)
            if dm:
                date_str = dm.group(1)

            # Extract snippet
            snippet = ""
            sm = re.search(r'<p[^>]*class="[^"]*b_lineclamp[^"]*"[^>]*>(.*?)</p>', block, re.DOTALL)
            if sm:
                snippet = re.sub(r'<[^>]+>', '', sm.group(1)).strip()[:200]

            results.append({
                "title": title, "url": href, "date": date_str,
                "source": site, "source_label": _source_label(site),
                "snippet": snippet,
            })
            if len(results) >= n:
                break
    except Exception:
        pass
    return results


def _source_label(site: str) -> str:
    labels = {
        "fgk.chinatax.gov.cn": "税务法规库",
        "chinatax.gov.cn": "国家税务总局",
        "mof.gov.cn": "财政部",
        "npc.gov.cn": "全国人大",
        "gov.cn": "中国政府网",
    }
    for k, v in labels.items():
        if k in site:
            return v
    # Handle provincial subdomain: shanghai.chinatax.gov.cn → "上海税务"
    m = re.match(r"([a-z]+)\.chinatax\.gov\.cn", site)
    if m:
        province_map = {
            "beijing":"北京税务","shanghai":"上海税务","tianjin":"天津税务",
            "chongqing":"重庆税务","guangdong":"广东税务","shenzhen":"深圳税务",
            "zhejiang":"浙江税务","jiangsu":"江苏税务","shandong":"山东税务",
            "sichuan":"四川税务","hubei":"湖北税务","hunan":"湖南税务",
            "henan":"河南税务","hebei":"河北税务","fujian":"福建税务",
            "xiamen":"厦门税务","anhui":"安徽税务","liaoning":"辽宁税务",
            "dalian":"大连税务","jilin":"吉林税务","heilongjiang":"黑龙江税务",
            "jiangxi":"江西税务","shanxi":"山西税务","shaanxi":"陕西税务",
            "gansu":"甘肃税务","qinghai":"青海税务","yunnan":"云南税务",
            "guizhou":"贵州税务","guangxi":"广西税务","hainan":"海南税务",
            "neimenggu":"内蒙古税务","ningxia":"宁夏税务","xinjiang":"新疆税务",
            "xizang":"西藏税务","qingdao":"青岛税务","ningbo":"宁波税务",
        }
        return province_map.get(m.group(1), f"{m.group(1)}税务")
    return site


def _anysearch_legal(query: str, n: int = 5) -> list[dict]:
    """Use AnySearch CLI as supplementary legal search."""
    any_dir = Path.home() / ".claude" / "skills" / "anysearch" / "scripts"
    cli = any_dir / "anysearch_cli.py"
    if not cli.exists():
        return []

    import subprocess
    try:
        result = subprocess.run(
            ["python3", str(cli), "search", query, "--domain", "legal",
             "--max_results", str(n)],
            capture_output=True, text=True, timeout=20,
            cwd=str(any_dir.parent),
        )
        if result.returncode != 0:
            return []
        items = []
        lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
        for line in lines[:n]:
            items.append({
                "title": line[:120],
                "url": "",
                "date": "",
                "source": "AnySearch",
                "source_label": "网页补充",
            })
        return items
    except Exception:
        return []


def search_interpretations(law_title: str, keyword: str = "",
                           sources: list[str] = None,
                           province: str = "") -> dict:
    """Search official policy interpretations across multiple .gov.cn sources."""
    cache_key = f"{law_title}|{keyword}|{'-'.join(sources or [])}|{province}"
    if cache_key in _interp_cache:
        return _interp_cache[cache_key]

    if sources is None:
        if province:
            sources = [f"{province}.chinatax.gov.cn", "chinatax.gov.cn", "www.gov.cn"]
        else:
            sources = ["chinatax.gov.cn", "fgk.chinatax.gov.cn", "mof.gov.cn", "www.gov.cn"]

    # Build varied queries to find different types of interpretations
    title_short = law_title.replace("中华人民共和国", "").strip()
    queries = [
        f"{law_title} 解读 答记者问",
        f"{title_short} 政策解读",
        f"{law_title} 官方解读",
    ]
    if keyword and keyword != law_title:
        queries.insert(0, f"{keyword} 政策解读 官方")

    all_results = []
    seen_urls = set()

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {}
        for site in sources:
            for q_text in queries[:3]:  # top 3 queries per site
                futures[(site, q_text)] = pool.submit(
                    _search_one_source, site, q_text, 4
                )

        for (site, q_text), future in futures.items():
            try:
                items = future.result(timeout=15)
                for item in items:
                    if item["url"] not in seen_urls:
                        seen_urls.add(item["url"])
                        all_results.append(item)
            except Exception:
                pass

    # Supplementary: AnySearch legal domain
    try:
        anysearch_items = _anysearch_legal(f"{law_title} 政策解读", 3)
        for item in anysearch_items:
            if item.get("url") and item["url"] not in seen_urls:
                seen_urls.add(item["url"])
                all_results.append(item)
            elif not item.get("url"):
                all_results.append(item)
    except Exception:
        pass

    result = {
        "law_title": law_title,
        "keyword": keyword,
        "total": len(all_results),
        "sources": all_results[:12],
        "searched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    _interp_cache[cache_key] = result
    return result


def _download_and_extract(bbbs_id: str) -> list[str]:
    """Download DOCX from NPC and extract text paragraphs. Returns list of non-empty lines."""
    if bbbs_id in _text_cache:
        return _text_cache[bbbs_id]

    dl_url = get_download_url(bbbs_id, "docx")
    if not dl_url:
        return []

    resp = req.get(dl_url, verify=False, timeout=30, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://flk.npc.gov.cn/",
    })
    if resp.status_code != 200:
        return []

    paragraphs = _parse_docx_from_bytes(resp.content)
    if paragraphs:
        _text_cache[bbbs_id] = paragraphs
    return paragraphs


@app.route("/")
def index():
    return send_from_directory(str(FRONTEND_DIR), "index.html")


@app.route("/api/search", methods=["POST"])
def api_search():
    data = request.get_json() or {}
    keyword = data.get("keyword", "").strip()
    if not keyword:
        return jsonify({"error": "keyword required"}), 400

    scope = data.get("scope", "title")
    search_type = 1 if data.get("exact") else 2
    status = data.get("status", 3)
    date_from = data.get("date_from")
    date_to = data.get("date_to")
    size = min(data.get("size", 20), 50)
    sort = data.get("sort", "relevance")
    source = data.get("source", "npc")
    province = data.get("province", "")

    intent = detect_intent(keyword)
    tax_type_info = resolve_tax_type(keyword)

    if source == "aggregated":
        result = aggregate_search(keyword, size=size, status=status, scope=scope)
    elif source == "chinatax":
        result = search_chinatax(keyword, size=size)
    else:
        result = search_tax(
            keyword, scope=scope, search_type=search_type,
            status=status, date_from=date_from, date_to=date_to,
            size=size, sort=sort,
        )

    return jsonify({
        "keyword": keyword,
        "intent": intent,
        "province": province,
        "intent_label": {
            "policy_lookup": "政策查询",
            "filing_guide": "申报指导",
            "risk_check": "合规风险",
            "eligibility": "资格判定",
            "invoice": "发票处理",
        }.get(intent, intent),
        "tax_type": tax_type_info["type"] if tax_type_info else None,
        "tax_type_aliases": tax_type_info["aliases"] if tax_type_info else [],
        "result": result,
    })


@app.route("/api/detail/<bbbs_id>", methods=["GET"])
def api_detail(bbbs_id):
    try:
        detail = fetch_detail(bbbs_id)
        return jsonify({"detail": detail})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/text/<bbbs_id>", methods=["GET"])
def api_text(bbbs_id):
    """Download and return the full text of a law."""
    try:
        detail = fetch_detail(bbbs_id)
        paragraphs = _download_and_extract(bbbs_id)

        # Classify paragraphs: headings vs articles vs body text
        heading_pattern = re.compile(r"^第[一二三四五六七八九十百千]+[章节条]|^目[\s　]*[录录]")
        article_pattern = re.compile(r"^第[一二三四五六七八九十百千\d]+条\s")
        chapter_pattern = re.compile(r"^第[一二三四五六七八九十百千]+章")

        sections = []
        current_chapter = ""
        for para in paragraphs:
            if chapter_pattern.match(para):
                current_chapter = para
                sections.append({"type": "chapter", "text": para})
            elif article_pattern.match(para):
                sections.append({"type": "article", "text": para, "chapter": current_chapter})
            elif heading_pattern.match(para):
                sections.append({"type": "heading", "text": para})
            else:
                sections.append({"type": "body", "text": para})

        return jsonify({
            "detail": detail,
            "total_paragraphs": len(paragraphs),
            "article_count": sum(1 for s in sections if s["type"] == "article"),
            "sections": sections,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/ai-interpret/<bbbs_id>", methods=["GET"])
def api_ai_interpret(bbbs_id):
    """AI-generated interpretation as fallback for a law."""
    keyword = request.args.get("keyword", "")
    try:
        detail = fetch_detail(bbbs_id)
        title = detail.get("title", "")
        if not title:
            return jsonify({"error": "Law not found"}), 404

        # Get law text sections
        paragraphs = _download_and_extract(bbbs_id)
        # Build a condensed version: first 20 paragraphs + article headings
        article_re = re.compile(r"^第[一二三四五六七八九十百千\d]+条\s")
        articles = [p for p in paragraphs if article_re.match(p)]
        # Take first 30 articles + all chapter headings
        chapter_re = re.compile(r"^第[一二三四五六七八九十百千]+章")
        chapters = [p for p in paragraphs if chapter_re.match(p)]
        condensed = chapters + articles[:30]
        law_text = "\n".join(condensed)

        if not law_text:
            return jsonify({"error": "Could not extract law text"}), 500

        prompt = f"""你是中国资深税务专家。请用通俗易懂的语言为以下法规条文撰写政策解读。

法规名称：{title}
用户关注的关键词：{keyword or "无特定关键词"}

法规条文：
{law_text}

请按以下格式输出 Markdown（每个部分必须包含）：

## 适用主体
[一句话说明谁适用这个法规]

## 核心要点
- 要点1
- 要点2
- 要点3

## {keyword + "相关条款" if keyword else "关键条款"}
[与关键词最相关的 2-3 个条款的通俗解读]

## 注意事项
- [注意] 注意点1
- [注意] 注意点2

要求：
- 语言通俗易懂，面向企业主和财务人员，避免法律术语
- 不要直接重复法条原文，用自己的话解释
- 如涉及税率、金额、日期等关键数据，请准确引用
- 总数控制在 500 字以内"""

        import subprocess, tempfile
        # Write prompt to temp file, then use stdin redirect to claude
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt",
                                          encoding="utf-8", delete=False) as pf:
            pf.write(prompt)
            prompt_file = pf.name

        npm_global = Path.home() / "AppData" / "Roaming" / "npm"
        claude_path = npm_global / "claude.cmd"
        if not claude_path.exists():
            claude_path = npm_global / "claude"

        try:
            result = subprocess.run(
                f'"{claude_path}" --print < "{prompt_file}"',
                capture_output=True, encoding="utf-8", errors="replace",
                timeout=120,
                cwd=str(Path.home()),
                shell=True,
            )
        finally:
            os.unlink(prompt_file)

        if result.returncode != 0:
            return jsonify({"error": f"Claude error: {result.stderr[:200]}"}), 500

        return jsonify({
            "law_id": bbbs_id,
            "law_title": title,
            "keyword": keyword,
            "interpretation": result.stdout,
            "model": "Claude (AI 生成)",
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "disclaimer": "AI 生成内容仅供参考，以官方政策文件和主管税务机关解释为准。",
        })
    except subprocess.TimeoutExpired:
        return jsonify({"error": "AI generation timed out"}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/interpretations/<bbbs_id>", methods=["GET"])
def api_interpretations(bbbs_id):
    """Search official policy interpretations for a law."""
    keyword = request.args.get("keyword", "")
    province = request.args.get("province", "")
    try:
        detail = fetch_detail(bbbs_id)
        title = detail.get("title", "")
        if not title:
            return jsonify({"error": "Law not found"}), 404

        result = search_interpretations(title, keyword, province=province)
        result["law_id"] = bbbs_id
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/quick-tax-types", methods=["GET"])
def api_quick_tax_types():
    return jsonify([
        {"label": "增值税", "icon": "📊", "keyword": "增值税"},
        {"label": "企业所得税", "icon": "🏢", "keyword": "企业所得税"},
        {"label": "个人所得税", "icon": "👤", "keyword": "个人所得税"},
        {"label": "消费税", "icon": "🛒", "keyword": "消费税"},
        {"label": "关税", "icon": "🚢", "keyword": "关税"},
        {"label": "房产税", "icon": "🏠", "keyword": "房产税"},
        {"label": "印花税", "icon": "📝", "keyword": "印花税"},
        {"label": "契税", "icon": "🔑", "keyword": "契税"},
        {"label": "土地增值税", "icon": "🏗️", "keyword": "土地增值税"},
        {"label": "税收优惠", "icon": "🎁", "keyword": "税收优惠"},
        {"label": "发票管理", "icon": "🧾", "keyword": "发票管理办法"},
        {"label": "税收征管", "icon": "⚖️", "keyword": "税收征收管理法"},
    ])


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    print("\n  [tax-policy-search] API Server")
    print("  http://localhost:5080")
    print("  POST /api/search")
    print("  GET  /api/text/<id>")
    print("  GET  /api/interpretations/<id>")
    print()
    app.run(host="0.0.0.0", port=5080, debug=False)
