# 财税政策检索 Skill — 架构分析报告

基于对 tax-policy-knowledge、npc-law-db、anysearch 三个已有 Skill 的深度逆向分析。

---

## 数据源验证结果

```
NPC API (flk.npc.gov.cn) — 实测通过，立即可用：

┌─────────────────────┬─────────┬──────────┐
│ 搜索词              │ 搜索范围 │ 结果总数  │
├─────────────────────┼─────────┼──────────┤
│ 增值税              │ 全文模糊 │ 1,794    │
│ 增值税              │ 标题模糊 │ 57       │
│ 企业所得税          │ 全文模糊 │ 22,134   │
│ 企业所得税          │ 标题模糊 │ 538      │
│ 个人所得税          │ 全文模糊 │ 24,574   │
│ 个人所得税          │ 标题模糊 │ 79       │
│ 税收优惠            │ 全文模糊 │ 6,147    │
│ 发票                │ 全文模糊 │ 1,041    │
└─────────────────────┴─────────┴──────────┘

API 端点：POST https://flk.npc.gov.cn/law-search/search/list
详情 API：GET  https://flk.npc.gov.cn/law-search/search/flfgDetails?bbbs={id}
下载 API：GET  https://flk.npc.gov.cn/law-search/download/pc?format=docx&bbbs={id}
```

---

## 三个参考 Skill 的架构精华

### 一、tax-policy-knowledge — 纯知识库模式

**可复用要素：**

| 要素 | 示例 | 作用 |
|------|------|------|
| 意图分类表 | 政策查询/申报指导/风险自检/资格判定/发票问题 → 5种意图 | AI 先判意图，再走对应路径 |
| 知识领域表 | 增值税/企业所得税/个人所得税/风险预警 → 7个领域 | 将模糊问题映射到具体知识域 |
| 回答模板 | 「结论(一句) → 政策依据 → 适用条件 → 风险提示」 | 输出结构化、可预期 |
| 禁止行为 | 不给具体金额建议、不预测稽查结果、不代替申报操作 | 法律安全边界 |
| 免责声明 | 仅供参考，以官方为准 | 合规必要 |

**本质：零代码的 Prompt 工程文件**。100% 靠文本质量驱动 AI，维护只需改 Markdown。

### 二、npc-law-db — API+脚本引擎模式（⭐ 推荐主架构）

**可复用要素：**

| 设计点 | 实现方式 | 解决什么问题 |
|--------|---------|-------------|
| API-First | Python 直接调用 flk.npc.gov.cn API | 比浏览器自动化快 4-10 倍 |
| 命令速查表 | SKILL.md 中嵌入可复制执行的 bash 命令 | AI 不需要读完整个文件就能干活 |
| 搜索策略决策树 | 已知法规名→exact / 宽泛主题→fuzzy / 不确定→问用户 | 避免搜出一堆噪音 |
| 时效性过滤 | sxx 参数：1=已废止, 2=已修改, 3=现行有效, 4=尚未生效 | 税收领域最关键的筛选维度 |
| 速率限制 | auto/fixed/adaptive 三模式 | 防止被封 IP |
| 缓存机制 | 搜索1h/元数据24h/DOCX 7天 | 减少重复请求 |
| 法条级检索 | DOCX→按"第X条"分割→grep | 比全文搜索精准得多 |
| 错误处理 | 429→指数退避 | 不被封禁 |
| 发布机关分类 | region_classifier.py 映射 table | "广州市"→"广东省" |
| 参数速查表 | 中文值→API数字码的完整映射 | AI 无需猜测参数 |

**最精华的设计 —— 命令速查表：**
```bash
# 不给 AI 讲原理，直接给可复制运行的命令
python scripts/download.py --search "增值税" --size 100
python scripts/download.py --search "企业所得税法" --exact --status 3
python scripts/download.py --download {id} --format docx
```

### 三、anysearch — CLI工具集模式

**可复用要素：**

| 设计点 | 实现方式 |
|--------|---------|
| 垂直领域路由 | 金融/法律/学术→先 get_sub_domains 再垂直搜索 |
| 多运行时 fallback | Python > Node.js > PowerShell > bash |
| API Key 管理 | --flag > .env > 系统环境变量 > 匿名 |
| Command Cheat Sheet | `<cmd>` 占位符替代写死命令名 |

---

## 推荐架构：npc-law-db 模式 + tax-policy 约束层

```
tax-policy-search/
├── SKILL.md                       ← 意图表 + 命令速查 + 约束规则 + 回答模板
├── references/
│   ├── tax_categories.md           ← 税种分类 + spxx 参数映射
│   └── policy_templates.md         ← 政策类型 → 回答模板映射
├── scripts/
│   ├── tax_search.py               ← 核心搜索（继承 npc-law-db 的 API 调用）
│   ├── tax_detail.py               ← 法规详情 + DOCX 下载
│   └── tax_formatter.py            ← 结构化输出（结论→依据→条件→风险）
├── tests/
│   └── test_tax_search.py
└── requirements.txt                ← requests
```

### SKILL.md 应包含的模块（按优先级）

```
1. YAML 元数据 — 触发词（增值税/所得税/发票/优惠/金税四期等）
2. 意图分类表 — 5种意图→对应处理策略（从 tax-policy 继承）
3. 命令速查表 — 可直接复制的 CLI 命令（从 npc-law-db 继承）
4. 税种参数映射 — 关键词→spxx编码→sxx时效过滤
5. 时效性过滤规则 — 默认只查"现行有效"，明确标注"含已废止"
6. 回答模板 — 结论→依据→条件→风险 四段式（从 tax-policy 继承）
7. 禁止行为列表 — 法律安全边界
8. 免责声明
```

### 核心技术决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 主数据源 | flk.npc.gov.cn API | 全国人大官网，最权威；实测全部税种可查 |
| 查询策略 | 标题精确 > 标题模糊 > 全文模糊 | 先窄后宽，减少噪音 |
| 默认时效 | sxx=3 现行有效 | 税法时效性要求极高 |
| 输出格式 | 四段式 Markdown | 可预期的结构 |
| 语言 | Python 3 (request) | 与 npc-law-db 一致，依赖最简 |
| 速率控制 | adaptive 模式 | 自动调节 1-8 req/s |
| 缓存 | 搜索结果 1h / 详情 24h | 税收政策变动不快，缓存有效 |

### 关键差异化：与普通法律检索的区别

| 维度 | npc-law-db | tax-policy-search |
|------|-----------|-------------------|
| 默认时效 | 不限 | 仅现行有效 |
| 领域理解 | 通用法律 | 税种（18个税种）× 行业 × 企业类型 |
| 输出要求 | 原文展示 | 政策解读 + 适用判定 + 风险提示 |
| 用户 | 法律从业者 | 企业主/财务/个体户 |
| 禁止行为 | 无 | 严格：不给具体金额建议/不预测稽查 |
