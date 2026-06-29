# Tax Categories & Search Parameter Reference

## 18 Tax Types — Keyword → Search Strategy Mapping

When the user's query matches a tax type, use the corresponding search keywords and strategies.

### Category A: 流转税 (Turnover Tax)

| Tax Type | Search Keywords | Parent Law | Priority |
|---------|----------------|------------|----------|
| 增值税 | 增值税, VAT, 进项税, 销项税, 留抵退税 | 中华人民共和国增值税法 | 1 |
| 消费税 | 消费税, 卷烟, 成品油 | 中华人民共和国消费税法 | 2 |
| 关税 | 关税, 进出口税, 保税, 海关 | 中华人民共和国关税法 | 3 |

### Category B: 所得税 (Income Tax)

| Tax Type | Search Keywords | Parent Law | Priority |
|---------|----------------|------------|----------|
| 企业所得税 | 企业所得税, 应税所得, 税前扣除, 加计扣除, 高新技术企业, 小微企业 | 中华人民共和国企业所得税法 | 1 |
| 个人所得税 | 个人所得税, 综合所得, 专项附加扣除, 年度汇算 | 中华人民共和国个人所得税法 | 1 |

### Category C: 财产行为税 (Property & Behavioral Tax)

| Tax Type | Search Keywords | Priority |
|---------|----------------|----------|
| 房产税 | 房产税, 房地产税 | 4 |
| 土地增值税 | 土地增值税, 土增税, 清算 | 4 |
| 契税 | 契税, 不动产登记 | 4 |
| 城镇土地使用税 | 城镇土地使用税 | 4 |
| 车船税 | 车船税, 车辆购置税 | 5 |
| 印花税 | 印花税, 合同印花税 | 4 |
| 城市维护建设税 | 城建税, 教育费附加, 地方教育附加 | 4 |

### Category D: 资源环境税 (Resource & Environmental Tax)

| Tax Type | Search Keywords | Priority |
|---------|----------------|----------|
| 资源税 | 资源税, 水资源税, 矿产资源税 | 4 |
| 环境保护税 | 环境保护税, 环保税 | 4 |

### Category E: 征管与优惠 (Administration & Preferences)

| Category | Search Keywords | Parent Law |
|----------|----------------|------------|
| 税收征管 | 税收征收管理, 税务登记, 纳税申报, 发票管理, 税务稽查, 金税四期 | 中华人民共和国税收征收管理法 |
| 税收优惠 | 税收优惠, 减免税, 退税, 即征即退, 先征后退 | — |

---

## NPC API Status Codes (sxx)

| Code | Status | Meaning | Badge |
|------|--------|---------|-------|
| 1 | 已废止 | No longer in force | 🔴 |
| 2 | 已修改 | Amended (older version) | 🟡 |
| 3 | 现行有效 | Currently effective | 🟢 |
| 4 | 尚未生效 | Published but not yet effective | 🔵 |

**Default filter: status=3 (effective only).**
User can request "all" or "include abolished" to remove the filter.

---

## Category Codes (flfgCodeId)

| Category | Scope |
|----------|-------|
| 宪法 | Constitutional law |
| 法律 | National laws (passed by NPC/NPCSC) |
| 行政法规 | Administrative regulations (State Council) |
| 监察法规 | Supervisory regulations |
| 地方法规 | Local regulations |
| 司法解释 | Judicial interpretations |

Tax laws are typically under "法律" (national laws) or "行政法规" (administrative regulations).

---

## Sort Options

| Value | Meaning |
|-------|---------|
| relevance (default) | By search relevance score |
| date (sort=gbrq, order=-1) | By publish date, newest first |

---

## Issuing Authorities (zdjgCodeId) — Tax-Relevant

| Code | Authority |
|------|-----------|
| 110 | 全国人民代表大会 / 全国人大常委会 |
| 120 | 国务院 |
| 130 | 最高人民法院 / 最高人民检察院 |
| *(local authorities vary by region)* | *(use region_classifier.py for post-processing)* |

---

## Rate Limiting

| Mode | Use Case |
|------|----------|
| auto (default) | Small tasks unlimited, medium 5rps, large adaptive |
| fixed | For programs: steady 5 req/s |
| adaptive | For collections >100 items: auto-adjusts 1-8 req/s |
