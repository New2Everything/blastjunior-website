# BLXST 数据源属性分析

> 来源：blast-campaigns-db
> 日期：2026-03-06
> 用途：分析每个数据源的属性，确定哪些应该在网站展示

---

## 数据源属性清单

### 1. events（赛事）
| 属性 | 类型 | 说明 | 网站展示? |
|------|------|------|----------|
| event_id | TEXT | 赛事ID | ✅ 用于关联 |
| name_zh | TEXT | 中文名 | ✅ Honor Room |
| name_en | TEXT | 英文名 | ✅ 展示| |
| level | TEXT | 级别 | ❌ 技术字段 |
| frequency | TEXT | 举办频率 | ❌ 技术字段 |
| official_url | TEXT | 官网链接 | ✅ 展示| |
| description | TEXT | 描述 | ✅ 展示| |

### 2. seasons（赛季）
| 属性 | 类型 | 说明 | 网站展示? |
|------|------|------|----------|
| season_id | TEXT | 赛季ID | ✅ 用于关联 |
| name | TEXT | 赛季名称 | ✅ Matches选择 |
| year | INTEGER | 年份 | ✅ 显示年份 |
| start_date | TEXT | 开始日期 | ✅ 展示| |
| end_date | TEXT | 结束日期 | ✅ 展示| |
| status | TEXT | 状态 | ✅ 展示|（进行中/已结束）|

### 3. divisions（组别）
| 属性 | 类型 | 说明 | 网站展示? |
|------|------|------|----------|
| division_id | TEXT | 组别ID | ✅ 用于关联 |
| season_id | TEXT | 赛季ID | ✅ 用于关联 |
| division_key | TEXT | 组别键(rookie/elite) | ✅ 用于筛选 |
| name | TEXT | 组别名称(HADO WORLD精英赛) | ✅ 显示组别名称 |
| sort_order | INTEGER | 排序 | ❌ 技术字段 |

### 4. players（选手）
| 属性 | 类型 | 说明 | 网站展示? |
|------|------|------|----------|
| player_id | TEXT | 选手ID | ✅ 用于关联 |
| nickname | TEXT | 昵称 | ✅ Players列表 |
| display_name | TEXT | 显示名 | ✅ 详情页 |
| real_name | TEXT | 真名 | ✅ 展示| |
| birth_year | INTEGER | 出生年 | ✅ 展示|（隐私考虑）|
| is_active | INTEGER | 是否活跃 | ✅ 显示状态 |
| club_name | TEXT | 俱乐部 | ✅ Players详情 |
| notes | TEXT | 备注 | ❌ 不展示 |
| created_at | TEXT | 创建时间 | ❌ 技术字段 |

### 5. teams（战队）
| 属性 | 类型 | 说明 | 网站展示? |
|------|------|------|----------|
| team_id | TEXT | 战队ID | ✅ 用于关联 |
| canonical_name | TEXT | 正式名称 | ✅ Teams列表 |
| club_id | TEXT | 俱乐部ID | ✅ 展示| |
| first_season_id | TEXT | 首次参赛赛季 | ❌ 技术字段 |
| note | TEXT | 备注 | ❌ 不展示 |
| team_type | TEXT | 战队类型 | ✅ 展示| |
| team_code | TEXT | 战队代码 | ✅ 展示| |

### 6. rosters（阵容）
| 属性 | 类型 | 说明 | 网站展示? |
|------|------|------|----------|
| roster_id | TEXT | 阵容ID | ✅ 用于关联 |
| season_id | TEXT | 赛季ID | ✅ 阵容详情 |
| team_id | TEXT | 战队ID | ✅ 用于关联 |
| player_id | TEXT | 选手ID | ✅ 阵容详情 |
| role | TEXT | 角色 | ✅ 展示|（队长/成员）|

### 7. registrations（报名）
| 属性 | 类型 | 说明 | 网站展示? |
|------|------|------|----------|
| registration_id | TEXT | 报名ID | ✅ 用于关联 |
| season_id | TEXT | 赛季ID | ✅ 参赛队伍 |
| team_id | TEXT | 战队ID | ✅ 参赛队伍 |
| club_id | TEXT | 俱乐部ID | ✅ 展示| |
| division | TEXT | 组别 | ✅ 参赛队伍 |
| status | TEXT | 状态 | ✅ 展示| |

### 8. team_aliases（战队别名）
| 属性 | 类型 | 说明 | 网站展示? |
|------|------|------|----------|
| alias_id | TEXT | 别名ID | ✅ 用于关联 |
| team_id | TEXT | 战队ID | ✅ 用于关联 |
| alias_name | TEXT | 别名 | ✅ 展示|（是否展示曾用名）|
| from_date | TEXT | 起始日期 | ❌ 不展示 |
| to_date | TEXT | 结束日期 | ❌ 不展示 |

