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
      
      // 新闻列表
      if (path === "/news") {
        return withCors(await getNews(env));
      }
      
      // 赞助商
      if (path === "/sponsors") {
        return withCors(await getSponsors(env));
      }
      
      // 赛程
      if (path === "/matches") return withCors(await getMatches(env));
      // 积分榜
      if (path === "/standings") return withCors(await getStandings(env));
      // 战队
      if (path === "/teams") return withCors(await getTeams(env));
      // 选手
      if (path === "/players") return withCors(await getPlayers(env));
      // 画廊
      if (path === "/gallery") return withCors(await getGallery(env));

      return withCors(jsonResponse({ ok: false, error: "Not found" }, 404));
    } catch (err) {
      return withCors(jsonResponse({ ok: false, error: "Server error", detail: String(err) }, 500));
    }
  }
};

async function getHomeData(env) {
  // 从D1获取新闻
  let news = [];
  try {
    const result = await env.DB.prepare("SELECT * FROM news WHERE status = 'published' ORDER BY date DESC LIMIT 5").all();
    news = result.results || [];
  } catch (e) { console.error("News error:", e); }

  // 从D1获取赞助商
  let sponsors = [];
  try {
    const result = await env.DB.prepare("SELECT * FROM sponsors WHERE status = 'active' ORDER BY sort_order LIMIT 10").all();
    sponsors = result.results || [];
  } catch (e) { console.error("Sponsors error:", e); }

  // 从R2获取聊天消息
  let messages = [];
  try {
    const msgObj = await env.BUCKET.get("community/messages.json");
    if (msgObj) messages = JSON.parse(await msgObj.text()).slice(0, 10);
  } catch (e) { console.error("Messages error:", e); }

  // 从R2获取精选照片
  let featuredPhotos = [];
  try {
    const list = await env.BUCKET.list({ prefix: "public/", maxKeys: 6 });
    featuredPhotos = list.objects.map(obj => ({
      key: obj.key,
      url: `${STATIC_API}/${obj.key}`
    }));
  } catch (e) { console.error("Photos error:", e); }

  return jsonResponse({
    ok: true,
    data: {
      news,
      sponsors,
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

async function getMatches(env) {
  const matches = [
    { id: 1, league: "2026春季联赛", group: "U12", team1: "烈焰", team2: "星光", score1: 3, score2: 1, status: "finished", time: "今天 14:30" },
    { id: 2, league: "2026春季联赛", group: "U15", team1: "冠军", team2: "雷霆", score1: 2, score2: 2, status: "finished", time: "昨天 16:00" },
    { id: 3, league: "2026春季联赛", group: "U12", team1: "烈焰", team2: "星光", status: "upcoming", time: "3月7日 14:30" }
  ];
  return jsonResponse({ ok: true, data: matches });
}

async function getStandings(env) {
  const standings = [
    { rank: 1, team: "烈焰", wins: 7, draws: 1, losses: 0, goals: 22, points: 22 },
    { rank: 2, team: "冠军", wins: 6, draws: 2, losses: 0, goals: 20, points: 20 },
    { rank: 3, team: "星光", wins: 5, draws: 2, losses: 1, goals: 17, points: 17 },
    { rank: 4, team: "雷霆", wins: 4, draws: 1, losses: 3, goals: 13, points: 13 }
  ];
  return jsonResponse({ ok: true, data: standings });
}

async function getTeams(env) {
  const teams = [
    { id: 1, name: "烈焰", tag: "U12 竞技组", wins: 7, points: 22, color: "fire" },
    { id: 2, name: "冠军", tag: "U15 竞技组", wins: 6, points: 20, color: "gold" },
    { id: 3, name: "星光", tag: "U12 竞技组", wins: 5, points: 17, color: "blue" },
    { id: 4, name: "雷霆", tag: "U15 训练组", wins: 4, points: 13, color: "purple" }
  ];
  return jsonResponse({ ok: true, data: teams });
}

async function getPlayers(env) {
  const players = [
    { id: 1, name: "小狮子", team: "烈焰", title: "得分王", goals: 28, assists: 12 },
    { id: 2, name: "闪电侠", team: "冠军", title: "MVP", goals: 25, assists: 15 },
    { id: 3, name: "铁壁", team: "铁壁", title: "最佳守门", goals: 0, saves: 95 }
  ];
  return jsonResponse({ ok: true, data: players });
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
