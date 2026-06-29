# 全网搜索政策解读 — 可行性评估

## 实测结论：完全可行，比 AI 生成方案更简单

---

## 核心发现

WebSearch 工具实测通过：

```
查询: site:chinatax.gov.cn 增值税法 官方解读 2024 2025

返回结果:
✅ 司法部 财政部 税务总局负责人就《增值税法实施条例》答记者问
✅ 《纳税缴费信用管理办法》解读
✅ 中华人民共和国增值税法全文
```

→ .gov.cn 域名的政策解读、答记者问、官方解读均能被搜到，**质量权威、时效最新**。

---

## 数据源覆盖矩阵

| 来源 | 内容类型 | 搜索方式 | 状态 |
|------|---------|---------|------|
| chinatax.gov.cn | 总局公告、答记者问、政策解读 | WebSearch `site:chinatax.gov.cn` | ✅ 已验证 |
| mof.gov.cn | 财政部解读、财税联合发文 | WebSearch `site:mof.gov.cn` | ✅ 同机制 |
| npc.gov.cn | 立法说明、草案审议报告 | WebSearch `site:npc.gov.cn` | ✅ 同机制 |
| gov.cn 全站 | 国务院政策吹风会、新闻发布 | WebSearch `site:gov.cn` | ✅ 同机制 |
| AnySearch legal domain | 学术解读、行业分析、律师评论 | CLI `--domain legal` | ✅ 已可用 |

---

## 与 AI 生成方案的对比

| 维度 | AI 生成解读 | 全网搜索解读 |
|------|-----------|------------|
| **权威性** | ⭐⭐ Claude 解读 | ⭐⭐⭐⭐⭐ 官方答记者问/立法说明 |
| **法律风险** | 有（AI 可能编造） | 无（都是官方来源） |
| **成本** | API token 费 | 零额外成本 |
| **延迟** | 3-10s | 2-5s |
| **新增代码** | ~120 行 | ~60 行 |
| **新增依赖** | 无（已有 Claude Code） | **无（全部已有）** |
| **可复用的已有代码** | 0 行 | `tax_web_search.py` 的 Baidu 搜索逻辑 + WebSearch/WebFetch 工具 |
| **维护成本** | 无 | 低 |

> **结论：全网搜索方案在权威性、法律风险、成本三个关键维度全面优于 AI 生成。**

---

## 实现方案（3h，~80 行新代码）

### 后端：新增 1 个端点（~30 行）

```python
# tax_server.py 新增

@app.route("/api/interpretations/<bbbs_id>", methods=["GET"])
def api_interpretations(bbbs_id):
    """Search the web for official policy interpretations of a law."""
    detail = fetch_detail(bbbs_id)
    title = detail.get("title", "")
    keyword = request.args.get("keyword", title)

    # Build search queries targeting official sources
    queries = [
        f"site:chinatax.gov.cn {title} 解读",
        f"site:chinatax.gov.cn {title} 答记者问",
        f"site:mof.gov.cn {title} 政策解读",
        f"site:gov.cn {title} 官方解读",
    ]
    if keyword and keyword != title:
        queries.insert(0, f"site:chinatax.gov.cn {keyword} 政策解读")

    # Each query result contains title + url + snippet
    results = []
    for q in queries[:3]:  # Limit to 3 to avoid rate limiting
        items = _search_web(q, n=3)
        results.extend(items)

    # Deduplicate by URL
    seen = set()
    deduped = []
    for r in results:
        if r["url"] not in seen:
            seen.add(r["url"])
            deduped.append(r)

    return jsonify({
        "law_id": bbbs_id,
        "law_title": title,
        "sources": deduped[:8],
        "searched_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
```

### 复用已有能力

| 能力 | 从哪里复用 | 方式 |
|------|-----------|------|
| chinatax 搜索 | `tax_web_search.py` `_baidu_site_search()` | 直接导函数，改参数 |
| WebFetch 页面抓取 | 已有 `requests` | 同上 |
| 多源聚合 | `tax_aggregator.py` 的模式 | 复用 ThreadPoolExecutor 并行架构 |
| AnySearch 兜底 | `anysearch` skill CLI | `subprocess.run(["python3", "anysearch_cli.py", "search", ...])` |

### 前端：法规弹窗加一个 Tab（~50 行）

```
┌──────────────────────────────────────────────┐
│ 📜 增值税法                         [✕]      │
├──────────────────────────────────────────────┤
│ [📖 法规原文]  [🔍 官方解读]  [🌐 相关网页]   │  ← 3 个 Tab
├──────────────────────────────────────────────┤
│                                              │
│ 🔍 官方政策解读（实时搜索）                    │
│                                              │
│ ┌──────────────────────────────────────────┐ │
│ │ 📋 司法部 财政部 税务总局负责人           │ │
│ │    就《增值税法实施条例》答记者问          │ │
│ │    chinatax.gov.cn · 2025-12-25          │ │
│ │    [查看原文 →]                           │ │
│ ├──────────────────────────────────────────┤ │
│ │ 📋 增值税法实施条例 官方解读              │ │
│ │    mof.gov.cn · 2024-12-26               │ │
│ │    [查看原文 →]                           │ │
│ └──────────────────────────────────────────┘ │
│                                              │
│ 🕐 搜索时间: 2026-06-29 · 来源: gov.cn 官方  │
└──────────────────────────────────────────────┘
```

### 推荐：官方解读 + AI 解读 双 Tab

```
[📖 法规原文]  [🔍 官方解读]  [🤖 AI 解读]

   官方的权威解读           +    AI 帮你用大白话总结
   （从 .gov.cn 搜到的）        （可选，有 API Key 时启用）
```

---

## 实施步骤

```
Step 1 (1h): 后端 /api/interpretations/<id>
  ├── 调用 WebSearch 搜索多个 .gov.cn 源
  ├── 去重 + 返回结构化结果
  └── 复用 tax_web_search.py 的 Baidu 搜索逻辑

Step 2 (1h): 前端 Tab 式 UI
  ├── 法规弹窗改为 3 个 Tab
  ├── "官方解读" Tab 展示搜索结果卡片列表
  └── 每条可点击跳转原文

Step 3 (0.5h): 可选 — "相关网页" Tab
  └── AnySearch legal domain 兜底，覆盖非官方但有用的解读

Step 4 (0.5h): 可选 — AI 解读 Tab
  └── 方案 A（Claude Code 子进程），有 API Key 时启用
```

---

## 一句话总结

**全网搜索政策解读：3 小时、约 80 行新代码、零新依赖、权威性完胜 AI 生成。** 优先做这个。AI 解读作为可选 Tab 后续再补。
