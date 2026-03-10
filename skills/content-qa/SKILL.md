# Content QA - 内容质量检察官

> 自动检测网站内容质量，对比数据库与外部网站

---

## 角色定义

**职责**：确保网站内容完整、及时、准确、正能量

---

## 检测维度

### 1. 完整性检测
- 数据库有数据但网站未展示 → 漏展示
- 网站展示了但数据库没有 → 假数据

### 2. 时效性检测
- 新闻/赛事是否最新
- 赛季/积分是否更新
- 活动是否过期

### 3. 丰富性检测
- 对比其他HADO网站
- 内容数量对比
- 内容质量对比

### 4. 正能量检测
- 内容是否正面积极
- 是否有违规词
- 是否有趣好玩

---

## 数据来源

### 数据库（D1）
```bash
# 战队数据
wrangler d1 execute blast-campaigns-db --command="SELECT COUNT(*) FROM teams" --remote

# 选手数据
wrangler d1 execute blast-campaigns-db --command="SELECT COUNT(*) FROM players" --remote

# 新闻数据
wrangler d1 execute news-database --command="SELECT COUNT(*) FROM news_articles" --remote
```

### 网站展示（API）
```bash
# 战队数量
curl https://blast-homepage-api.kanjiaming2022.workers.dev/teams

# 选手数量
curl https://blast-homepage-api.kanjiaming2022.workers.dev/players
```

### 外部HADO网站
- https://www.hado-official.cn (HADO中国官网)
- 搜索引擎获取其他HADO相关网站

---

## 检测命令

### 完整性检测
```bash
# 对比数据库数量与API返回数量
# 1. 获取数据库战队数量
# 2. 获取API返回战队数量
# 3. 对比差异
```

### 时效性检测
```bash
# 检查最新新闻日期
curl https://blast-homepage-api.kanjiaming2022.workers.dev/news | jq '.[0].published_at'

# 检查赛季状态
curl https://blast-homepage-api.kanjiaming2022.workers.dev/seasons
```

### 丰富性检测
```bash
# 使用tavily-search搜索HADO相关内容
tavily-search --query "HADO 2025 赛事 新闻"
```

### 正能量检测
```bash
# 调用safe-api检查内容
curl -X POST https://blast-safe-api.kanjiaming2022.workers.dev/check \
  -d '{"content":"内容文本"}'
```

---

## 报告格式

```markdown
# 内容质量报告

## 1. 完整性
| 模块 | 数据库 | 网站展示 | 状态 |
|------|--------|----------|------|
| 战队 | 108 | 108 | ✅ |
| 选手 | 49 | 49 | ✅ |
| 新闻 | 5 | 5 | ✅ |

## 2. 时效性
| 模块 | 最新日期 | 状态 |
|------|----------|------|
| 新闻 | 2026-03-07 | ✅ |

## 3. 丰富性
- 外部网站：XX条
- 本网站：XX条
- 对比：XX

## 4. 正能量
- 违规词检测：通过 ✅
- 正面词汇：XX个

## 结论
- 综合评分：85/100
- 建议：XXX
```

---

## 自动化

### Cron任务（每周一次）
```bash
# 每周日晚8点生成报告
0 20 * * 0 cd /workspace && bash skills/content-qa/run.sh
```

### 触发方式
- 手动触发：`content-qa check`
- 定时任务：每周生成报告
- 部署后：自动检测新增内容
