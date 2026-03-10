# AI News 自动化技能

> 自动生成俱乐部新闻，可转发HADO官方资讯或生成Opinion

---

## 核心原则

**四不原则**：
1. **不捏造事实** - 只能用真实数据（战队名/选手名/赛事名）
2. **不传播谣言** - 只能基于真实来源
3. **Opinion正面** - 只发表正面有趣的观点
4. **注明出处** - 转发内容必须注明来源

---

## 内容类型

| 类型 | 说明 | 数据来源 |
|------|------|----------|
| **转发报道** | 转发HADO官网news/events，注明出处 | knowledge/hado/news-archive.md |
| **时效判断** | 对比当前时间，判断新鲜度 | 时间戳 |
| **独立Opinion** | 在转发/数据基础上发表AI观点 | AI生成（正面有趣） |
| **数据原创** | 基于俱乐部实时数据的原创 | D1 API |

---

## 时效性规则

```
当前时间: 2026-03-07

判断规则：
- 7天内：🔥 热点，直接转发
- 30天内：可转发 + Opinion
- 30天前：仅History，不适合发布

示例：
2025-12-24 (73天前) → 不适合发
2026-01-07 (59天前) → 不适合发
```

---

## 生成流程

### 1. 准备阶段

```
读取 knowledge/hado-news-archive.md  → 获取可转发内容
读取 knowledge/hado-business.md    → 确保术语正确
调用 D1 API → 获取俱乐部实时数据
```

### 2. 生成阶段

**类型A：转发报道**
```
标题：【转载】+ 原始标题
内容：原文内容
来源：HADO中国官网 + 日期
类型：转发
```

**类型B：转发+Opinion**
```
标题：【转载】+ 原始标题
内容：原文内容 + AI Opinion
Opinion示例：期待中国战队在国际赛场取得好成绩！
来源：HADO中国官网 + 日期
类型：转发+Opinion
```

**类型C：数据原创**
```
标题：第二届HPL联赛积分榜更新
内容：基于某联赛实时数据的报道（注意：每个联赛独立积分，不混总积分）
数据来源：/standings-v2 API
类型：原创
```

**类型D：纯Opinion**
```
标题：新赛季招新启动
内容：正面有趣的招新宣传
类型：Opinion
```

### 3. 验证阶段

```javascript
// 生成后验证
if (type === '转发') {
    mustHave('source')           // 必须有出处
    checkFreshness()             // 检查时效性
}

if (type === 'Opinion') {
    mustBePositive()            // 必须是正面
    noNegativeWords()           // 禁止负面词
    mustRelatedTo(['HADO', '兰星少年', '战队', '选手'])
}
```

### 4. 发布阶段

```bash
# 插入数据库
wrangler d1 execute news-database \
  --command "INSERT INTO news_articles (title, content, author, category, published_at, status) 
  VALUES ('$title', '$content', 'AI助手', 'Opinion', datetime('now'), 'published')"
```

---

## 使用方法

### 手动触发
```bash
# 生成一条AI News
ai-news generate --type opinion

# 转发+Opinion
ai-news generate --type repost --source hado-cn

# 基于数据
ai-news generate --type data
```

### 自动触发（未来）
```
通过cron定时任务激活
```

---

## 依赖文件

| 文件 | 用途 |
|------|------|
| knowledge/hado-business.md | 术语正确性 |
| knowledge/hado/news-archive.md | 可转发内容 |
| D1: news-database | 发布目标 |

---

## 禁止事项

- ❌ 捏造比赛结果
- ❌ 捏造选手信息
- ❌ 传播未经证实的信息
- ❌ 发表负面/消极观点
- ❌ 抄袭不做原创说明

---

## 正面词汇示例

```
加油！、期待！、恭喜！、精彩！、出色！
恭喜夺得！、表现亮眼！、实至名归！
新赛季加油！、未来可期！、潜力无限！
```

---

*持续更新中...*
