-- ================================================
-- BLXST 新版数据库架构（避免与旧表名冲突）
-- 2026-04-18
-- ================================================

-- 俱乐部表
CREATE TABLE IF NOT EXISTS blxst_clubs (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    logo TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 用户表（成员、领队、管理、赞助商等）
CREATE TABLE IF NOT EXISTS blxst_users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    nickname TEXT,
    real_name TEXT,
    avatar TEXT,
    role TEXT DEFAULT 'member' CHECK(role IN ('leader', 'admin', 'member', 'support', 'sponsor')),
    player_level TEXT CHECK(player_level IN ('T0', 'elite', 'rookie', 'newbie', NULL)),
    club_id TEXT REFERENCES blxst_clubs(id),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 战队表
CREATE TABLE IF NOT EXISTS blxst_teams (
    id TEXT PRIMARY KEY,
    club_id TEXT NOT NULL REFERENCES blxst_clubs(id),
    name TEXT NOT NULL,
    description TEXT,
    captain_id TEXT REFERENCES blxst_users(id),
    logo TEXT,
    status TEXT DEFAULT 'active' CHECK(status IN ('active', 'inactive')),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 战队成员关系表（包含审批状态）
CREATE TABLE IF NOT EXISTS blxst_team_members (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL REFERENCES blxst_teams(id),
    user_id TEXT NOT NULL REFERENCES blxst_users(id),
    role_in_team TEXT DEFAULT 'member' CHECK(role_in_team IN ('captain', 'vice_captain', 'member')),
    status TEXT DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected')),
    current INTEGER DEFAULT 1 CHECK(current IN (0, 1)),
    joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
    left_at TEXT,
    approved_by TEXT REFERENCES blxst_users(id),
    UNIQUE(team_id, user_id)
);

-- 赛季表
CREATE TABLE IF NOT EXISTS blxst_seasons (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    start_date TEXT,
    end_date TEXT,
    status TEXT DEFAULT 'upcoming' CHECK(status IN ('upcoming', 'ongoing', 'finished')),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 赛季分数表（老K直接导入）
CREATE TABLE IF NOT EXISTS blxst_season_scores (
    id TEXT PRIMARY KEY,
    season_id TEXT NOT NULL REFERENCES blxst_seasons(id),
    team_id TEXT REFERENCES blxst_teams(id),
    team_name TEXT,
    rank INTEGER,
    points INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    draws INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    goals_for INTEGER DEFAULT 0,
    goals_against INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(season_id, team_id)
);

-- 新闻表
CREATE TABLE IF NOT EXISTS blxst_news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    content TEXT,
    category TEXT,
    author_id TEXT REFERENCES blxst_users(id),
    published_at TEXT DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'published' CHECK(status IN ('draft', 'published'))
);

-- ================================================
-- 初始化数据
-- ================================================

-- 插入俱乐部
INSERT INTO blxst_clubs (id, name, description) VALUES 
('club-lanxing', '兰星少年 HADO 俱乐部', '专业HADO运动俱乐部');

-- 插入管理员账号（密码: 123456）
INSERT INTO blxst_users (id, email, password_hash, nickname, real_name, role, club_id) VALUES 
('admin-1', 'admin@blastjunior.com', '8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92', '管理员', '阚家鸣', 'admin', 'club-lanxing');
-- 8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92 = 123456 (SHA256)

-- 插入示例赛季
INSERT INTO blxst_seasons (id, name, status) VALUES 
('season-2026-s1', '2026春季赛季', 'ongoing');
