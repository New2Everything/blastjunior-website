// blast-search-api - 搜索与标签API
// 从R2/D1读取数据进行搜索

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const action = url.searchParams.get("action");
    const query = url.searchParams.get("q") || "";
    const type = url.searchParams.get("type"); // all/teams/players/matches

    const cors = { 
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, OPTIONS" 
    };

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors });
    }

    try {
      let results = { teams: [], players: [], matches: [], news: [] };
      
      // 搜索战队
      if (!type || type === "all" || type === "teams") {
        try {
          const obj = await env.BUCKET.get("data/teams.json");
          if (obj) {
            const teams = JSON.parse(await obj.text());
            results.teams = query 
              ? teams.filter(t => t.name.includes(query) || (t.tag && t.tag.includes(query)))
              : teams;
          }
        } catch (e) { console.error("teams error:", e); }
      }
      
      // 搜索选手
      if (!type || type === "all" || type === "players") {
        try {
          const obj = await env.BUCKET.get("data/players.json");
          if (obj) {
            const players = JSON.parse(await obj.text());
            results.players = query
              ? players.filter(p => p.name.includes(query) || (p.title && p.title.includes(query)) || (p.team_name && p.team_name.includes(query)))
              : players;
          }
        } catch (e) { console.error("players error:", e); }
      }
      
      // 搜索比赛
      if (!type || type === "all" || type === "matches") {
        try {
          const obj = await env.BUCKET.get("data/matches.json");
          if (obj) {
            const matches = JSON.parse(await obj.text());
            results.matches = query
              ? matches.filter(m => m.team1.includes(query) || m.team2.includes(query) || m.league.includes(query))
              : matches;
          }
        } catch (e) { console.error("matches error:", e); }
      }
      
      // 搜索新闻 (D1)
      if (!type || type === "all" || type === "news") {
        try {
          const result = await env.DB.prepare("SELECT * FROM news WHERE status = 'published' AND (title LIKE ? OR summary LIKE ?) LIMIT 20")
            .bind(`%${query}%`, `%${query}%`).all();
          results.news = result.results || [];
        } catch (e) { console.error("news error:", e); }
      }

      return new Response(JSON.stringify({ ok: true, query, results }), {
        headers: { "Content-Type": "application/json", ...cors }
      });

    } catch (err) {
      return new Response(JSON.stringify({ error: err.message }), { status: 500, headers: { "Content-Type": "application/json", ...cors } });
    }
  }
};
