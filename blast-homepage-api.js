// blast-homepage-api - 首页数据聚合API
// 绑定：D1(blastjunior-content-db, blast-campaigns-db, blast-photo-db) + KV(blast-cache) + R2(blastjunior-media)

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
      
      // 比赛（空，按白皮书V1.1方案A）
      if (path === "/matches") {
        return withCors(await getMatches(env));
      }
      
      // 积分榜
      if (path === "/standings" || path === "/standings-v2") {
        return withCors(await getStandingsV2(env));
      }
      
      // 画廊
      if (path === "/gallery") {
        return withCors(await getGallery(env));
      }
      
      // 赛季
      if (path === "/seasons") {
        return withCors(await getSeasons(env));
      }
      
      // 积分项目
      if (path === "/score-components") {
        return withCors(await getScoreComponents(env));
      }
      
      // 内部联赛
      if (path === "/internal-rounds") {
        return withCors(await getInternalRounds(env));
      }
      
      // 荣誉
      if (path === "/honors") {
        return withCors(await getHonors(env));
      }
      
      // 组别
      if (path === "/divisions") {
        return withCors(await getDivisions(env));
      }
      
      // 参赛队伍
      if (path === "/registrations") {
        return withCors(await getRegistrations(env));
      }
      
      // 赛事
      if (path === "/events") {
        return withCors(await getEvents(env));
      }
      
      // 战队详情
      if (path.startsWith("/team/")) {
        const teamId = path.replace("/team/", "");
        return withCors(await getTeamDetail(env, teamId));
      }
      
      // 阵容
      if (path.startsWith("/rosters/")) {
        const teamId = path.replace("/rosters/", "");
        return withCors(await getRosters(env, teamId));
      }
      
      // 清除缓存（调试用）
      if (path === "/clear-cache") {
        await env.CACHE.delete("homepage");
        await env.CACHE.delete("teams");
        await env.CACHE.delete("players");
        await env.CACHE.delete("matches");
        return jsonResponse({ ok: true, message: "Cache cleared" });
      }
      
      return jsonResponse({ ok: false, error: "Not found" }, 404);
      
    } catch (e) {
      return jsonResponse({ ok: false, error: e.message }, 500);
    }
  }
};

// ===== 辅助函数 =====

function corsHeaders() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
  };
}

function withCors(response) {
  response.headers.set("Access-Control-Allow-Origin", "*");
  return response;
}

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json", "Access-Control-Allow-Origin": "*" }
  });
}

// ===== 数据函数 =====

async function getHomeData(env) {
  // 尝试从缓存读取
  let cachedData = null;
  try {
    const cached = await env.CACHE.get("homepage");
    if (cached) cachedData = JSON.parse(cached);
  } catch (e) {}
  
  if (cachedData) return jsonResponse({ ok: true, data: cachedData });

  let news = [], sponsors = [];
  try { const r = await env.DB.prepare("SELECT * FROM news WHERE status = 'published' ORDER BY date DESC LIMIT 5").all(); news = r.results || []; } catch (e) {}
  try { const r = await env.DB.prepare("SELECT * FROM sponsors WHERE status = 'active' ORDER BY sort_order LIMIT 10").all(); sponsors = r.results || []; } catch (e) {}

  // 获取当前赛季
  let currentSeason = null;
  let topTeams = [];
  try { 
    const s = await env.CAMPAIGNS.prepare("SELECT * FROM seasons ORDER BY CASE status WHEN 'ongoing' THEN 0 WHEN 'upcoming' THEN 1 ELSE 2 END LIMIT 1").first();
    currentSeason = s;
  } catch (e) {}
  
  // 获取TOP3战队
  try {
    const t = await env.CAMPAIGNS.prepare(`
      SELECT r.team_id, t.canonical_name as name, SUM(tcp.points) as points
      FROM team_component_points tcp
      JOIN registrations r ON tcp.registration_id = r.registration_id
      JOIN teams t ON r.team_id = t.team_id
      GROUP BY r.team_id
      ORDER BY points DESC
      LIMIT 3
    `).all();
    topTeams = (t.results || []).map((x, i) => ({ rank: i + 1, ...x }));
  } catch (e) {}

  // 获取内部联赛TOP选手
  let topPlayers = [];
  try {
    const p = await env.CAMPAIGNS.prepare(`
      SELECT player_name, SUM(total_points) as total_points
      FROM internal_league_results
      GROUP BY player_name
      ORDER BY total_points DESC
      LIMIT 3
    `).all();
    topPlayers = p.results || [];
  } catch (e) {}

  const data = { 
    news, 
    sponsors, 
    currentSeason,
    topTeams,
    topPlayers,
    stats: { 
      totalTeams: 108, 
      totalPlayers: 49,
      totalSeasons: 4
    } 
  };
  
  try { await env.CACHE.put("homepage", JSON.stringify(data), { expirationTtl: 300 }); } catch (e) {}
  return jsonResponse({ ok: true, data });
}

