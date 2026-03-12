# Content QA 技能

> 检测网站内容质量（完整性、时效性、正能量）

---

## 触发方式

**手动触发：**
```
输入: /content-qa 或 "检查内容质量"
```

---

## 检测维度

| 维度 | 内容 |
|------|------|
| 完整性 | 数据库有数据但网站未展示？ |
| 时效性 | 新闻/赛季是否最新？ |
| 正能量 | 内容是否正面积极？ |

---

## 检测命令

```bash
# 1. 对比数据库与网站数据
curl https://blast-homepage-api.kanjiaming2022.workers.dev/teams | jq '.data | length'

# 2. 检查新闻时效
curl https://blast-homepage-api.kanjiaming2022.workers.dev/news | jq '.[0].published_at'

# 3. 验证数据来源
curl https://blast-homepage-api.kanjiaming2022.workers.dev/gallery | jq '.data | length'
```

---

## 报告格式

```
## 内容质量报告

### 完整性
- 战队: 108 ✅
- 选手: 49 ✅

### 时效性
- 最新新闻: 2026-XX-XX ✅

### 结论
综合评分: XX/100
```
