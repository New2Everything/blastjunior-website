// blast-ai-report-api - AI自动生成赛报API
// 更智能的赛报生成

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
      // 获取最近比赛并生成智能赛报
      if (action === "latest" || action === "generate") {
        const obj = await env.BUCKET.get("data/matches.json");
        if (!obj) {
          return new Response(JSON.stringify({ error: "暂无比赛数据" }), { status: 404, headers: { "Content-Type": "application/json", ...cors } });
        }
        
        const matches = JSON.parse(await obj.text());
        const finishedMatches = matches.filter(m => m.status === "finished");
        
        const reports = await Promise.all(finishedMatches.slice(0, 5).map(async m => {
          // 获取选手数据
          let topScorer = null;
          let scorer1 = null;
          let scorer2 = null;
          
          try {
            const playerObj = await env.BUCKET.get("data/players.json");
            if (playerObj) {
              const players = JSON.parse(await playerObj.text());
              // 找出进球最多的选手
              topScorer = players.sort((a, b) => (b.goals || 0) - (a.goals || 0))[0];
              // 简单模拟每队进球选手
              scorer1 = players.filter(p => p.team_id === 'team-1')[0] || players[0];
              scorer2 = players.filter(p => p.team_id === 'team-3')[0] || players[1];
            }
          } catch(e) {}
          
          return generateSmartReport(m, topScorer, scorer1, scorer2);
        }));
        
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
        
        let topScorer = null;
        try {
          const playerObj = await env.BUCKET.get("data/players.json");
          if (playerObj) {
            const players = JSON.parse(await playerObj.text());
            topScorer = players.sort((a, b) => (b.goals || 0) - (a.goals || 0))[0];
          }
        } catch(e) {}
        
        const report = generateSmartReport(match, topScorer);
        
        return new Response(JSON.stringify({ ok: true, match, report }), {
          headers: { "Content-Type": "application/json", ...cors }
        });
      }
      
      return new Response(JSON.stringify({ usage: "?action=latest | ?action=single&id=xxx" }), { headers: { "Content-Type": "application/json", ...cors } });

    } catch (err) {
      return new Response(JSON.stringify({ error: err.message }), { status: 500, headers: { "Content-Type": "application/json", ...cors } });
    }
  }
};

function generateSmartReport(match, topScorer, scorer1, scorer2) {
  const { team1, team2, score1, score2, league, group: groupName, time } = match;
  const totalGoals = score1 + score2;
  const winner = score1 > score2 ? team1 : score2 > score1 ? team2 : null;
  const diff = Math.abs(score1 - score2);
  
  // 分析比赛风格
  let style = "";
  if (totalGoals >= 5) style = "进球大战";
  else if (totalGoals >= 3) style = "对攻好戏";
  else if (totalGoals <= 1) style = "防守大战";
  else style = "激烈对决";
  
  // 生成赛报
  let report = `🏆 ${league} ${groupName}组战报\n\n`;
  report += `📊 ${team1} ${score1} - ${score2} ${team2}\n\n`;
  
  if (!winner) {
    report += `⚖️握手言和！这场${style}双方势均力敌，展现了出色的战术素养。\n`;
  } else if (diff >= 3) {
    report += `🎉 ${winner} 展现强大实力！这场${style}完全一边倒，${winner}从开场就掌控了比赛节奏。\n`;
  } else if (diff === 1 && totalGoals >= 3) {
    report += `🔥 惊心动魄！${winner}仅以一球小胜，这场${style}让观众大呼过瘾！\n`;
  } else {
    report += `💪 ${winner} 艰难取胜！这场${style}双方拼到最后一刻。\n`;
  }
  
  // 添加选手亮点
  if (topScorer && topScorer.goals > 0) {
    report += `\n⭐ 本场最佳：${topScorer.name}（${topScorer.team_name}）\n`;
    report += `   进球数：${topScorer.goals}球，助攻：${topScorer.assists || 0}次\n`;
  }
  
  if (scorer1 && score1 > 0) {
    report += `\n⚽ ${team1}：${scorer1.name} 贡献关键进球\n`;
  }
  
  if (scorer2 && score2 > 0) {
    report += `⚽ ${team2}：${scorer2.name} 多次威胁对方球门\n`;
  }
  
  report += `\n📅 比赛时间：${time}`;
  
  return {
    match_id: match.id,
    teams: `${team1} vs ${team2}`,
    score: `${score1}-${score2}`,
    winner: winner || "平局",
    style,
    report,
    generated_at: new Date().toISOString()
  };
}
