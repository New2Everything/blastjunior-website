# BLXST 网站现状图谱

> **Description**: 记录网站的当前实际状态，是项目的核心知识库
> **维护规则**: 不要增加骨架

> 本文件记录网站的**当前实际状态**，是项目的核心知识库
> 规则类内容请查看 `BLXST-rules.md`

## 用途

本文档记录BLXST网站的现状骨架，包括：
- API有哪些（名称 + 端点）
- 数据库有哪些（名称 + 数据表）
- 存储有哪些（名称 + 用途）
- 知识库有哪些（名称 + 用途）
- 技能有哪些（名称 + 用途）

知道名称后，可通过 skills/ 目录查找对应技能，通过 knowledge/ 目录查找对应知识。

---

## 📦 当前状态

### 1. Workers API

#### ✅ 已建成 (实际运行)
| 端点 | 域名 | 状态 |
|------|------|------|
| blast-homepage-api | blast-homepage-api.kanjiaming2022.workers.dev | ✅ 运行中 |

#### ❌ 未建成 (规划中)
| API | 用途 | 状态 |
|-----|------|------|
| blast-safe-api | AI内容审核 | ❌ 未建 |
| blast-auth-api | 用户认证 | ❌ 未建 |
| blast-media-api | 照片管理 | ❌ 未建 |
| blast-news-api | 新闻管理 | ❌ 未建 |
| blast-comment-api | 评论系统 | ❌ 未建 |

#### API 端点 (单API架构)
| 端点 | 返回数据 |
|------|----------|
| `/` | 首页聚合: news, sponsors, topTeams, topPlayers, featuredPhotos, stats, currentSeason |
| `/teams` | 108个战队 |
| `/teams/:id` | 战队详情 (含阵容、积分、荣誉) |
| `/players` | 49个选手 |
| `/players/:id` | 选手详情 (含战队历史、内部联赛) |
| `/gallery` | 257张照片 |
| `/news` | 新闻列表 |
| `/sponsors` | 赞助商 |
| `/matches` | 赛季和参赛队伍列表 |
| `/matches/:id` | 比赛详情 (内部联赛结果) |
| `/standings` | 积分榜 |

---

### 2. D1 数据库

| 数据库 | UUID后4位 | 用途 |
|--------|-----------|------|
| blast-campaigns-db | bc11dbe6 | 战队/选手/赛季/比赛 |
| news-database | c2d2f16b | 新闻内容 |

#### 数据表 (blast-campaigns-db)
- events (赛事)
- seasons (赛季)
- divisions (组别)
- players (选手)
- teams (战队)
- rosters (阵容)
- registrations (报名)
- team_aliases (战队别名)
- score_components (积分项目)
- team_component_points (战队积分)
- tournament_outcomes (赛事成绩)
- internal_league_results (内部联赛)

---

### 3. R2 Storage

| Bucket | 用途 |
|--------|------|
| blastjunior-media | 网站照片、视频等媒体文件 |

---

### 4. 知识库 (Knowledge)

| 文件 | 用途 |
|------|------|
| knowledge/hado-business.md | HADO业务规则 |
| knowledge/hado-learning.md | HADO学习资料 |
| knowledge/hado-resources.md | HADO资源链接 |

---

### 5. 技能 (Skills)

| 技能 | 用途 | 归属角色 |
|------|------|----------|
| blxst-controller | 项目主控，调度子智能体 | 主智能体 |
| blxst-sync | 同步检查，变更记录 | 主智能体 |
| blxst-deploy | 网站部署到 Cloudflare Pages | Coder |
| website-builder | 完整网站开发流程 | Coder |
| website-test | 自动化测试 | Tester |
| website-learning | 网站学习资料 | Coder |
| e2e-testing-patterns | E2E测试最佳实践 | Tester |
| agent-browser | 浏览器自动化，运行时测试 | Tester |
| web-design-guidelines | Web设计规范审查 | Architect, Design Reviewer |
| scrapling-mcp | 网页爬取，数据采集 | Tester |
| ai-news | AI新闻生成 | 定时任务 |
| content-qa | 内容质量审核 | 辅助 |
| wrangler | Cloudflare Workers/KV/R2/D1管理 | Coder |
| project-leader | 项目管理，任务拆解 | 主智能体 |
| find-skills | 技能发现与安装 | 通用 |
| github | GitHub 操作 | 通用 |
| notion | Notion 操作 | 通用 |
| obsidian | Obsidian 操作 | 通用 |
| summarize | 网址/文件摘要 | 通用 |
| tavily-search | AI搜索 | 通用 |
| weather | 天气查询 | 通用 |

---

### 6. 项目文件 (projects/)

| 文件 | 用途 |
|------|------|
| BLXST.md | 项目主入口 |
| BLXST-rules.md | 建站规则+执行规范 |
| BLXST-knowledge-graph.md | 现状图谱（本文件） |
| BLXST-status.md | 项目状态 |
| BLXST-design.md | 设计文档 |

---

## ⚠️ 重建说明

当前项目处于**重建准备阶段**。旧版本网站仍可访问，但新版本开发待开始。

**保留的资产：**
- HADO业务规则 (knowledge/hado-*)
- 建站铁律 (BLXST-rules.md)
- 数据库结构 (D1/R2)
- 开发技能 (website-builder, website-test, ai-news, wrangler)

**待建功能：**
- AI内容审核 (blast-safe-api)
- 用户认证系统
- 评论系统 等

---

## 📝 更新日志

- 2026-03-08: 初始版本
- 2026-03-10: 重构为现状图谱，规则移至 BLXST-rules.md
- 2026-03-12: 清理错误板块，添加知识文档列表，添加description
- 2026-03-12: 合并 skill-knowledge-map.md 内容