async function getNews(env) {
  try { const r = await env.DB.prepare("SELECT * FROM news WHERE status = 'published' ORDER BY date DESC").all(); return jsonResponse({ ok: true, data: r.results || [] }); }
  catch (e) { return jsonResponse({ ok: false, error: e.message }, 500); }
}

async function getSponsors(env) {
  try { const r = await env.DB.prepare("SELECT * FROM sponsors WHERE status = 'active' ORDER BY sort_order").all(); return jsonResponse({ ok: true, data: r.results || [] }); }
  catch (e) { return jsonResponse({ ok: false, error: e.message }, 500); }
}

async function getTeams(env) {
  try { const cached = await env.CACHE.get("teams"); if (cached) { const d = JSON.parse(cached); if (d?.length > 0) return jsonResponse({ ok: true, data: d }); } }
  catch (e) {}
  try { 
    // 获取战队基本信息
    const teams = await env.CAMPAIGNS.prepare("SELECT team_id as id, canonical_name as name, club_id, team_type, team_code FROM teams ORDER BY canonical_name LIMIT 50").all();
    const data = (teams.results || []).map(t => {
      return { 
        id: t.id, 
        name: t.name, 
        club_id: t.club_id,
        team_type: t.team_type,
        team_code: t.team_code
      };
    });
    if (data.length > 0) await env.CACHE.put("teams", JSON.stringify(data), { expirationTtl: 300 }); 
    return jsonResponse({ ok: true, data }); 
  }
  catch (e) { return jsonResponse({ ok: false, error: e.message }, 500); }
}

// 获取战队详情（包含阵容、积分、荣誉）
async function getTeamDetail(env, teamId) {
  try {
    // 战队基本信息
    const team = await env.CAMPAIGNS.prepare("SELECT * FROM teams WHERE team_id = ?").bind(teamId).first();
    if (!team) return jsonResponse({ ok: false, error: "Team not found" }, 404);
    
    // 当前赛季阵容
    let roster = [];
    try {
      const r = await env.CAMPAIGNS.prepare(`
        SELECT p.player_id, p.nickname, p.real_name, p.gender, r.season_id 
        FROM rosters r 
        JOIN players p ON r.player_id = p.player_id 
        WHERE r.team_id = ?
        ORDER BY r.season_id DESC
      `).bind(teamId).all();
      roster = r.results || [];
    } catch(e) {}
    
    // 积分
    let points = [];
    try {
      const p = await env.CAMPAIGNS.prepare(`
        SELECT sc.name, tcp.points, r.season_id 
        FROM team_component_points tcp 
        JOIN score_components sc ON tcp.component_id = sc.component_id
        JOIN registrations r ON tcp.registration_id = r.registration_id
        WHERE r.team_id = ?
        ORDER BY tcp.points DESC
      `).bind(teamId).all();
      points = p.results || [];
    } catch(e) {}
    
    // 荣誉
    let honors = [];
    try {
      const h = await env.CAMPAIGNS.prepare(`
        SELECT * FROM tournament_outcomes 
        WHERE team_id = ?
        ORDER BY final_rank
      `).bind(teamId).all();
      honors = h.results || [];
    } catch(e) {}
    
    // 别名
    let aliases = [];
    try {
      const a = await env.CAMPAIGNS.prepare("SELECT alias_name, note FROM team_aliases WHERE team_id = ?").bind(teamId).all();
      aliases = a.results || [];
    } catch(e) {}
    
    return jsonResponse({ 
      ok: true, 
      data: {
        id: team.team_id,
        name: team.canonical_name,
        club_id: team.club_id,
        team_type: team.team_type,
        first_season: team.first_season_season_id,
        note: team.note,
        roster: roster,
        points: points,
        honors: honors,
        aliases: aliases
      }
    });
  } catch (e) {
    return jsonResponse({ ok: false, error: e.message }, 500);
  }
}

