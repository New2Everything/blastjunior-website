# BLXST 数据库设计总结

> 本文档供AI快速理解BLXST项目的数据库架构设计

---

## 概览

| 数据库 | UUID | 用途 | 存储位置 |
|--------|------|------|----------|
| blast-campaigns-db | bc11dbe6-4f21-490b-b713-70564c95cf8e | **联赛业务核心** - 赛事/赛季/战队/选手 | APAC (SIN) |
| blastjunior-content-db | 9e484b49-935c-4ef5-8407-54f5bf38b441 | **官网内容** - 新闻/赞助商/展示数据 | US (SJC) |
| blast-photo-db | 9f259478-4234-4a29-92da-66b4c73feac5 | **媒体库** - 照片/相册 | APAC (HKG) |
| news-database | c2d2f16b-a85e-4cd6-8d95-eb16981c19c4 | 旧版新闻库（备用） | US (SJC) |

---

## 1. blast-campaigns-db - 联赛业务核心

**用途**：存储HADO联赛的完整业务数据，包括赛事、赛季、战队、选手、比赛成绩

### 表结构

| 表名 | 用途 | 数据量 | 字段 |
|------|------|--------|------|
| **events** | 赛事定义 | 5 | event_id, name_zh, name_en, level, frequency, official_url, description, created_at, updated_at |
| **seasons** | 赛季 | 4 | season_id, event_id, name, year, start_date, end_date, status, notes |
| **divisions** | 组别/分区 | 8 | division_id, season_id, division_key, name, sort_order, notes, leaderboard_key |
| **teams** | 战队 | 108 | team_id, canonical_name, club_id, first_season_id, note, team_type, team_code |
| **players** | 选手 | 49 | player_id, nickname, display_name, real_name, birth_year, is_active, club_name |
| **rosters** | 战队阵容 | 94 | roster_id, season_id, team_id, player_id, role |
| **registrations** | 报名记录 | 72 | registration_id, season_id, team_id, club_id, division, status |
| **team_aliases** | 战队别名 | 22 | alias_id, team_id, alias_name, from_date, to_date |
| **score_components** | 积分项目 | 9 | component_id, leaderboard_key, name, component_type, start_date, end_date |
| **team_component_points** | 战队积分 | 106 | id, registration_id, component_id, points, recorded_at |
| **tournament_outcomes** | 赛事成绩 | - | outcome_id, event_id, season_id, division_key, team_id, stage_reached, final_rank, country_name, country_code |
| **internal_league_results** | 内部联赛成绩 | - | id, season_id, round_date, player_name, points, total_points, rank |

### 数据关系

```
events (1) ──< seasons (N)
seasons (1) ──< divisions (N)
seasons (1) ──< registrations (N)
teams (1) ──< rosters (N)
players (1) ──< rosters (N)
registrations (1) ──< team_component_points (N)
```

---

## 2. blastjunior-content-db - 官网内容

**用途**：支撑 blastjunior.com 官网展示的内容数据

### 表结构

| 表名 | 用途 | 数据量 | 状态 | 字段 |
|------|------|--------|------|------|
| **news** | 新闻公告 | 5 | ✅ 真实 | id, title, date, tag, summary, content, image_url, link_url, status, created_at, updated_at |
| **sponsors** | 赞助商 | 4 | ✅ 真实 | id, name, level, tagline, description, logo_url, website, sort_order, status |
| **teams** | 战队展示 | 4 | ⚠️ 捏造 | id, name, tag, color, wins, draws, losses, points |
| **players** | 选手展示 | 4 | ⚠️ 捏造 | id, name, team_id, team_name, title, goals, assists, saves |
| **matches** | 比赛记录 | 3 | ⚠️ 捏造 | id, league, group_name, team1_name, team2_name, score1, score2, status, match_time |
| **media** | 媒体文件 | 0 | ❌ 空 | id, filename, file_type, uploaded_at |

### 备注
- teams/players/matches 表数据为测试时捏造，需删除或替换为真实数据
- media 表目前为空，相册功能暂无数据

---

## 3. blast-photo-db - 媒体库

**用途**：照片/相册管理系统

### 表结构

| 表名 | 用途 |
|------|------|
| uploads | 上传记录 |
| photos | 照片元数据 |
| comments | 照片评论 |

---

## 4. news-database - 旧版新闻库

**用途**：备用新闻库

| 表名 | 数据量 |
|------|--------|
| news_articles | 2 |

---

## 数据使用策略

### 网站数据流

```
blast-campaigns-db (真实联赛数据)
    ↓ (需开发同步逻辑)
blastjunior-content-db (官网展示数据)
    ↓
blast-homepage-api (Worker)
    ↓
blastjunior.com (前端页面)
```

### 当前问题

1. **数据未同步**：blast-campaigns-db 有108队+49人真实数据，但网站用的是 blastjunior-content-db 的捏造数据
2. **需决策**：是同步 blast-campaigns-db 数据到网站，还是保持现状

---

## 快速查询示例

```bash
# 查看blast-campaigns-db的战队
CLOUDFLARE_API_TOKEN="xxx" CLOUDFLARE_ACCOUNT_ID="xxx" \
  wrangler d1 execute blast-campaigns-db \
  --command="SELECT * FROM teams LIMIT 5" --remote

# 查看blastjunior-content-db的新闻
CLOUDFLARE_API_TOKEN="xxx" CLOUDFLARE_ACCOUNT_ID="xxx" \
  wrangler d1 execute blastjunior-content-db \
  --command="SELECT * FROM news" --remote
```
