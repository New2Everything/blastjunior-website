# BLXST - 兰星少年俱乐部官网

## 概述

- **项目定位**：无人值守 AI 运营管理官网
- **风格**：明亮运动风（Bright Sports）
- **用户**：成员 / 家长 / 粉丝 / 潜在新人 / 赞助合作方
- **设计白皮书**：见 `BLXST-design.md`

---

## 当前进度（2026-03-05）

### ✅ P0功能（已完成）

| 功能 | 状态 | 数据来源 |
|------|------|----------|
| 首页聚合 | ✅ | API→D1+R2 |
| 赛程赛果 | ✅ | API→R2 |
| 积分榜 | ✅ | API→R2 |
| 战队列表 | ✅ | API→R2 |
| 选手列表 | ✅ | API→R2 |
| 画廊 | ✅ | API→R2 |
| 加入我们 | ✅ | 静态 |
| 战队详情 | ✅ | 静态 |
| 选手详情 | ✅ | 静态 |
| 比赛复盘 | ✅ | API→R2 |

### ✅ P1功能（已完成）

| 功能 | 状态 | API |
|------|------|-----|
| 比赛复盘页 | ✅ | blast-homepage-api |
| 一键分享卡 | ✅ | blast-share-api |
| 搜索与标签 | ✅ | blast-search-api |
| 关注订阅 | ✅ | blast-subscribe-api |
| AI自动发赛果 | ✅ | blast-ai-report-api |
| 荣誉室 | ✅ | honor.html |

---

## Workers API列表

| Worker | 用途 | 数据来源 |
|--------|------|----------|
| blast-homepage-api | 聚合数据 | D1+R2 |
| blast-share-api | 分享卡 | R2 |
| blast-search-api | 搜索 | D1+R2 |
| blast-subscribe-api | 订阅 | KV(新建) |
| blast-ai-report-api | AI赛报 | R2 |
| blast-auth-api | 登录注册 | KV |
| blast-safe-api | 内容审核 | KV |
| blast-static-api | R2访问 | R2 |

---

## 数据流（按设计白皮书）

```
前端 → Worker API → D1 (新闻/赞助商)
                → R2 JSON (战队/选手/比赛)
                → R2 (照片/媒体)
                → KV (订阅/会话)
```

---

## 页面列表

| 页面 | URL | 状态 |
|------|-----|------|
| 首页 | / | ✅ |
| 赛程 | /matches.html | ✅ |
| 积分榜 | /standings.html | ✅ |
| 战队列表 | /teams.html | ✅ |
| 选手列表 | /players.html | ✅ |
| 画廊 | /gallery.html | ✅ |
| 加入我们 | /join.html | ✅ |
| 战队详情 | /team-detail.html | ✅ |
| 选手详情 | /player-detail.html | ✅ |
| 比赛详情 | /match-detail.html | ✅ |
| 荣誉室 | /honor.html | ✅ |

---

## 验收清单

- [x] 首页：30秒内找到关键信息
- [x] 风格：明亮运动风
- [x] 导航：8栏完整
- [x] 色彩：符合白皮书规范
- [x] 无控制台错误
- [x] API数据流接通（D1+R2/KV）
- [x] P0功能完成
- [x] P1功能完成

---

## 待询问老K

1. ~~D1表初始化~~ - 部分完成（teams表有数据，R2 JSON作为备用）
2. ~~订阅KV~~ - 已创建独立命名空间
3. ~~AI赛报~~ - 已升级为智能分析
