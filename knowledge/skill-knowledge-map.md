# Skill与.md业务关系知识库

> 用于理解各Skill之间的依赖关系和数据流向

---

## 总览图

```
                    ┌──────────────────┐
                    │  website-builder │
                    │    (输出网站)     │
                    └────────┬─────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
┌─────────────┐    ┌─────────────────┐  ┌─────────────┐
│   ai-news   │    │  website-test   │  │ website-    │
│  (输入知识)  │    │  (测试验证)    │  │  learning   │
└─────┬───────┘    └────────┬────────┘  │  (输入知识)  │
      │                     │            └─────┬───────┘
      │                     │                  │
      ▼                     ▼                  ▼
knowledge/              skills/            knowledge/
 hado-business.md     website-test/       hado-learning.md
 hado/news-archive.md  best-practices.md  hado-resources.md
                                           hado-business.md
```

---

## 1. ai-news（AI新闻生成）

### 功能
自动生成俱乐部新闻，支持转发HADO官方资讯或生成Opinion

### 依赖关系

```
输入                                    输出
│                                      │
├── knowledge/hado-business.md ──────→ 术语正确性
├── knowledge/hado/news-archive.md ──→ 转发内容来源
├── D1: news-database ──────────────→ 发布目标
│
└── skills/ai-news/SKILL.md ──────── 定义
```

### 核心原则
- 不捏造事实
- 不传播谣言
- Opinion正面
- 注明出处

---

## 2. website-builder（网站建设）

### 功能
完整网站开发工作流，从需求分析到部署上线

### 依赖关系

```
输入                                    输出
│                                      │
├── projects/BLXST.md ──────────────→ 项目主文件
├── projects/BLXST-design.md ───────→ 设计规范
├── projects/BLXST-data-attributes.md → 数据定义
├── workers/ ───────────────────────→ API代码
├── public/ ───────────────────────→ 前端页面
│
└── skills/website-builder/SKILL.md ── 定义
```

### 输出
- blastjunior.com 网站
- Workers API
- D1数据库

---

## 3. website-learning（网站增量学习）

### 功能
从官网高效学习知识，避免重复抓取

### 依赖关系

```
输入                                    输出
│                                      │
├── 官网URLs ────────────────────────→ 学习来源
│   (www.hado-official.cn)
│
├── knowledge/hado-resources.md ─────→ URL汇总
├── knowledge/hado-learning.md ──────→ 待学清单
│
├── knowledge/hado-business.md ──────→ 知识库
├── knowledge/hado/news-archive.md ──→ 详情存档
│
└── skills/website-learning/SKILL.md → 定义
```

### 核心原则
- 增量优先
- 定向抓取
- 分层存储
- 引用为主

---

## 4. website-test + agent-browser（网站自动化测试）

### 两者关系

```
website-test (定义/脚本)
      │
      │ 调用
      ▼
agent-browser (执行)
```

**website-test** 负责：
- 定义最佳实践/检测项
- 编写测试脚本
- 组织测试流程

**agent-browser** 负责：
- 实际打开浏览器
- 截图/Snapshot
- 检测JS错误
- 执行交互

### 依赖关系

```
┌─────────────────────────────────────────────────────────────┐
│                   website-test                              │
│  (定义检测项)                                               │
└─────────────────────────────────────────────────────────────┘
           │                              │
           ▼                              ▼
skills/website-test/              skills/agent-browser/
├── SKILL.md                    └── SKILL.md
├── references/                   (浏览器操作定义)
│   ├── best-practices.md        (无.md依赖)
│   └── slo.md
└── scripts/
    └── best_practice_test.sh
           │
           ▼
   ┌──────────────────┐
   │ agent-browser    │
   │ (执行层)         │
   └──────────────────┘
           │
           ▼
   ┌──────────────────────────────────────────┐
   │ 目标网站: blastjunior.com                 │
   │                                           │
   │ 输入: URL                                  │
   │ 输出: Snapshot/错误/检测结果               │
   └──────────────────────────────────────────┘
```

### 与.md的关系

| 文件 | 用途 |
|------|------|
| `skills/website-test/SKILL.md` | 技能定义 |
| `skills/website-test/references/best-practices.md` | **10项最佳实践**（核心检测标准） |
| `skills/website-test/references/slo.md` | SLO性能基准 |
| `skills/website-test/scripts/best_practice_test.sh` | 检测脚本 |
| `skills/agent-browser/SKILL.md` | 浏览器操作 |

### 执行流程

```
1. website-test 读取
   └── best_practice_test.sh
       └── 10项检测定义
   
2. 执行检测
   ├── curl 检查 (URL/title/源码)
   └── agent-browser 检查 (JS错误/snapshot)
   
3. agent-browser 执行
   ├── open URL
   ├── snapshot
   ├── errors
   └── eval JS

4. 输出结果
   └── 10项通过/失败
```

---

## 角色总结

| Skill | 角色 | 核心依赖 |
|-------|------|----------|
| ai-news | 生产者 | knowledge/ + D1 |
| website-builder | 构建者 | projects/ + workers/ |
| website-learning | 学习者 | 官网 + knowledge/ |
| website-test | 检验者 | best-practices.md |
| agent-browser | 执行者 | 无（独立工具） |

---

## 文件索引

### Skills (自建)
- skills/ai-news/SKILL.md
- skills/website-builder/SKILL.md
- skills/website-learning/SKILL.md
- skills/website-test/SKILL.md
- skills/agent-browser/SKILL.md

### 知识库
- knowledge/hado-business.md
- knowledge/hado-learning.md
- knowledge/hado-resources.md
- knowledge/hado/news-archive.md

### 项目文件
- projects/BLXST.md
- projects/BLXST-design.md
- projects/BLXST-data-attributes.md

### 测试标准
- skills/website-test/references/best-practices.md
- skills/website-test/references/slo.md

---

*最后更新：2026-03-07*
