# Search Strategies by Intent Type

Five intent types × two-phase search strategy. Always search FIRST, answer SECOND.

---

## Intent → Search Strategy Matrix

### 1. policy_lookup (政策查询)

**Trigger**: General policy questions without specific filing/risk/eligibility signals.

```bash
# Phase 1: Title search with keyword
python scripts/tax_search.py "<keyword>" --status 3 --size 20

# Phase 2 (if Phase 1 returns 0): Fulltext search
python scripts/tax_search.py "<keyword>" --scope fulltext --status 3 --size 20

# When user knows exact regulation name: Exact match
python scripts/tax_search.py "<exact_name>" --exact --status 3
```

**Example queries**: "小规模纳税人增值税率多少", "研发费用加计扣除比例"

---

### 2. filing_guide (申报指导)

**Trigger**: Keywords about filing, deadlines, procedures.

```bash
# Title-first search for filing-related regulations
python scripts/tax_search.py "<keyword> 申报" --status 3 --sort date

# Supplement: chinatax.gov.cn for operational guides
python scripts/tax_web_search.py "<keyword> 申报流程" --size 10
```

**Key data to extract from results**:
- Filing deadlines
- Required documents
- Filing channels (online/offline)
- Step-by-step procedure

---

### 3. risk_check (合规风险)

**Trigger**: Keywords about risk, compliance, audit, penalties.

```bash
# Fulltext search — risk indicators often appear in body text, not titles
python scripts/tax_search.py "<risk_keyword>" --scope fulltext --status 3 --size 20

# Supplement: chinatax.gov.cn for latest enforcement notices
python scripts/tax_web_search.py "<keyword> 稽查 处罚" --size 10
```

**Risk keywords reference**:
- 虚开发票, 骗取留抵退税, 骗取出口退税
- 关联交易, 转让定价, 两税收入差异
- 长亏不倒, 税负率异常, 资金闭环回流

**Output format for risk checks**:
```
风险类型: [从法规提取]
触发条件: [从法规提取]
风险等级: 🟢低 / 🟡中 / 🔴高
法规依据: [文号 + 法条引用]
```

---

### 4. eligibility (资格判定)

**Trigger**: Keywords about whether a policy applies, qualifying conditions.

```bash
# Exact + fuzzy dual approach
python scripts/tax_search.py "<policy_name>" --status 3 --scope fulltext --size 20
```

**Key data to extract**:
- Eligibility criteria (industry, size, revenue, employee count)
- Required documentation
- Application procedure and deadlines
- Common exclusion conditions
- "Not applicable if..." clauses

**Always check effective dates**: Policies expire or change thresholds over time.

---

### 5. invoice (发票)

**Trigger**: Keywords about invoices, issuance, redaction, loss.

```bash
# Invoice management regulations — title-first
python scripts/tax_search.py "发票管理办法" --exact --status 3

# Specific invoice issues — fulltext
python scripts/tax_search.py "<keyword>" --scope fulltext --status 3 --size 15
```

**Key invoice topics**:
- 发票领购 / 发票开具 / 发票红冲
- 发票遗失处理 / 发票认证 / 发票抵扣
- 全电发票 / 数电票 / 电子发票
- 发票管理办法处罚条款

---

## Cross-Intent Rules

1. **Always include --status 3 by default**. Only show abolished/amended laws when explicitly requested.
2. **Prefer title search first**, fallback to fulltext only when title returns 0 results.
3. **When uncertain about intent**: run both `policy_lookup` and `eligibility` strategies, let user pick.
4. **Always include `searched_at` timestamp** in output.
5. **Never use training data as the primary answer source**. Always cite specific API results with document IDs.
