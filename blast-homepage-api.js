// blast-homepage-api - 首页数据聚合API
// 数据来源：D1(新闻/赞助商) + R2(其他数据)

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
      
      // 新闻 (D1)
      if (path === "/news") {
        return withCors(await getNews(env));
      }
      
      // 赞助商 (D1)
      if (path === "/sponsors") {
        return withCors(await getSponsors(env));
      }
      
      // 战队 (R2)
      if (path === "/teams") {
        return withCors(await getTeams(env));
      }
      
      // 选手 (R2)
      if (path === "/players") {
        return withCors(await getPlayers(env));
      }
      
      // 比赛 (R2)
      if (path === "/matches") {
        return withCors(await getMatches(env));
      }
      
      // 积分榜 (R2)
      if (path === "/standings") {
        return withCors(await getStandings(env));
      }
      
      // 画廊 (R2)
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

  // 从R2获取比赛数据
  let matches = [];
  try {
    const obj = await env.BUCKET.get("data/matches.json");
    if (obj) {
      const data = JSON.parse(await obj.text());
      matches = data.filter(m => m.status === 'finished').slice(0, 3);
    }
  } catch (e) { console.error("Matches error:", e); }

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
    const obj = await env.BUCKET.get("data/teams.json");
    if (obj) {
      const data = JSON.parse(await obj.text());
      return jsonResponse({ ok: true, data });
    }
  } catch (e) { console.error(e); }
  
  return jsonResponse({ ok: true, data: [] });
}

async function getPlayers(env) {
  try {
    const obj = await env.BUCKET.get("data/players.json");
    if (obj) {
      const data = JSON.parse(await obj.text());
      return jsonResponse({ ok: true, data });
    }
  } catch (e) { console.error(e); }
  
  return jsonResponse({ ok: true, data: [] });
}

async function getMatches(env) {
  try {
    const obj = await env.BUCKET.get("data/matches.json");
    if (obj) {
      const data = JSON.parse(await obj.text());
      return jsonResponse({ ok: true, data });
    }
  } catch (e) { console.error(e); }
  
  return jsonResponse({ ok: true, data: [] });
}

async function getStandings(env) {
  try {
    const obj = await env.BUCKET.get("data/teams.json");
    if (obj) {
      const data = JSON.parse(await obj.text());
      const standings = data.map((t, i) => ({
        rank: i + 1,
        team: t.name,
        wins: t.wins || 0,
        draws: t.draws || 0,
        losses: t.losses || 0,
        goals: ((t.wins || 0) * 2) - (t.losses || 0),
        points: t.points || 0
      })).sort((a, b) => b.points - a.points);
      
      return jsonResponse({ ok: true, data: standings });
    }
  } catch (e) { console.error(e); }
  
  return jsonResponse({ ok: true, data: [] });
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
