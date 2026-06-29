# Tax Risk Indicator Framework (search prompt reference only)

> ⚠️ **IMPORTANT**: This is a SEARCH PROMPT REFERENCE, not authoritative knowledge.
> All risk indicator names below should trigger real-time API searches — never answer from this list alone.
> The Golden Tax IV (金税四期) indicator system is continuously updated by tax authorities.

---

## Indicator Categories (Search Keywords)

### 增值税风险指标 (VAT — ~32 items)

Search keywords:
虚开发票, 骗取留抵退税, 进项税抵扣异常, 销项税申报不实, 即征即退异常,
增值税税负率偏低, 进销项不匹配, 四流合一异常, 农产品收购发票异常,
海关缴款书异常, 出口退税异常, 免税政策适用不当

### 企业所得税风险指标 (CIT — ~28 items)

Search keywords:
两税收入差异过大, 长亏不倒, 税负率低于行业均值, 虚增成本,
税前扣除异常, 研发费用加计扣除异常, 无形资产摊销异常,
关联交易价格异常, 资本弱化, 境外支付异常, 跨期费用调节

### 个人所得税风险指标 (IIT — ~12 items)

Search keywords:
工资薪金申报不实, 劳务报酬未代扣代缴, 专项附加扣除异常,
多处所得未合并申报, 经营所得核定征收异常, 股权转让个税

### 开票经济风险指标 (~36 items)

Search keywords:
暴力虚开, 票货分离, 资金回流, 空壳企业, 走逃失联,
富余票, 变名开票, 无货虚开, 两头在外, 环开发票

### 资金流风险指标 (~12 items)

Search keywords:
私户收款, 账外经营, 资金闭环, 大额现金交易, 公转私异常,
数字货币交易涉税, 跨境资金异常

### 关联交易风险指标 (~10 items)

Search keywords:
转让定价, 关联申报, 同期资料, 成本分摊协议,
受控外国企业, 预约定价安排, 资本弱化

### 跨境税务风险指标 (~12 items)

Search keywords:
境外所得申报, 非居民企业所得税, 常设机构判定,
跨境服务增值税, 跨境电商税务, 外汇管理

### 特殊行业风险指标 (~14 items)

Search keywords by industry:
- 建筑: 工程挂靠, 甲供材, 清包工
- 医药: 两票制, CSO推广费, 咨询费异常
- 电商: 平台刷单, 跨境代购, 社交电商
- 外贸: 出口骗税, 假自营真代理, 买单出口
- 房地产: 土地增值税清算, 配套设施费

---

## Three-Level Alert System (as publicly described)

| Level | Threshold | Description |
|-------|-----------|-------------|
| 🟢 绿线 | < 5% deviation | Normal monitoring |
| 🟡 黄线 | 5% - 15% deviation | Elevated attention required |
| 🔴 红线 | > 15% deviation | Immediate review triggered |

---

## TOP30 High-Risk Indicators (commonly referenced)

1. 虚开发票
2. 骗取留抵退税
3. 骗取出口退税
4. 资金闭环回流
5. 两税收入差异 > 10%
6. 长亏不倒（连续 3 年以上亏损仍正常经营）
7. 税负率 < 行业均值 60%
8. 进销项不匹配
9. 暴力虚开
10. 票货分离
11. 四流合一异常
12. 私户收款
13. 大额公转私异常
14. 关联交易价格明显偏低
15. 资本弱化
16. 转让定价同期资料缺失
17. 境外支付无扣缴凭证
18. 工资薪金申报不实
19. 多处所得未合并申报
20. 农产品收购发票异常
21. 海关缴款书异常比对
22. 富余票
23. 空壳企业
24. 医药咨询费异常
25. 房地产土增税清算逾期
26. 跨境电商未申报
27. 研发费用加计扣除材料不实
28. 高新技术企业认定材料不实
29. 跨期费用调节
30. 无形资产摊销异常

---

## How to Use This Document

When user asks about tax risks:
1. **First**: Run real-time search against NPC API with the specific risk keyword
2. **Then**: Supplement with chinatax.gov.cn search for latest enforcement notices
3. **Only then**: Cite this framework as context for categorizing the results
4. **Never**: List indicators from this document as the final answer without real-time verification

**Search command template**:
```bash
# NPC search for specific risk indicator
python scripts/tax_search.py "<risk_keyword>" --scope fulltext --status 3 --size 15

# chinatax enforcement notices
python scripts/tax_web_search.py "<risk_keyword> 处罚 稽查" --size 10
```

---

> ⚠️ The Golden Tax IV indicator system is maintained by the State Taxation Administration.
> Indicator names, thresholds, and scope change as the system evolves.
> This document dated 2026-06 — verify against real-time search results.
