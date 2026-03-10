# 网站增量学习 Skill

> 用于高效从官网学习知识，避免重复抓取

## 核心原则

1. **增量优先** - 只学新的/变化的，不重复学已掌握的
2. **定向抓取** - 只抓关键区域，不抓全页
3. **分层存储** - 概念放business.md，详情放独立文件
4. **引用为主** - 不复制大段内容，只引用URL

---

## 必备文件

### 1. 学习清单
`knowledge/hado-learning.md` - 待学主题清单

### 2. 官方资源库 ⚠️必读
`knowledge/hado-resources.md` - 官网URL汇总

**重要**：每次学习前必须先读取resources.md，确认去哪个网站抓数据！

### 3. 知识库
`knowledge/hado-business.md` - 整理后的知识

---

## 学习流程

### 1. 检查待学清单 + 资源

```
读取 knowledge/hado-learning.md  → 确认学习主题
读取 knowledge/hado-resources.md → 确认去哪个网站抓
```

### 2. 分析网站结构

```bash
# 探测网站有哪些页面
curl -s "https://www.hado-official.cn/" | grep -oE 'href="[^"]*"' | grep -v "#" | sort -u
```

### 3. 定向抓取

不抓全页，只抓目标区域：

```bash
# 抓取特定关键词区域
curl -s "URL" | sed 's/<[^>]*>//g' | grep -A10 -B5 "目标关键词"
```

### 4. 检查变化

如果需要增量更新：
```bash
# 检查是否有变化（简单hash对比）
curl -s "URL" | md5sum
```

### 5. 更新知识库

- 新内容 → 添加到 business.md 对应章节
- 已更新 → 标记更新时间
- 记录学习进度到 learning.md

---

## 文件结构

```
knowledge/
├── hado-business.md      # 概念层 - 浓缩版（AI检索用）
├── hado-learning.md     # 学习进度清单
├── hado-resources.md    # 官方资源汇总
└── hado/               # 详情层 - 详细资料
    ├── heroes.md       # 英雄详细数据
    ├── events-2026.md  # 赛事详情
    └── news-archive.md # 新闻存档
```

### 分层存储规则

```
# business.md 只存浓缩版
## 05. 英雄系统
- 坦克/护盾 - 防御型
- [详细英雄图鉴 -> knowledge/hado/heroes.md]

# 详细资料单独存
knowledge/hado/heroes.md

# 只引用不复制
- 最新赛事：[HADO世界杯](https://...)
```

---

## 学习命令

### 快速检查
```bash
# 检查某页面是否有新内容
check_updates() {
    url="$1"
    keyword="$2"
    content=$(curl -s "$url" | grep -i "$keyword")
    echo "$content" | md5sum
}
```

### 定向抓取
```bash
# 从about-us抓取规则相关内容
curl -s "https://www.hado-official.cn/about-us/" | \
    sed 's/<[^>]*>//g' | \
    grep -i "规则" -A10 -B2
```

### 智能归类
```bash
# 自动归类到business.md对应章节
learn_and_categorize() {
    content="$1"
    category="$2"  # 01-13对应business.md章节
    # 追加到对应章节
}
```

---

## 重点关注：News/Events

> 官网的 news 和 events 页面是更新最频繁的入口
> 适合持续跟踪最新动态

### 典型用途

| 页面 | 内容 | 价值 |
|------|------|------|
| /news | 最新赛事报道、活动信息 | 了解行业动态 |
| /events | 赛事安排、赛季信息 | 掌握比赛日程 |

### 学习建议

- 每次需要了解HADO最新情况 → 先查 news
- 准备赛季/比赛 → 先查 events
- 这两个页面变化最快，优先检查

---

## 示例：从news学习最新动态

```bash
# 1. 检查learning.md确认需要学
# 2. 定向抓取英雄相关
curl -s "https://www.hado-official.cn/products/" | \
    sed 's/<[^>]*>//g' | \
    grep -E "坦克|辅助|输出" -A2

# 3. 整理结构化
# 坦克/护盾 - 防御型
# 辅助/治疗 - 治疗辅助
# 输出/强化 - 攻击强化

# 4. 更新business.md第05章
```

---

## 关键技巧

| 技巧 | 命令 | 用途 |
|------|------|------|
| 去HTML | `sed 's/<[^>]*>//g'` | 提取纯文本 |
| 关键词区域 | `grep -A10 -B5 "关键词"` | 抓取目标区域 |
| 去重 | `sort -u` | 提取不重复URL |
| Hash对比 | `md5sum` | 检查变化 |
| 管道组合 | `\|` | 多重过滤 |

---

## 学习周期建议

| 频率 | 动作 |
|------|------|
| 每次新需求 | 定向抓取相关页面 |
| 每周一次 | 检查learning.md进度 |
| 每月一次 | 全面检查官网更新 |

---

*持续更新中...*
