// blast-ai-report-api - AI自动生成赛报API
// 基于比赛数据生成简单赛报

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const action = url.searchParams.get("action");

    const cors = { 
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, OPTIONS" 
    };

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors });
    }

    try {
      // 获取最近比赛并生成赛报
      if (action === "generate" || action === "latest") {
        const obj = await env.BUCKET.get("data/matches.json");
        if (!obj) {
          return new Response(JSON.stringify({ error: "暂无比赛数据" }), { status: 404, headers: { "Content-Type": "application/json", ...cors } });
        }
        
        const matches = JSON.parse(await obj.text());
        const finishedMatches = matches.filter(m => m.status === "finished").slice(0, 5);
        
        const reports = finishedMatches.map(m => {
          const winner = m.score1 > m.score2 ? m.team1 : m.score2 > m.score1 ? m.team2 : "平局";
          const diff = Math.abs(m.score1 - m.score2);
          
          // 生成简报
          let report = `🏆 ${m.league} ${m.group}组比赛战报\n\n`;
          report += `${m.team1} ${m.score1} - ${m.score2} ${m.team2}\n\n`;
          
          if (diff === 0) {
            report += `双方握手言和！`;
          } else if (diff >= 3) {
            report += `${winner} 大比分获胜！`;
          } else {
            report += `${winner} 险胜对手！`;
          }
          
          report += `\n\n📅 比赛时间：${m.time}`;
          
          return {
            match_id: m.id,
            teams: `${m.team1} vs ${m.team2}`,
            score: `${m.score1}-${m.score2}`,
            report: report,
            generated_at: new Date().toISOString()
          };
        });
        
        return new Response(JSON.stringify({ ok: true, count: reports.length, reports }), {
          headers: { "Content-Type": "application/json", ...cors }
        });
      }
      
      // 生成单场比赛赛报
      if (action === "single" && url.searchParams.get("id")) {
        const matchId = url.searchParams.get("id");
        
        const obj = await env.BUCKET.get("data/matches.json");
        if (!obj) {
          return new Response(JSON.stringify({ error: "暂无比赛数据" }), { status: 404, headers: { "Content-Type": "application/json", ...cors } });
        }
        
        const matches = JSON.parse(await obj.text());
        const match = matches.find(m => m.id === matchId);
        
        if (!match) {
          return new Response(JSON.stringify({ error: "比赛不存在" }), { status: 404, headers: { "Content-Type": "application/json", ...cors } });
        }
        
        const winner = match.score1 > match.score2 ? match.team1 : match.score2 > match.score1 ? match.team2 : "平局";
        const diff = Math.abs(match.score1 - match.score2);
        
        let report = `🏆 ${match.league} ${match.group}组比赛战报\n\n`;
        report += `${match.team1} ${match.score1} - ${match.score2} ${match.team2}\n\n`;
        
        if (diff === 0) {
          report += `双方握手言和！`;
        } else if (diff >= 3) {
          report += `${winner} 大比分获胜，展现强大实力！`;
        } else {
          report += `${winner} 艰难取胜，比赛非常激烈！`;
        }
        
        report += `\n\n📅 比赛时间：${match.time}`;
        
        return new Response(JSON.stringify({ ok: true, match, report }), {
          headers: { "Content-Type": "application/json", ...cors }
        });
      }
      
      return new Response(JSON.stringify({ 
        usage: [
          "?action=latest - 获取最近赛报",
          "?action=single&id=match-1 - 生成单场比赛赛报"
        ]
      }), { headers: { "Content-Type": "application/json", ...cors } });

    } catch (err) {
      return new Response(JSON.stringify({ error: err.message }), { status: 500, headers: { "Content-Type": "application/json", ...cors } });
    }
  }
};