async function getPlayers(env) {
  try { const cached = await env.CACHE.get("players"); if (cached) { const d = JSON.parse(cached); if (d?.length > 0) return jsonResponse({ ok: true, data: d }); } }
  catch (e) {}
  try { 
    // 获取选手信息和当前所属战队
    const r = await env.CAMPAIGNS.prepare(`
      SELECT p.player_id as id, p.nickname as name, p.display_name, p.real_name, p.birth_year, p.gender, p.is_active, p.club_name,
             r.team_id, r.season_id, t.canonical_name as team_name
      FROM players p
      LEFT JOIN (
        SELECT r1.team_id, r1.season_id, r1.player_id,
               ROW_NUMBER() OVER (PARTITION BY r1.player_id ORDER BY r1.season_id DESC) as rn
        FROM rosters r1
      ) r ON p.player_id = r.player_id AND r.rn = 1
      LEFT JOIN teams t ON r.team_id = t.team_id
      ORDER BY p.nickname LIMIT 50
    `).all(); 
    
    // 获取内部联赛排名
    const ranks = await env.CAMPAIGNS.prepare(`
      SELECT player_name, SUM(total_points) as total_points, SUM(points) as points
      FROM internal_league_results 
      GROUP BY player_name
    `).all();
    
    const rankMap = {};
    (ranks.results || []).forEach(x => { rankMap[x.player_name] = x; });
    
    const data = (r.results || []).map(p => ({
      id: p.id,
      name: p.name,
      display_name: p.display_name,
      real_name: p.real_name,
      birth_year: p.birth_year,
      gender: p.gender,
      is_active: p.is_active,
      club_name: p.club_name,
      current_team: p.team_id ? { id: p.team_id, name: p.team_name, season: p.season_id } : null,
      internal_rank: rankMap[p.name] || null
    }));
    
    if (data.length > 0) await env.CACHE.put("players", JSON.stringify(data), { expirationTtl: 300 }); 
    return jsonResponse({ ok: true, data }); 
  }
  catch (e) { return jsonResponse({ ok: false, error: e.message }, 500); }
}

// Matches API - 返回赛季和参赛队伍（无具体比赛结果）
async function getMatches(env) {
  try {
    // 获取所有赛季（按状态排序：进行中 > 即将开始 > 已结束）
    const seasons = await env.CAMPAIGNS.prepare(`
      SELECT season_id, name, year, start_date, end_date, status 
      FROM seasons 
      ORDER BY 
        CASE status WHEN 'ongoing' THEN 0 WHEN 'upcoming' THEN 1 ELSE 2 END,
        start_date DESC
    `).all();
    
    // 获取所有组别
    const divisions = await env.CAMPAIGNS.prepare("SELECT * FROM divisions ORDER BY sort_order").all();
    
    // 获取参赛队伍（按赛季）
    const registrations = await env.CAMPAIGNS.prepare(`
      SELECT r.registration_id, r.season_id, r.team_id, r.division, r.status,
             t.canonical_name as team_name, d.name as division_name
      FROM registrations r
      JOIN teams t ON r.team_id = t.team_id
      LEFT JOIN divisions d ON r.season_id = d.season_id AND r.division = d.division_key
      ORDER BY r.season_id, r.status DESC
    `).all();
    
    // 按赛季分组
    const seasonMap = {};
    (seasons.results || []).forEach(s => {
      seasonMap[s.season_id] = {
        ...s,
        divisions: [],
        teams: []
      };
    });
    
    // 添加组别
    (divisions.results || []).forEach(d => {
      if (seasonMap[d.season_id]) {
        seasonMap[d.season_id].divisions.push(d);
      }
    });
    
    // 添加参赛队伍
    (registrations.results || []).forEach(r => {
      if (seasonMap[r.season_id]) {
        seasonMap[r.season_id].teams.push(r);
      }
    });
    
    return jsonResponse({ 
      ok: true, 
      data: Object.values(seasonMap)
    });
  } catch (e) { 
    return jsonResponse({ ok: false, error: e.message }, 500); 
  }
}

async function getStandingsV2(env) {
  try { const r = await env.CAMPAIGNS.prepare(`SELECT r.team_id, t.canonical_name as team, SUM(tcp.points) as points, COUNT(tcp.id) as rounds FROM team_component_points tcp JOIN registrations r ON tcp.registration_id = r.registration_id JOIN teams t ON r.team_id = t.team_id GROUP BY r.team_id ORDER BY points DESC LIMIT 50`).all(); const data = (r.results || []).map((s, i) => ({ rank: i + 1, team_id: s.team_id, team: s.team, points: s.points || 0, rounds: s.rounds || 0 })); return jsonResponse({ ok: true, data }); }
  catch (e) { return jsonResponse({ ok: false, error: e.message }, 500); }
}

async function getGallery(env) {
  try { const r = await env.PHOTOS.prepare("SELECT photo_id as id, photo_key as key, ext, created_at FROM photos WHERE status = 'approved' ORDER BY photo_id ASC LIMIT 50").all(); 
    if (r.results?.length) {
      const data = r.results.map(p => {
        const title = p.key?.replace(/\.[^.]+$/, "");
        // 从文件名提取标签
        let tags = [];
        const key = p.key?.toLowerCase() || "";
        if (key.includes("hado")) tags.push("HADO");
        if (key.includes("training") || key.includes("训练")) tags.push("训练");
        if (key.includes("match") || key.includes("比赛")) tags.push("比赛");
        if (key.includes("team") || key.includes("队")) tags.push("团队");
        if (key.includes("player") || key.includes("选手")) tags.push("选手");
        if (key.includes("event") || key.includes("活动")) tags.push("活动");
        if (tags.length === 0) tags.push("其他");
        return { 
          id: p.id, 
          title: title, 
          cover: `https://blastjunior-media.kanjiaming2022.workers.dev/web/${p.key}`, 
          date: p.created_at,
          tags: tags
        }; 
      });
      return jsonResponse({ ok: true, data });
    }
  } catch (e) { console.error(e); }
  return jsonResponse({ ok: true, data: [] });
}

