# BLXST 网站现状图谱

> 本文件记录网站的**当前实际状态**，每次 sync 必须参考
> 规则类内容请查看 `BLXST-rules.md`

---

## 🗂️ 现状概览

```
BLXST-website/
├── 📁 后端 (Backend)
│   ├── Workers API (1个)
│   ├── D1 数据库 (2个)
│   └── R2 存储 (1个)
│
├── 📁 前端 (Frontend)
│   ├── Pages 部署
│   └── 页面文件
│
├── 📁 知识库 (Knowledge)
│   └── HADO业务规则
│
└── 📁 技能 (Skills)
    └── 开发/测试工具
```

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
| `/teams/:id` | 战队详情 (含阵容、积分、荣誉) ⭐新增 |
| `/players` | 49个选手 |
| `/players/:id` | 选手详情 (含战队历史、内部联赛) ⭐新增 |
| `/gallery` | 257张照片 |
| `/news` | 新闻列表 |
| `/sponsors` | 赞助商 |
| `/matches` | 赛季和参赛队伍列表 |
| `/matches/:id` | 比赛详情 (内部联赛结果) ⭐新增 |
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

### 4. 前端

#### Pages 部署
- **主站**: https://blastjunior.com
- **备用**: https://blastjunior-website.pages.dev

#### 页面文件
| 文件 | 用途 |
|------|------|
| public/index.html | 首页 |
| public/teams.html | 战队列表 |
| public/players.html | 选手列表 |
| public/gallery.html | 画廊 |
| public/heroes.html | 英雄图鉴 |
| public/match.html | 比赛详情 |
| public/standings.html | 积分榜 |
| public/login.html | 登录 |
| public/register.html | 注册 |

#### API 配置
```javascript
const API_BASE = 'https://blast-homepage-api.kanjiaming2022.workers.dev';
```

---

### 5. 知识库

| 文件 | 用途 |
|------|------|
| knowledge/hado-business.md | HADO业务规则 |
| knowledge/hado-resources.md | 资源链接 |
| knowledge/hado/news-archive.md | 新闻存档 |

---

### 6. 技能 (Skills)

| 技能 | 用途 |
|------|------|
| blxst-controller | 项目主控，调度子智能体 |
| blxst-sync | 同步检查，变更记录 |
| website-builder | 完整网站开发流程 |
| website-test | 自动化测试 |
| agent-browser | 浏览器自动化 |
| ai-news | AI新闻生成 |
| wrangler | Cloudflare管理 |

---

### 7. 角色

| 角色 | 职责 |
|------|------|
| 🦐 小虾 | 架构设计、任务规划、质量把控 |
| 🤖 subagent | 执行开发、测试、部署 |
| 🔧 agent-browser | UI测试、bug排查 |

---

## 🔄 Sync 检查流程

每次 new session 开始时：

```
1. 读取本文件 (BLXST-knowledge-graph.md)
2. 读取 BLXST-status.md (项目进度)
3. 读取 BLXST-rules.md (建站规则)
4. 运行验证命令
5. 汇报状态
```

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
- 2026-03-10: 清理旧文件，标记未建成API，进入重建准备阶段
