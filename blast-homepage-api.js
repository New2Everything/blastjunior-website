// blast-homepage-api - 首页数据聚合API
// 数据来源：D1 + R2

const STATIC_API = 'https://blast-static-api.kanjiaming2022.workers.dev';

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders() });
    }

    try {
      // 首页聚合
      if (path === "/" || path === "/home") {
        return withCors(await getHomeData(env));
      }
      
      // 新闻
      if (path === "/news") {
        return withCors(await getNews(env));
      }
      
      // 赞助商
      if (path === "/sponsors") {
        return withCors(await getSponsors(env));
      }
      
      // 战队
      if (path === "/teams") {
        return withCors(await getTeams(env));
      }
      
      // 选手
      if (path === "/players") {
        return withCors(await getPlayers(env));
      }
      
      // 比赛
      if (path === "/matches") {
        return withCors(await getMatches(env));
      }
      
      // 积分榜
      if (path === "/standings") {
        return withCors(await getStandings(env));
      }
      
      // 画廊
      if (path === "/gallery") {
        return withCors(await getGallery(env));
      }

      return withCors(jsonResponse({ ok: false, error: "Not found" }, 404));
    } catch (err) {
      return withCors(jsonResponse({ ok: false, error: "Server error", detail: String(err) }, 500));
    }
  }
};

async function getHomeData(env) {
  let news = [], sponsors = [], matches = [];
  
  try {
    const result = await env.DB.prepare("SELECT * FROM news WHERE status = 'published' ORDER BY date DESC LIMIT 5").all();
    news = result.results || [];
  } catch (e) { console.error("News error:", e); }

  try {
    const result = await env.DB.prepare("SELECT * FROM sponsors WHERE status = 'active' ORDER BY sort_order LIMIT 10").all();
    sponsors = result.results || [];
  } catch (e) { console.error("Sponsors error:", e); }

  // 从R2获取聊天消息
  let messages = [];
  try {
    const msgObj = await env.BUCKET.get("community/messages.json");
    if (msgObj) messages = JSON.parse(await msgObj.text()).slice(0, 10);
  } catch (e) { console.error(e); }

  // 从R2获取精选照片
  let featuredPhotos = [];
  try {
    const list = await env.BUCKET.list({ prefix: "public/", maxKeys: 6 });
    featuredPhotos = list.objects.map(obj => ({
      key: obj.key,
      url: `${STATIC_API}/${obj.key}`
    }));
  } catch (e) { console.error(e); }

  // 尝试从D1获取比赛
  try {
    const result = await env.DB.prepare("SELECT * FROM matches WHERE status = 'finished' ORDER BY match_time DESC LIMIT 3").all();
    matches = result.results || [];
  } catch (e) { 
    // 表可能不存在，使用默认数据
    matches = [
      { id: "1", league: "2026春季联赛", group_name: "U12", team1_name: "烈焰", team2_name: "星光", score1: 3, score2: 1, status: "finished", match_time: "今天 14:30" }
    ];
  }

  return jsonResponse({
    ok: true,
    data: {
      news,
      sponsors,
      matches,
      messages,
      onlineCount: Math.floor(Math.random() * 20) + 5,
      featuredPhotos,
      stats: { totalMatches: 24, totalPlayers: 48, totalTeams: 8 }
    }
  });
}

async function getNews(env) {
  try {
    const result = await env.DB.prepare("SELECT * FROM news WHERE status = 'published' ORDER BY date DESC LIMIT 20").all();
    return jsonResponse({ ok: true, data: result.results || [] });
  } catch (e) {
    return jsonResponse({ ok: false, error: e.message }, 500);
  }
}

async function getSponsors(env) {
  try {
    const result = await env.DB.prepare("SELECT * FROM sponsors WHERE status = 'active' ORDER BY sort_order").all();
    return jsonResponse({ ok: true, data: result.results || [] });
  } catch (e) {
    return jsonResponse({ ok: false, error: e.message }, 500);
  }
}

async function getTeams(env) {
  try {
    const result = await env.DB.prepare("SELECT * FROM teams ORDER BY points DESC").all();
    if (result.results && result.results.length > 0) {
      return jsonResponse({ ok: true, data: result.results });
    }
  } catch (e) { console.error(e); }
  
  // 默认数据
  return jsonResponse({ ok: true, data: [
    { id: "1", name: "烈焰战队", tag: "U12 竞技组", color: "fire", wins: 7, points: 22 },
    { id: "2", name: "冠军战队", tag: "U15 竞技组", color: "gold", wins: 6, points: 20 },
    { id: "3", name: "星光战队", tag: "U12 竞技组", color: "blue", wins: 5, points: 17 }
  ]});
}

async function getPlayers(env) {
  try {
    const result = await env.DB.prepare("SELECT * FROM players ORDER BY goals DESC").all();
    if (result.results && result.results.length > 0) {
      return jsonResponse({ ok: true, data: result.results });
    }
  } catch (e) { console.error(e); }
  
  return jsonResponse({ ok: true, data: [
    { id: "1", name: "小狮子", team_id: "1", title: "得分王", goals: 28, assists: 12 },
    { id: "2", name: "闪电侠", team_id: "2", title: "MVP", goals: 25, assists: 15 }
  ]});
}

async function getMatches(env) {
  try {
    const result = await env.DB.prepare("SELECT * FROM matches ORDER BY match_time DESC").all();
    if (result.results && result.results.length > 0) {
      return jsonResponse({ ok: true, data: result.results });
    }
  } catch (e) { console.error(e); }
  
  return jsonResponse({ ok: true, data: [
    { id: "1", league: "2026春季联赛", group_name: "U12", team1_name: "烈焰", team2_name: "星光", score1: 3, score2: 1, status: "finished", match_time: "2026-03-05 14:30" }
  ]});
}

async function getStandings(env) {
  try {
    const result = await env.DB.prepare("SELECT * FROM teams ORDER BY points DESC").all();
    if (result.results && result.results.length > 0) {
      const standings = result.results.map((t, i) => ({
        rank: i + 1,
        team: t.name,
        wins: t.wins,
        draws: t.draws || 0,
        losses: t.losses || 0,
        goals: (t.wins * 2) - t.losses,
        points: t.points
      }));
      return jsonResponse({ ok: true, data: standings });
    }
  } catch (e) { console.error(e); }
  
  return jsonResponse({ ok: true, data: [
    { rank: 1, team: "烈焰", wins: 7, draws: 1, losses: 0, goals: 22, points: 22 }
  ]});
}

async function getGallery(env) {
  let albums = [];
  try {
    const list = await env.BUCKET.list({ prefix: "public/", maxKeys: 20 });
    albums = list.objects.map((obj, i) => ({
      id: i + 1,
      title: obj.key.replace("public/", "").replace(/\.[^.]+$/, ""),
      cover: `${STATIC_API}/${obj.key}`,
      count: Math.floor(Math.random() * 20) + 10,
      date: "2026-03-01",
      type: ["赛事", "训练", "活动", "人物"][i % 4]
    }));
  } catch (e) { albums = []; }
  return jsonResponse({ ok: true, data: albums });
}

function corsHeaders() {
  return { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET, OPTIONS" };
}

function withCors(resp) {
  const h = new Headers(resp.headers);
  for (const [k, v] of Object.entries(corsHeaders())) h.set(k, v);
  return new Response(resp.body, { status: resp.status, headers: h });
}

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data, null, 2), { status, headers: { "Content-Type": "application/json" } });
}