### 9. score_components（积分项目）
| 属性 | 类型 | 说明 | 网站展示? |
|------|------|------|----------|
| component_id | TEXT | 积分项目ID | ✅ 用于关联 |
| name | TEXT | 项目名称 | ✅ Standings规则 |
| component_type | TEXT | 项目类型 | ✅ 展示| |
| sort_order | INTEGER | 排序 | ❌ 技术字段 |

### 10. team_component_points（战队积分）
| 属性 | 类型 | 说明 | 网站展示? |
|------|------|------|----------|
| id | TEXT | 记录ID | ❌ 技术字段 |
| registration_id | TEXT | 报名ID | ✅ 用于关联 |
| component_id | TEXT | 积分项目ID | ✅ 用于关联 |
| points | INTEGER | 积分 | ✅ Standings |
| recorded_at | TEXT | 记录时间 | ❌ 不展示 |

### 11. tournament_outcomes（赛事成绩）
| 属性 | 类型 | 说明 | 网站展示? |
|------|------|------|----------|
| outcome_id | TEXT | 成绩ID | ✅ 用于关联 |
| event_id | TEXT | 赛事ID | ✅ Honor |
| season_id | TEXT | 赛季ID | ✅ Honor |
| division_key | TEXT | 组别键 | ✅ 展示| |
| team_id | TEXT | 战队ID | ✅ Honor |
| stage_reached | TEXT | 晋级阶段 | ✅ Honor |
| final_rank | TEXT | 最终排名 | ✅ Honor |
| country_name | TEXT | 国家/地区 | ✅ Honor |
| country_code | TEXT | 国家代码 | ❌ 技术字段 |

### 12. internal_league_results（内部联赛）
| 属性 | 类型 | 说明 | 网站展示? |
|------|------|------|----------|
| id | TEXT | 记录ID | ❌ 技术字段 |
| season_id | TEXT | 赛季ID | ✅ 轮次详情 |
| round_date | TEXT | 轮次日期 | ✅ Matches轮次 |
| player_name | TEXT | 选手名 | ✅ 轮次榜单 |
| points | INTEGER | 本轮得分 | ✅ 轮次榜单 |
| total_points | INTEGER | 总积分 | ✅ 轮次榜单 |
| rank | INTEGER | 排名 | ✅ 轮次榜单 |

---

## 待确认属性（需老K决策）

> 2026-03-06: 老K确认全部可以展示 ✅

| 数据源 | 属性 | 展示 | 备注 |
|--------|------|------|------|
| events | name_en | ✅ | 英文名 |
| events | official_url | ✅ | 赛事官网链接 |
| events | description | ✅ | 赛事描述 |
| seasons | start_date | ✅ | 开始日期 |
| seasons | end_date | ✅ | 结束日期 |
| seasons | status | ✅ | 赛季状态 |
| players | birth_year | ✅ | 出生年 |
| teams | team_type | ✅ | 战队类型 |
| teams | club_id | ✅ | 俱乐部ID |
| divisions | name | ✅ | 组别名称 |
| rosters | role | ✅ | 队长/成员 |
| team_aliases | alias_name | ✅ | 曾用名 |

---

## 统计

- ✅ 已展示属性: 56个 (75%)
- ❌ 不展示属性: 14个 (19%)
- ⚠️ 待确认: 0个（老K已确认全部展示）
- 不展示（技术字段）：约15个
- 待确认：约20个

---

## 附录：HADO业务关系（2026-03-06）

### 实体层级

```
赛事 (events)
    ├── 赛季 (seasons)
    │       ├── 组别 (divisions)
    │       └── 参赛报名 (registrations)
    │               └── 战队 (teams)
    │                       ├── 阵容 (rosters)
    │                       │       └── 选手 (players)
    │                       └── 积分 (team_component_points)
    └── 荣誉 (tournament_outcomes)

内部联赛 (internal_league_results) - 独立系统
```

### 核心关系

1. **赛事 > 赛季 > 组别**: 层级包含关系
2. **战队通过报名参加赛季**: registrations表
3. **选手通过阵容属于战队**: rosters表（有赛季属性）
4. **积分来自多个项目累加**: score_components
5. **内部联赛独立于官方赛事**: 俱乐部内部训练赛

### 业务查询示例

```sql
-- 某战队在某赛季的阵容
SELECT p.* FROM players p
JOIN rosters r ON p.player_id = r.player_id
WHERE r.team_id = 'TEAM002' AND r.season_id = 'hpl_s2_2025'

-- 某战队在某赛季的积分
SELECT sc.name, tcp.points 
FROM team_component_points tcp
JOIN score_components sc ON tcp.component_id = sc.component_id
JOIN registrations r ON tcp.registration_id = r.registration_id
WHERE r.team_id = 'TEAM002' AND r.season_id = 'hpl_s2_2025'
```
