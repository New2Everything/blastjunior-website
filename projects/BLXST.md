# BLXST - 兰星少年俱乐部官网

## 概述

- **项目定位**：无人值守 AI 运营管理官网（对外好逛好玩；对内可管理可追溯）
- **风格**：明亮运动风（Bright Sports）
- **用户**：成员 / 家长 / 粉丝 / 潜在新人 / 赞助合作方
- **设计白皮书**：见 `BLXST-design.md`

---

## 设计白皮书概要

### 核心风格
- **视觉**：浅底留白 + 高能点缀；运动元素（斜切角/速度线/计分牌/徽章）
- **色彩**：
  - 品牌主色：`#FF6B35`（橙色）
  - 行动点亮色：`#00B4D8`（蓝色）
  - 对抗色：红/蓝（仅用于对阵/比分）

### P0功能
- [x] 首页聚合：赛果/新闻/赞助商/相册
- [x] 赛程赛果：列表/筛选
- [x] 积分榜：排名/组别筛选
- [x] 战队列表：卡片展示
- [x] 选手列表：卡片展示
- [x] 画廊：相册卡片
- [x] 加入我们：报名表单/FAQ
- [x] AI运营后台：草稿→审核→发布

---

## 当前进度（2026-03-05）

### ✅ 已完成

#### 页面（9个）
| 页面 | URL | 数据来源 |
|------|-----|----------|
| 首页 | / | API→D1+R2 |
| 赛程 | /matches.html | API |
| 积分榜 | /standings.html | API |
| 战队列表 | /teams.html | API |
| 选手列表 | /players.html | API |
| 画廊 | /gallery.html | API→R2 |
| 加入我们 | /join.html | 静态 |
| 战队详情 | /team-detail.html | 静态 |
| 选手详情 | /player-detail.html | 静态 |

#### 技术架构
| 组件 | 状态 |
|------|------|
| Pages 部署 | ✅ blastjunior.com |
| blast-homepage-api | ✅ 数据聚合API |
| blast-auth-api | ✅ 登录注册 |
| blast-safe-api | ✅ 内容审核 |
| blast-static-api | ✅ R2公开访问 |
| D1 数据库 | ✅ 3个表（news/sponsors/media） |
| R2 存储 | ✅ 照片/聊天记录 |

#### D1数据（真实）
- **news表**：5条新闻（官网上线、济州岛比赛、运营团队等）
- **sponsors表**：3个赞助商（东方富海、味动力、Joma）
- **media表**：目前为空

#### R2数据
- community/messages.json（真实聊天记录）
- public/（HADO照片）

---

## 技术架构

### Workers
| Worker | 域名 | 用途 |
|--------|------|------|
| blast-homepage-api | kanjiaming2022.workers.dev | 统一数据API |
| blast-auth-api | kanjiaming2022.workers.dev | 用户登录注册 |
| blast-safe-api | kanjiaming2022.workers.dev | 内容安全审核 |
| blast-static-api | kanjiaming2022.workers.dev | R2公开访问 |

### 数据流（按白皮书第14点）
```
用户浏览器 → Pages（静态页）
     ↓
Worker API（blast-homepage-api）
     ↓
┌─────┴─────┐
D1          R2
(新闻/赞助商)  (照片/聊天)
```

### D1数据库
- **blastjunior-content-db** (uuid: 9e484b49...)
  - news：新闻表
  - sponsors：赞助商表
  - media：媒体表

### 数据分离原则（按设计白皮书）
| 数据类型 | 定义 | 存储 | 访问方式 |
|----------|------|------|----------|
| 可变化数据 | 赛果/积分/比赛记录 | R2 JSON | Worker API |
| 可统计数据 | 在线人数/浏览量 | R2 JSON | Worker API |
| 可追溯数据 | 积分榜/排名 | R2 JSON | Worker API |
| 新闻/赞助商 | 公告类内容 | D1 | Worker API |
| 媒体文件 | 照片/视频 | R2 | Worker API |
| 品牌表达 | Slogan/介绍文字 | 静态HTML | 直接渲染 |

**规则**：
- 所有变化数据必须经由Worker API，禁止前端直连D1/R2/KV
- 品牌表达文字允许占位，与数据模块严格隔离

### R2业务数据（当前）
- data/teams.json - 战队数据
- data/players.json - 选手数据
- data/matches.json - 比赛数据

---

## ⚠️ 关键经验：D1数据库访问

**问题**：直接调用Cloudflare API查询D1会返回"Route not found"

**原因**：D1的API路径格式与Workers/KV不同，官方文档中的路径可能不正确

**解决方案**：使用 `wrangler` CLI操作D1

```bash
# 方式1：通过Worker + D1绑定查询（推荐）
# 1. 创建带D1绑定的Worker
# 2. 在Worker里执行: await env.DB.prepare("SELECT * FROM table").all()

# 方式2：wrangler CLI（适合直接操作）
CLOUDFLARE_API_TOKEN="xxx" CLOUDFLARE_ACCOUNT_ID="xxx" \
  wrangler d1 execute <database_id> --remote --command="SELECT * FROM table"
```

**经验总结**：
- 不能用 `curl` 直接查D1 API
- 必须通过Worker+D1绑定，或者wrangler CLI
- D1绑定格式：`[[d1_databases]] binding = "DB" database_name = "xxx" database_id = "xxx"`

---

## 待完成

| 功能 | 优先级 |
|------|--------|
| 比赛复盘页 | P1 | ✅ | ✅ |
| 一键分享卡 | P1 | ✅ |
| 关注订阅 | P1 | ✅ |
| 搜索与标签 | P1 | ✅ |
| AI自动发赛果 | P0 |

---

## 验收清单

- [x] 首页：30秒内找到关键信息
- [x] 风格：明亮运动风
- [x] 导航：8栏完整
- [x] 色彩：符合白皮书规范
- [x] 无控制台错误
- [x] API数据流接通（D1+R2）

---

## Workers API列表

| Worker | 用途 | 数据来源 |
|--------|------|----------|
| blast-homepage-api | 聚合数据 | D1+R2 |
| blast-share-api | 分享卡 | R2 |
| blast-search-api | 搜索 | D1+R2 |
| blast-subscribe-api | 订阅 | KV+R2 |
| blast-ai-report-api | AI赛报 | R2 |
| blast-auth-api | 登录注册 | KV |
| blast-safe-api | 内容审核 | KV |
| blast-static-api | R2访问 | R2 |

---

## 待询问老K

1. KV命名空间：订阅功能使用现有blast-comments，是否需要单独创建？
2. AI赛报：当前是简单模板生成，需要更智能的分析吗？
3. D1表：teams/players/matches表初始化失败，是否需要继续尝试？