async function getSeasons(env) { try { const r = await env.CAMPAIGNS.prepare("SELECT season_id as id, name, year, start_date, end_date, status FROM seasons ORDER BY start_date DESC").all(); return jsonResponse({ ok: true, data: r.results || [] }); } catch (e) { return jsonResponse({ ok: false, error: e.message }, 500); } }

async function getScoreComponents(env) { try { const r = await env.CAMPAIGNS.prepare("SELECT component_id as id, name, component_type FROM score_components ORDER BY component_id").all(); return jsonResponse({ ok: true, data: r.results || [] }); } catch (e) { return jsonResponse({ ok: false, error: e.message }, 500); } }

async function getInternalRounds(env) { try { const r = await env.CAMPAIGNS.prepare("SELECT DISTINCT season_id, round_date FROM internal_league_results ORDER BY round_date DESC LIMIT 20").all(); const rounds = r.results || []; for (const round of rounds) { const p = await env.CAMPAIGNS.prepare("SELECT player_name, points, total_points, rank FROM internal_league_results WHERE season_id = ? AND round_date = ? ORDER BY rank LIMIT 10").bind(round.season_id, round.round_date).all(); round.topPlayers = (p.results || []).map(x => ({ name: x.player_name, points: x.points, total: x.total_points, rank: x.rank })); } return jsonResponse({ ok: true, data: rounds }); } catch (e) { return jsonResponse({ ok: false, error: e.message }, 500); } }

async function getHonors(env) { try { const r = await env.CAMPAIGNS.prepare("SELECT outcome_id as id, event_id, season_id, team_id, stage_reached, final_rank, country_name FROM tournament_outcomes WHERE final_rank IS NOT NULL AND final_rank <= 8 ORDER BY final_rank LIMIT 50").all(); return jsonResponse({ ok: true, data: r.results || [] }); } catch (e) { return jsonResponse({ ok: false, error: e.message }, 500); } }

async function getDivisions(env) { try { const r = await env.CAMPAIGNS.prepare("SELECT division_id as id, season_id, division_key, name, sort_order FROM divisions ORDER BY sort_order LIMIT 50").all(); return jsonResponse({ ok: true, data: r.results || [] }); } catch (e) { return jsonResponse({ ok: false, error: e.message }, 500); } }

async function getRegistrations(env) { try { const r = await env.CAMPAIGNS.prepare("SELECT r.registration_id as id, r.season_id, r.team_id, r.club_id, r.division, r.status, t.canonical_name as team_name FROM registrations r JOIN teams t ON r.team_id = t.team_id ORDER BY r.season_id DESC, r.division LIMIT 100").all(); return jsonResponse({ ok: true, data: r.results || [] }); } catch (e) { return jsonResponse({ ok: false, error: e.message }, 500); } }

async function getEvents(env) { try { const r = await env.CAMPAIGNS.prepare("SELECT event_id, name_zh, name_en, official_url, description, level, frequency FROM events ORDER BY level, name_zh LIMIT 50").all(); return jsonResponse({ ok: true, data: r.results || [] }); } catch (e) { return jsonResponse({ ok: false, error: e.message }, 500); } }

async function getTeamHonors(env, teamId) { try { const r = await env.CAMPAIGNS.prepare("SELECT outcome_id as id, event_id, season_id, stage_reached, final_rank, country_name FROM tournament_outcomes WHERE team_id = ? AND final_rank IS NOT NULL ORDER BY final_rank LIMIT 20").bind(teamId).all(); return jsonResponse({ ok: true, data: r.results || [] }); } catch (e) { return jsonResponse({ ok: false, error: e.message }, 500); } }

async function getRosters(env, teamId) { try { const r = await env.CAMPAIGNS.prepare("SELECT r.roster_id as id, r.season_id, r.team_id, r.player_id, p.nickname as player_name, p.display_name FROM rosters r LEFT JOIN players p ON r.player_id = p.player_id WHERE r.team_id = ? ORDER BY r.season_id DESC LIMIT 50").bind(teamId).all(); return jsonResponse({ ok: true, data: r.results || [] }); } catch (e) { return jsonResponse({ ok: false, error: e.message }, 500); } }
