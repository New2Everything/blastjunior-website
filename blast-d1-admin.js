export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const action = url.searchParams.get("action");
    
    const cors = { "Access-Control-Allow-Origin": "*", "Content-Type": "application/json" };
    
    try {
      // 创建表
      if (action === "create_tables") {
        await env.DB.exec(`
          CREATE TABLE IF NOT EXISTS teams (
            id TEXT PRIMARY KEY,
            name TEXT,
            tag TEXT,
            color TEXT,
            wins INTEGER DEFAULT 0,
            draws INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            points INTEGER DEFAULT 0
          );
          CREATE TABLE IF NOT EXISTS players (
            id TEXT PRIMARY KEY,
            name TEXT,
            team_id TEXT,
            team_name TEXT,
            title TEXT,
            goals INTEGER DEFAULT 0,
            assists INTEGER DEFAULT 0,
            saves INTEGER DEFAULT 0
          );
          CREATE TABLE IF NOT EXISTS matches (
            id TEXT PRIMARY KEY,
            league TEXT,
            group_name TEXT,
            team1_name TEXT,
            team2_name TEXT,
            score1 INTEGER DEFAULT 0,
            score2 INTEGER DEFAULT 0,
            status TEXT DEFAULT 'upcoming',
            match_time TEXT
          );
        `);
        return new Response(JSON.stringify({ ok: true, message: "表创建成功" }), { headers: cors });
      }
      
      // 插入数据
      if (action === "insert_data") {
        // 战队
        await env.DB.prepare(`INSERT OR REPLACE INTO teams VALUES (?, ?, ?, ?, ?, ?, ?, ?)`)
          .bind('team-1', '烈焰战队', 'U12 竞技组', 'fire', 7, 1, 0, 22).run();
        await env.DB.prepare(`INSERT OR REPLACE INTO teams VALUES (?, ?, ?, ?, ?, ?, ?, ?)`)
          .bind('team-2', '冠军战队', 'U15 竞技组', 'gold', 6, 2, 0, 20).run();
        await env.DB.prepare(`INSERT OR REPLACE INTO teams VALUES (?, ?, ?, ?, ?, ?, ?, ?)`)
          .bind('team-3', '星光战队', 'U12 竞技组', 'blue', 5, 2, 1, 17).run();
        await env.DB.prepare(`INSERT OR REPLACE INTO teams VALUES (?, ?, ?, ?, ?, ?, ?, ?)`)
          .bind('team-4', '雷霆战队', 'U15 训练组', 'purple', 4, 1, 3, 13).run();
        
        // 选手
        await env.DB.prepare(`INSERT OR REPLACE INTO players VALUES (?, ?, ?, ?, ?, ?, ?)`)
          .bind('player-1', '小狮子', 'team-1', '烈焰战队', '得分王', 28, 12).run();
        await env.DB.prepare(`INSERT OR REPLACE INTO players VALUES (?, ?, ?, ?, ?, ?, ?)`)
          .bind('player-2', '闪电侠', 'team-2', '冠军战队', 'MVP', 25, 15).run();
        await env.DB.prepare(`INSERT OR REPLACE INTO players VALUES (?, ?, ?, ?, ?, ?, ?)`)
          .bind('player-3', '铁壁', 'team-4', '雷霆战队', '最佳守门', 0, 5).run();
        await env.DB.prepare(`INSERT OR REPLACE INTO players VALUES (?, ?, ?, ?, ?, ?, ?)`)
          .bind('player-4', '旋风', 'team-3', '星光战队', '助攻王', 18, 22).run();
        
        // 比赛
        await env.DB.prepare(`INSERT OR REPLACE INTO matches VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`)
          .bind('match-1', '2026春季联赛', 'U12', '烈焰战队', '星光战队', 3, 1, 'finished', '2026-03-05 14:30').run();
        await env.DB.prepare(`INSERT OR REPLACE INTO matches VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`)
          .bind('match-2', '2026春季联赛', 'U15', '冠军战队', '雷霆战队', 2, 2, 'finished', '2026-03-04 16:00').run();
        await env.DB.prepare(`INSERT OR REPLACE INTO matches VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`)
          .bind('match-3', '2026春季联赛', 'U12', '烈焰战队', '铁壁战队', 0, 0, 'upcoming', '2026-03-07 14:30').run();
        
        return new Response(JSON.stringify({ ok: true, message: "数据插入成功" }), { headers: cors });
      }
      
      // 查询表
      if (action === "tables") {
        const { results } = await env.DB.prepare("SELECT name FROM sqlite_master WHERE type='table'").all();
        return new Response(JSON.stringify(results), { headers: cors });
      }
      
      // 查询数据
      if (action === "query" && url.searchParams.get("table")) {
        const table = url.searchParams.get("table");
        const { results } = await env.DB.prepare(`SELECT * FROM ${table}`).all();
        return new Response(JSON.stringify(results), { headers: cors });
      }
      
      return new Response(JSON.stringify({ usage: "?action=create_tables | ?action=insert_data | ?action=tables | ?action=query&table=xxx" }), { headers: cors });
      
    } catch (err) {
      return new Response(JSON.stringify({ error: err.message }), { status: 500, headers: cors });
    }
  }
};
