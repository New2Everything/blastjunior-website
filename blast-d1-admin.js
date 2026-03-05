export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const action = url.searchParams.get("action");
    
    if (action === "init") {
      // 创建表
      await env.DB.exec(`
        CREATE TABLE IF NOT EXISTS teams (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, tag TEXT, color TEXT DEFAULT 'blue',
          wins INTEGER DEFAULT 0, draws INTEGER DEFAULT 0, losses INTEGER DEFAULT 0, points INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS players (
          id TEXT PRIMARY KEY, name TEXT NOT NULL, team_id TEXT, title TEXT,
          goals INTEGER DEFAULT 0, assists INTEGER DEFAULT 0, saves INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS matches (
          id TEXT PRIMARY KEY, league TEXT NOT NULL, group_name TEXT,
          team1_name TEXT, team2_name TEXT, score1 INTEGER DEFAULT 0, score2 INTEGER DEFAULT 0,
          status TEXT DEFAULT 'upcoming', match_time TEXT
        );
      `);
      
      // 插入数据
      await env.DB.exec(`
        INSERT OR REPLACE INTO teams VALUES 
          ('team-1', '烈焰战队', 'U12 竞技组', 'fire', 7, 1, 0, 22),
          ('team-2', '冠军战队', 'U15 竞技组', 'gold', 6, 2, 0, 20),
          ('team-3', '星光战队', 'U12 竞技组', 'blue', 5, 2, 1, 17),
          ('team-4', '雷霆战队', 'U15 训练组', 'purple', 4, 1, 3, 13);
          
        INSERT OR REPLACE INTO players VALUES
          ('player-1', '小狮子', 'team-1', '得分王', 28, 12),
          ('player-2', '闪电侠', 'team-2', 'MVP', 25, 15),
          ('player-3', '铁壁', 'team-4', '最佳守门', 0, 5);
          
        INSERT OR REPLACE INTO matches VALUES
          ('match-1', '2026春季联赛', 'U12', '烈焰战队', '星光战队', 3, 1, 'finished', '2026-03-05 14:30'),
          ('match-2', '2026春季联赛', 'U15', '冠军战队', '雷霆战队', 2, 2, 'finished', '2026-03-04 16:00'),
          ('match-3', '2026春季联赛', 'U12', '烈焰战队', '星光战队', 0, 0, 'upcoming', '2026-03-07 14:30');
      `);
      
      return new Response(JSON.stringify({ ok: true, message: "D1 initialized!" }), {
        headers: { "Content-Type": "application/json" }
      });
    }
    
    // 查询表
    if (action === "tables") {
      const { results } = await env.DB.prepare("SELECT name FROM sqlite_master WHERE type='table'").all();
      return new Response(JSON.stringify(results), { headers: { "Content-Type": "application/json" } });
    }
    
    return new Response("Use ?action=init or ?action=tables");
  }
};
