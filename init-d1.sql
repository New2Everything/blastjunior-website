-- 战队表
CREATE TABLE IF NOT EXISTS teams (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    tag TEXT,
    color TEXT DEFAULT 'blue',
    wins INTEGER DEFAULT 0,
    draws INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    points INTEGER DEFAULT 0,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 选手表
CREATE TABLE IF NOT EXISTS players (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    team_id TEXT,
    title TEXT,
    goals INTEGER DEFAULT 0,
    assists INTEGER DEFAULT 0,
    saves INTEGER DEFAULT 0,
    avatar TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (team_id) REFERENCES teams(id)
);

-- 比赛表
CREATE TABLE IF NOT EXISTS matches (
    id TEXT PRIMARY KEY,
    league TEXT NOT NULL,
    group_name TEXT,
    team1_id TEXT,
    team2_id TEXT,
    team1_name TEXT,
    team2_name TEXT,
    score1 INTEGER DEFAULT 0,
    score2 INTEGER DEFAULT 0,
    status TEXT DEFAULT 'upcoming',
    match_time TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 插入初始战队数据
INSERT OR REPLACE INTO teams (id, name, tag, color, wins, draws, losses, points) VALUES
('team-1', '烈焰战队', 'U12 竞技组', 'fire', 7, 1, 0, 22),
('team-2', '冠军战队', 'U15 竞技组', 'gold', 6, 2, 0, 20),
('team-3', '星光战队', 'U12 竞技组', 'blue', 5, 2, 1, 17),
('team-4', '雷霆战队', 'U15 训练组', 'purple', 4, 1, 3, 13),
('team-5', '铁壁战队', 'U12 训练组', 'green', 3, 2, 3, 11),
('team-6', '海浪战队', 'U18 竞技组', 'cyan', 2, 1, 5, 7);

-- 插入初始选手数据
INSERT OR REPLACE INTO players (id, name, team_id, title, goals, assists) VALUES
('player-1', '小狮子', 'team-1', '得分王', 28, 12),
('player-2', '闪电侠', 'team-2', 'MVP', 25, 15),
('player-3', '铁壁', 'team-5', '最佳守门', 0, 5),
('player-4', '旋风', 'team-3', '助攻王', 18, 22),
('player-5', '火焰', 'team-1', '前锋', 24, 10),
('player-6', '星星', 'team-3', '中场', 15, 18);

-- 插入初始比赛数据
INSERT OR REPLACE INTO matches (id, league, group_name, team1_name, team2_name, score1, score2, status, match_time) VALUES
('match-1', '2026春季联赛', 'U12', '烈焰战队', '星光战队', 3, 1, 'finished', '2026-03-05 14:30'),
('match-2', '2026春季联赛', 'U15', '冠军战队', '雷霆战队', 2, 2, 'finished', '2026-03-04 16:00'),
('match-3', '2026春季联赛', 'U12', '烈焰战队', '铁壁战队', 0, 0, 'upcoming', '2026-03-07 14:30'),
('match-4', '2026春季联赛', 'U15', '冠军战队', '海浪战队', 0, 0, 'upcoming', '2026-03-08 10:00');
