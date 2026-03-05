// blast-share-api - 一键分享卡生成API
// 生成比赛/选手/战队/荣誉的分享卡片

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const type = url.searchParams.get("type"); // match/player/team
    const id = url.searchParams.get("id");

    const cors = { 
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, OPTIONS" 
    };

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors });
    }

    try {
      if (!type || !id) {
        return new Response(JSON.stringify({ 
          error: "缺少参数，需要 type 和 id",
          usage: "/?type=match&id=match-1 | /?type=player&id=player-1 | /?type=team&id=team-1"
        }), { status: 400, headers: { "Content-Type": "application/json", ...cors } });
      }

      let cardData = {};

      // 获取分享数据
      if (type === "match") {
        const obj = await env.BUCKET.get("data/matches.json");
        if (obj) {
          const matches = JSON.parse(await obj.text());
          const match = matches.find(m => m.id === id);
          if (match) {
            cardData = {
              type: "比赛",
              title: `${match.team1} vs ${match.team2}`,
              subtitle: match.status === "finished" 
                ? `⚽ ${match.score1} - ${match.score2} 已结束`
                : `⏰ ${match.time} 即将开始`,
              league: match.league,
              tags: [match.group, match.status === "finished" ? "已结束" : "未开始"]
            };
          }
        }
      } else if (type === "player") {
        const obj = await env.BUCKET.get("data/players.json");
        if (obj) {
          const players = JSON.parse(await obj.text());
          const player = players.find(p => p.id === id);
          if (player) {
            cardData = {
              type: "选手",
              title: player.name,
              subtitle: player.title || "",
              team: player.team_name,
              tags: [`⚽ ${player.goals}球`, `🅰️ ${player.assists}助攻`]
            };
          }
        }
      } else if (type === "team") {
        const obj = await env.BUCKET.get("data/teams.json");
        if (obj) {
          const teams = JSON.parse(await obj.text());
          const team = teams.find(t => t.id === id);
          if (team) {
            cardData = {
              type: "战队",
              title: team.name,
              subtitle: team.tag,
              tags: [`🏆 ${team.points}分`, `✅ ${team.wins}胜`]
            };
          }
        }
      }

      if (!cardData.title) {
        return new Response(JSON.stringify({ error: "未找到对应数据" }), { status: 404, headers: { "Content-Type": "application/json", ...cors } });
      }

      return new Response(JSON.stringify({ ok: true, data: cardData }), {
        headers: { "Content-Type": "application/json", ...cors }
      });

    } catch (err) {
      return new Response(JSON.stringify({ error: err.message }), { status: 500, headers: { "Content-Type": "application/json", ...cors } });
    }
  }
};
