// blast-homepage-api - 首页数据聚合API
// 绑定：D1(blastjunior-content-db, blast-campaigns-db, blast-photo-db) + KV(blast-cache) + R2(blastjunior-media)

const STATIC_API = 'https://blast-static-api.kanjiaming2022.workers.dev';

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname;
    const origin = request.headers.get("Origin") || "";

    // 验证 origin - 只允许单域名 (BLXST-rules)
    const allowedOrigins = ["https://blastjunior.com", "https://www.blastjunior.com", "https://blastjunior-website.pages.dev"];
    const isAllowedOrigin = allowedOrigins.includes(origin);

    // 静态文件请求 - 返回 404 让 Pages 处理
    if (path.endsWith(".html") || path.endsWith(".css") || path.endsWith(".js") || path.endsWith(".png") || path.endsWith(".jpg") || path.endsWith(".ico")) {
      return new Response("Not Found", { status: 404 });
    }

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders(origin) });
    }

    try {
      // 首页聚合
      if (path === "/" || path === "/home") {
        return withCors(await getHomeData(env, origin), origin);
      }
      
      // 新闻
      if (path === "/news") {
        return withCors(await getNews(env, origin), origin);
      }
      
      // 赞助商
      if (path === "/sponsors") {
        return withCors(await getSponsors(env, origin), origin);
      }
      
      // 战队
      if (path === "/teams") {
        return withCors(await getTeams(env, origin), origin);
      }
      
      // 选手
      if (path === "/players") {
        return withCors(await getPlayers(env, origin), origin);
      }
      
      // 比赛列表（按白皮书V1.1方案A - 返回赛季和参赛队伍）
      if (path === "/matches") {
        return withCors(await getMatches(env, origin), origin);
      }
      
      // 比赛详情（单个赛季）
      if (path.startsWith("/matches/")) {
        const seasonId = path.replace("/matches/", "");
        return withCors(await getMatchDetail(env, seasonId, origin), origin);
      }
      
      // 积分榜
      if (path === "/standings" || path === "/standings-v2") {
        return withCors(await getStandingsV2(env, origin), origin);
      }
      
      // 画廊
      if (path === "/gallery") {
        return withCors(await getGallery(env, origin), origin);
      }
      
      // 赛季
      if (path === "/seasons") {
        return withCors(await getSeasons(env, origin), origin);
      }
      
      // 积分项目
      if (path === "/score-components") {
        return withCors(await getScoreComponents(env, origin), origin);
      }
      
      // 内部联赛
      if (path === "/internal-rounds") {
        return withCors(await getInternalRounds(env, origin), origin);
      }
      
      // 荣誉
      if (path === "/honors") {
        return withCors(await getHonors(env, origin), origin);
      }
      
      // 组别
      if (path === "/divisions") {
        return withCors(await getDivisions(env, origin), origin);
      }
      
      // 参赛队伍
      if (path === "/registrations") {
        return withCors(await getRegistrations(env, origin), origin);
      }
      
      // 赛事
      if (path === "/events") {
        return withCors(await getEvents(env, origin), origin);
      }
      
      // 战队详情
      if (path.startsWith("/team/")) {
        const teamId = path.replace("/team/", "");
        return withCors(await getTeamDetail(env, teamId, origin), origin);
      }
      
      // 战队详情 (备用路径)
      if (path.startsWith("/teams/")) {
        const teamId = path.replace("/teams/", "");
        return withCors(await getTeamDetail(env, teamId, origin), origin);
      }
      
      // 选手详情
      if (path.startsWith("/player/")) {
        const playerId = path.replace("/player/", "");
        return withCors(await getPlayerDetail(env, playerId, origin), origin);
      }
      
      // 选手详情 (备用路径)
      if (path.startsWith("/players/")) {
        const playerId = path.replace("/players/", "");
        return withCors(await getPlayerDetail(env, playerId, origin), origin);
      }
      
      // 阵容
      if (path.startsWith("/rosters/")) {
        const teamId = path.replace("/rosters/", "");
        return withCors(await getRosters(env, teamId, origin), origin);
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

function corsHeaders(origin) {
  // CORS 允许多个域名
  const allowedOrigins = ["https://blastjunior.com", "https://www.blastjunior.com", "https://blastjunior-website.pages.dev"];
  const normalizedOrigin = origin.replace(/\/$/, ""); // 去掉末尾斜杠
  const allowOrigin = allowedOrigins.includes(normalizedOrigin) ? normalizedOrigin : "";
  
  return {
    "Access-Control-Allow-Origin": allowOrigin,
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
  };
}

function withCors(response, origin) {
  // CORS 允许多个域名
  const allowedOrigins = ["https://blastjunior.com", "https://www.blastjunior.com", "https://blastjunior-website.pages.dev"];
  const normalizedOrigin = origin.replace(/\/$/, ""); // 去掉末尾斜杠
  const allowOrigin = allowedOrigins.includes(normalizedOrigin) ? normalizedOrigin : "";
  response.headers.set("Access-Control-Allow-Origin", allowOrigin);
  return response;
}

function jsonResponse(data, status = 200, origin = "") {
  // CORS 允许多个域名
  const allowedOrigins = ["https://blastjunior.com", "https://www.blastjunior.com", "https://blastjunior-website.pages.dev"];
  const normalizedOrigin = origin.replace(/\/$/, ""); // 去掉末尾斜杠
  const allowOrigin = allowedOrigins.includes(normalizedOrigin) ? normalizedOrigin : "";
  return new Response(JSON.stringify(data), {
    status,
    headers: { 
      "Content-Type": "application/json", 
      "Access-Control-Allow-Origin": allowOrigin 
    }
  });
}

// ===== 数据函数 =====

async function getHomeData(env, origin = "") {
  // 尝试从缓存读取
  let cachedData = null;
  try {
    const cached = await env.CACHE.get("homepage");
    if (cached) cachedData = JSON.parse(cached);
  } catch (e) {}
  
  if (cachedData) return jsonResponse({ ok: true, data: cachedData }, 200, origin);

  let news = [], sponsors = [];
  try { const r = await env.NEWS.prepare("SELECT * FROM news_articles WHERE status = 'published' ORDER BY published_at DESC LIMIT 5").all(); news = r.results || []; } catch (e) {}
  try { const r = await env.CAMPAIGNS.prepare("SELECT * FROM sponsors WHERE status = 'active' ORDER BY sort_order LIMIT 10").all(); sponsors = r.results || []; } catch (e) {}

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

  // 获取精选照片（首页精彩瞬间）
  let featuredPhotos = [];
  try {
    const photos = await env.PHOTOS.prepare(`
      SELECT photo_id, photo_key, ext, created_at
      FROM photos 
      WHERE status = 'approved' 
      ORDER BY created_at DESC 
      LIMIT 6
    `).all();
    
    if (photos.results && photos.results.length > 0) {
      featuredPhotos = photos.results.map(p => ({
        id: p.photo_id,
        url: `https://blastjunior-media.kanjiaming2022.workers.dev/media/web/${p.photo_key}`,
        title: p.photo_key?.replace(/\.[^.]+$/, "") || "精彩瞬间"
      }));
    }
  } catch (e) {
    console.error("获取精选照片失败:", e);
  }

  const data = { 
    news, 
    sponsors, 
    currentSeason,
    topTeams,
    topPlayers,
    featuredPhotos,
    stats: { 
      totalTeams: 108, 
      totalPlayers: 49,
      totalSeasons: 4
    } 
  };
  
  try { await env.CACHE.put("homepage", JSON.stringify(data), { expirationTtl: 300 }); } catch (e) {}
  return jsonResponse({ ok: true, data }, 200, origin);
}

async function getNews(env, origin = "") {
  try { const r = await env.NEWS.prepare("SELECT * FROM news_articles WHERE status = 'published' ORDER BY published_at DESC").all(); return jsonResponse({ ok: true, data: r.results || [] }, 200, origin); }
  catch (e) { return jsonResponse({ ok: false, error: e.message }, 500, origin); }
}

async function getSponsors(env, origin = "") {
  try { const r = await env.CAMPAIGNS.prepare("SELECT * FROM sponsors WHERE status = 'active' ORDER BY sort_order").all(); return jsonResponse({ ok: true, data: r.results || [] }, 200, origin); }
  catch (e) { return jsonResponse({ ok: false, error: e.message }, 500, origin); }
}

async function getTeams(env, origin = "") {
  try { const cached = await env.CACHE.get("teams"); if (cached) { const d = JSON.parse(cached); if (d?.length > 0) return jsonResponse({ ok: true, data: d }, 200, origin); } }
  catch (e) {}
  try { 
    // 获取战队基本信息
    const teams = await env.CAMPAIGNS.prepare("SELECT team_id as id, canonical_name as name, club_id, team_type, team_code FROM teams ORDER BY canonical_name LIMIT 200").all();
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
    return jsonResponse({ ok: true, data }, 200, origin); 
  }
  catch (e) { return jsonResponse({ ok: false, error: e.message }, 500, origin); }
}

// 获取战队详情（包含阵容、积分、荣誉）
async function getTeamDetail(env, teamId, origin = "") {
  try {
    // 战队基本信息
    const team = await env.CAMPAIGNS.prepare("SELECT * FROM teams WHERE team_id = ?").bind(teamId).first();
    if (!team) return jsonResponse({ ok: false, error: "Team not found" }, 404, origin);
    
    // 获取当前赛季ID
    const currentSeason = await env.CAMPAIGNS.prepare(`
      SELECT season_id FROM seasons WHERE status = 'ongoing' ORDER BY start_date DESC LIMIT 1
    `).first();
    const currentSeasonId = currentSeason?.season_id || 'hpl_s2_2025';
    
    // 当前赛季阵容（仅显示当前赛季成员）
    let currentRoster = [];
    try {
      const r = await env.CAMPAIGNS.prepare(`
        SELECT p.player_id, p.nickname, p.real_name, p.gender, r.season_id, r.role
        FROM rosters r 
        JOIN players p ON r.player_id = p.player_id 
        WHERE r.team_id = ? AND r.season_id = ?
      `).bind(teamId, currentSeasonId).all();
      currentRoster = r.results || [];
    } catch(e) {}
    
    // 历史阵容（所有赛季，按时间倒序）
    let rosterHistory = [];
    try {
      const rh = await env.CAMPAIGNS.prepare(`
        SELECT p.player_id, p.nickname, p.real_name, p.gender, r.season_id, r.role,
               s.status as season_status, s.season_type
        FROM rosters r 
        JOIN players p ON r.player_id = p.player_id
        JOIN seasons s ON r.season_id = s.season_id
        WHERE r.team_id = ?
        ORDER BY s.start_date DESC
      `).bind(teamId).all();
      rosterHistory = rh.results || [];
    } catch(e) {}
    
    // 积分（按赛季区分联赛vs杯赛）
    let points = [];
    try {
      const pt = await env.CAMPAIGNS.prepare(`
        SELECT sc.name, tcp.points, r.season_id, s.season_type, s.name as season_name
        FROM team_component_points tcp 
        JOIN score_components sc ON tcp.component_id = sc.component_id
        JOIN registrations r ON tcp.registration_id = r.registration_id
        JOIN seasons s ON r.season_id = s.season_id
        WHERE r.team_id = ?
        ORDER BY s.start_date DESC, tcp.points DESC
      `).bind(teamId).all();
      points = (pt.results || []).map(x => ({
        ...x,
        isLeague: x.season_type !== 'cup',
        isCup: x.season_type === 'cup'
      }));
    } catch(e) {}
    
    // 荣誉/参赛记录（区分联赛vs杯赛，显示级别）
    let honors = [];
    try {
      const h = await env.CAMPAIGNS.prepare(`
        SELECT to.*, e.name_zh, e.level, e.frequency, s.season_type, s.name as season_name
        FROM tournament_outcomes to
        JOIN events e ON to.event_id = e.event_id
        JOIN seasons s ON to.season_id = s.season_id
        WHERE to.team_id = ?
        ORDER BY to.final_rank, s.start_date DESC
      `).bind(teamId).all();
      honors = (h.results || []).map(x => ({
        ...x,
        isLeague: x.season_type !== 'cup',
        isCup: x.season_type === 'cup',
        levelLabel: x.level === 'World' ? 'World' : x.level === 'National' ? 'National' : x.level === 'International' ? 'International' : x.level === 'Regional' ? 'Regional' : 'Other'
      }));
    } catch(e) {}
    
    // 首次亮相赛事
    let firstAppearance = null;
    try {
      const fa = await env.CAMPAIGNS.prepare(`
        SELECT to.season_id, s.name as season_name, e.name_zh as event_name, 
               e.level, to.stage_reached, to.final_rank, s.season_type
        FROM tournament_outcomes to
        JOIN seasons s ON to.season_id = s.season_id
        JOIN events e ON to.event_id = e.event_id
        WHERE to.team_id = ?
        ORDER BY s.start_date ASC
        LIMIT 1
      `).bind(teamId).first();
      if (fa) {
        firstAppearance = {
          ...fa,
          isLeague: fa.season_type !== 'cup',
          isCup: fa.season_type === 'cup'
        };
      }
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
        first_season: team.first_seen_season_id,
        note: team.note,
        currentSeasonId,
        currentRoster: currentRoster,
        rosterHistory: rosterHistory,
        points: points,
        honors: honors,
        firstAppearance: firstAppearance,
        aliases: aliases
      }
    }, 200, origin);
  } catch (e) {
    return jsonResponse({ ok: false, error: e.message }, 500, origin);
  }
}

async function getPlayers(env, origin = "") {
  try { const cached = await env.CACHE.get("players"); if (cached) { const d = JSON.parse(cached); if (d?.length > 0) return jsonResponse({ ok: true, data: d }, 200, origin); } }
  catch (e) {}
  
  try { 
    // 获取当前赛季信息
    const currentSeason = await env.CAMPAIGNS.prepare(`
      SELECT season_id, name FROM seasons 
      WHERE status = 'ongoing' ORDER BY start_date DESC LIMIT 1
    `).first();
    const currentSeasonId = currentSeason?.season_id || 'hpl_s2_2025';
    
    // 获取选手信息和当前所属战队（联赛）
    const r = await env.CAMPAIGNS.prepare(`
      SELECT p.player_id as id, p.nickname as name, p.display_name, p.real_name, p.birth_year, p.gender, p.is_active, p.club_name,
             r.team_id, r.season_id, t.canonical_name as team_name,
             s.season_type
      FROM players p
      LEFT JOIN (
        SELECT r1.team_id, r1.season_id, r1.player_id,
               ROW_NUMBER() OVER (PARTITION BY r1.player_id ORDER BY r1.season_id DESC) as rn
        FROM rosters r1
        JOIN seasons s1 ON r1.season_id = s1.season_id
      ) r ON p.player_id = r.player_id AND r.rn = 1
      LEFT JOIN teams t ON r.team_id = t.team_id
      LEFT JOIN seasons s ON r.season_id = s.season_id
      ORDER BY p.nickname LIMIT 50
    `).all(); 
    
    // 获取选手历史效力战队
    const playerHistory = await env.CAMPAIGNS.prepare(`
      SELECT p.player_id, p.nickname, r.team_id, r.season_id, t.canonical_name as team_name, s.season_type, s.status as season_status
      FROM rosters r
      JOIN players p ON r.player_id = p.player_id
      JOIN teams t ON r.team_id = t.team_id
      JOIN seasons s ON r.season_id = s.season_id
      ORDER BY s.start_date DESC
    `).all();
    
    // 按选手分组历史战队
    const historyMap = {};
    (playerHistory.results || []).forEach(x => {
      if (!historyMap[x.player_id]) historyMap[x.player_id] = [];
      historyMap[x.player_id].push({
        team_id: x.team_id,
        team_name: x.team_name,
        season_id: x.season_id,
        isLeague: x.season_type !== 'cup',
        isCup: x.season_type === 'cup',
        isCurrent: x.season_status === 'ongoing'
      });
    });
    
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
      current_team: p.team_id ? { 
        id: p.team_id, 
        name: p.team_name, 
        season: p.season_id,
        isLeague: p.season_type !== 'cup'
      } : null,
      team_history: historyMap[p.id] || [],
      internal_rank: rankMap[p.name] || null
    }));
    
    if (data.length > 0) await env.CACHE.put("players", JSON.stringify(data), { expirationTtl: 300 }); 
    return jsonResponse({ ok: true, data, meta: { currentSeasonId } }, 200, origin); 
  }
  catch (e) { return jsonResponse({ ok: false, error: e.message }, 500, origin); }
}

// Matches API - 返回赛季和参赛队伍（无具体比赛结果）
async function getMatches(env, origin = "") {
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
    }, 200, origin);
  } catch (e) { 
    return jsonResponse({ ok: false, error: e.message }, 500, origin); 
  }
}

// 获取单个赛季详情（比赛/赛季详情）
async function getMatchDetail(env, seasonId, origin = "") {
  try {
    // 获取指定赛季信息
    const season = await env.CAMPAIGNS.prepare(`
      SELECT season_id, name, year, start_date, end_date, status, season_type
      FROM seasons 
      WHERE season_id = ?
    `).bind(seasonId).first();
    
    if (!season) {
      return jsonResponse({ ok: false, error: "Season not found" }, 404, origin);
    }
    
    // 获取该赛季的组别
    const divisions = await env.CAMPAIGNS.prepare(`
      SELECT * FROM divisions WHERE season_id = ? ORDER BY sort_order
    `).bind(seasonId).all();
    
    // 获取该赛季的参赛队伍
    const registrations = await env.CAMPAIGNS.prepare(`
      SELECT r.registration_id, r.season_id, r.team_id, r.division, r.status,
             t.canonical_name as team_name, d.name as division_name
      FROM registrations r
      JOIN teams t ON r.team_id = t.team_id
      LEFT JOIN divisions d ON r.season_id = d.season_id AND r.division = d.division_key
      WHERE r.season_id = ?
      ORDER BY r.status DESC, t.canonical_name
    `).bind(seasonId).all();
    
    // 获取该赛季的积分
    let points = [];
    try {
      const pt = await env.CAMPAIGNS.prepare(`
        SELECT r.team_id, t.canonical_name as team_name, 
               SUM(tcp.points) as total_points, 
               COUNT(DISTINCT tcp.component_id) as rounds_played
        FROM team_component_points tcp
        JOIN registrations r ON tcp.registration_id = r.registration_id
        JOIN teams t ON r.team_id = t.team_id
        WHERE r.season_id = ?
        GROUP BY r.team_id
        ORDER BY total_points DESC
      `).bind(seasonId).all();
      points = pt.results || [];
    } catch(e) {}
    
    return jsonResponse({ 
      ok: true, 
      data: {
        ...season,
        divisions: divisions.results || [],
        teams: registrations.results || [],
        standings: points
      }
    }, 200, origin);
  } catch (e) { 
    return jsonResponse({ ok: false, error: e.message }, 500, origin); 
  }
}

async function getStandingsV2(env, origin = "") {
  try {
    // 获取当前赛季信息
    const currentSeason = await env.CAMPAIGNS.prepare(`
      SELECT season_id, name, season_type FROM seasons 
      WHERE status = 'ongoing' ORDER BY start_date DESC LIMIT 1
    `).first();
    
    const seasonId = currentSeason?.season_id || 'hpl_s2_2025';
    const seasonName = currentSeason?.name || '第二届HPL超级联赛';
    const seasonType = currentSeason?.season_type || null;
    
    // 获取该赛季积分（区分联赛和杯赛）
    const r = await env.CAMPAIGNS.prepare(`
      SELECT r.team_id, t.canonical_name as team, 
             SUM(tcp.points) as points, 
             COUNT(DISTINCT tcp.component_id) as rounds,
             s.season_type
      FROM team_component_points tcp 
      JOIN registrations r ON tcp.registration_id = r.registration_id
      JOIN teams t ON r.team_id = t.team_id
      JOIN seasons s ON r.season_id = s.season_id
      WHERE r.season_id = ?
      GROUP BY r.team_id
      ORDER BY points DESC LIMIT 50
    `).bind(seasonId).all();
    
    const data = (r.results || []).map((s, i) => ({
      rank: i + 1,
      team_id: s.team_id,
      team: s.team,
      points: s.points || 0,
      rounds: s.rounds || 0,
      isLeague: s.season_type !== 'cup',
      isCup: s.season_type === 'cup'
    }));
    
    return jsonResponse({ 
      ok: true, 
      data, 
      meta: {
        seasonId,
        seasonName,
        seasonType,
        description: seasonType === 'cup' ? '杯赛单独计分' : '联赛总积分'
      }
    }, 200, origin);
  }
  catch (e) { return jsonResponse({ ok: false, error: e.message }, 500, origin); }
}

async function getGallery(env, origin = "") {
  const R2_BASE = "https://blastjunior-media.kanjiaming2022.workers.dev";
  
  try {
    // 直接从 R2 列出 thumb/ 目录的文件
    const bucket = env.BUCKET;
    let items = [];
    let cursor = undefined;
    
    do {
      const listed = await bucket.list({ prefix: "thumb/", cursor, limit: 1000 });
      items.push(...(listed.objects || []));
      cursor = listed.truncated ? listed.cursor : undefined;
    } while (cursor);
    
    if (items.length > 0) {
      const data = items
        .map(obj => {
          // key: "thumb/HADO (1).png" -> name: "HADO (1).png"
          const name = obj.key.replace(/^thumb\//, "");
          // 过滤无效文件名
          if (!name || !name.match(/HADO\s*\(\d+\)/i)) {
            return null;
          }
          const title = name.replace(/\.[^.]+$/, "");
          const key = name.toLowerCase();
          
          // 解析 id: "HADO (1).png" -> id = 1
          const idMatch = name.match(/HADO\s*\((\d+)\)/i);
          const id = idMatch ? parseInt(idMatch[1]) : 0;
          
          // 赛季检测
          let season = "S4";
          if (key.includes("s1") || key.includes("season1")) season = "S1";
          else if (key.includes("s2") || key.includes("season2")) season = "S2";
          else if (key.includes("s3") || key.includes("season3")) season = "S3";
          else if (key.includes("s4") || key.includes("season4")) season = "S4";
          
          // 类型标签
          let tags = ["其他"];
          let type = "other";
          if (key.includes("training") || key.includes("训练")) { tags = ["训练"]; type = "training"; }
          else if (key.includes("match") || key.includes("比赛")) { tags = ["比赛"]; type = "match"; }
          else if (key.includes("team") || key.includes("队")) { tags = ["团队"]; type = "team"; }
          else if (key.includes("player") || key.includes("选手")) { tags = ["选手"]; type = "team"; }
          else if (key.includes("event") || key.includes("活动")) { tags = ["活动"]; type = "event"; }
          
          // 日期从 R2 metadata 或使用上传日期
          const date = obj.uploaded ? obj.uploaded.toISOString().split('T')[0] : "2026-01-01";
          
          // 构建 web URL (注意需要 encodeURIComponent 处理空格)
          const webUrl = `${R2_BASE}/media/web/${encodeURIComponent(name)}`;
          
          return {
            id,
            title,
            cover: webUrl,
            date,
            tags,
            season,
            type,
            team_id: null,
            team_name: null
          };
        })
        .filter(item => item !== null);
      
      // 按 id 排序
      data.sort((a, b) => a.id - b.id);
      return jsonResponse({ ok: true, data }, 200, origin);
    }
  } catch (e) { 
    console.error("getGallery error:", e); 
  }
  return jsonResponse({ ok: true, data: [] }, 200, origin);
}

async function getSeasons(env, origin = "") { try { const r = await env.CAMPAIGNS.prepare("SELECT season_id as id, name, year, start_date, end_date, status FROM seasons ORDER BY start_date DESC").all(); return jsonResponse({ ok: true, data: r.results || [] }, 200, origin); } catch (e) { return jsonResponse({ ok: false, error: e.message }, 500, origin); } }

async function getScoreComponents(env, origin = "") { try { const r = await env.CAMPAIGNS.prepare("SELECT component_id as id, name, component_type FROM score_components ORDER BY component_id").all(); return jsonResponse({ ok: true, data: r.results || [] }, 200, origin); } catch (e) { return jsonResponse({ ok: false, error: e.message }, 500, origin); } }

async function getInternalRounds(env, origin = "") { try { const r = await env.CAMPAIGNS.prepare("SELECT DISTINCT season_id, round_date FROM internal_league_results ORDER BY round_date DESC LIMIT 20").all(); const rounds = r.results || []; for (const round of rounds) { const p = await env.CAMPAIGNS.prepare("SELECT player_name, points, total_points, rank FROM internal_league_results WHERE season_id = ? AND round_date = ? ORDER BY rank LIMIT 10").bind(round.season_id, round.round_date).all(); round.topPlayers = (p.results || []).map(x => ({ name: x.player_name, points: x.points, total: x.total_points, rank: x.rank })); } return jsonResponse({ ok: true, data: rounds }, 200, origin); } catch (e) { return jsonResponse({ ok: false, error: e.message }, 500, origin); } }

async function getHonors(env, origin = "") { try { const r = await env.CAMPAIGNS.prepare("SELECT outcome_id as id, event_id, season_id, team_id, stage_reached, final_rank, country_name FROM tournament_outcomes WHERE final_rank IS NOT NULL AND final_rank <= 8 ORDER BY final_rank LIMIT 50").all(); return jsonResponse({ ok: true, data: r.results || [] }, 200, origin); } catch (e) { return jsonResponse({ ok: false, error: e.message }, 500, origin); } }

async function getDivisions(env, origin = "") { try { const r = await env.CAMPAIGNS.prepare("SELECT division_id as id, season_id, division_key, name, sort_order FROM divisions ORDER BY sort_order LIMIT 50").all(); return jsonResponse({ ok: true, data: r.results || [] }, 200, origin); } catch (e) { return jsonResponse({ ok: false, error: e.message }, 500, origin); } }

async function getRegistrations(env, origin = "") { try { const r = await env.CAMPAIGNS.prepare("SELECT r.registration_id as id, r.season_id, r.team_id, r.club_id, r.division, r.status, t.canonical_name as team_name FROM registrations r JOIN teams t ON r.team_id = t.team_id ORDER BY r.season_id DESC, r.division LIMIT 100").all(); return jsonResponse({ ok: true, data: r.results || [] }, 200, origin); } catch (e) { return jsonResponse({ ok: false, error: e.message }, 500, origin); } }

async function getEvents(env, origin = "") { 
  try { 
    const r = await env.CAMPAIGNS.prepare(`
      SELECT e.event_id, e.name_zh, e.name_en, e.official_url, e.description, e.level, e.frequency,
             s.season_id, s.name as season_name, s.season_type, s.status as season_status
      FROM events e
      LEFT JOIN seasons s ON e.event_id = s.event_id
      ORDER BY e.level, e.name_zh, s.start_date DESC
      LIMIT 50
    `).all(); 
    
    // 按赛事分组
    const eventMap = {};
    (r.results || []).forEach(x => {
      if (!eventMap[x.event_id]) {
        eventMap[x.event_id] = {
          event_id: x.event_id,
          name_zh: x.name_zh,
          name_en: x.name_en,
          level: x.level,
          levelLabel: x.level === 'World' ? 'World' : x.level === 'National' ? 'National' : x.level === 'International' ? 'International' : x.level === 'Regional' ? 'Regional' : 'Other',
          frequency: x.frequency,
          description: x.description,
          seasons: []
        };
      }
      if (x.season_id) {
        eventMap[x.event_id].seasons.push({
          season_id: x.season_id,
          name: x.season_name,
          isLeague: x.season_type !== 'cup',
          isCup: x.season_type === 'cup',
          status: x.season_status
        });
      }
    });
    
    return jsonResponse({ ok: true, data: Object.values(eventMap) }, 200, origin); 
  } catch (e) { return jsonResponse({ ok: false, error: e.message }, 500, origin); } 
}

async function getTeamHonors(env, teamId, origin = "") { 
  try { 
    const r = await env.CAMPAIGNS.prepare(`
      SELECT to.outcome_id as id, to.event_id, to.season_id, to.stage_reached, to.final_rank, to.country_name,
             e.name_zh, e.level, s.season_type, s.name as season_name
      FROM tournament_outcomes to
      JOIN events e ON to.event_id = e.event_id
      JOIN seasons s ON to.season_id = s.season_id
      WHERE to.team_id = ? AND to.final_rank IS NOT NULL
      ORDER BY s.start_date DESC, to.final_rank
      LIMIT 20
    `).bind(teamId).all(); 
    const data = (r.results || []).map(x => ({
      ...x,
      isLeague: x.season_type !== 'cup',
      isCup: x.season_type === 'cup',
      levelLabel: x.level === 'World' ? 'World' : x.level === 'National' ? 'National' : x.level === 'International' ? 'International' : x.level === 'Regional' ? 'Regional' : 'Other'
    }));
    return jsonResponse({ ok: true, data }, 200, origin); 
  } catch (e) { return jsonResponse({ ok: false, error: e.message }, 500, origin); } 
}

async function getRosters(env, teamId, origin = "") { try { const r = await env.CAMPAIGNS.prepare("SELECT r.roster_id as id, r.season_id, r.team_id, r.player_id, p.nickname as player_name, p.display_name FROM rosters r LEFT JOIN players p ON r.player_id = p.player_id WHERE r.team_id = ? ORDER BY r.season_id DESC LIMIT 50").bind(teamId).all(); return jsonResponse({ ok: true, data: r.results || [] }, 200, origin); } catch (e) { return jsonResponse({ ok: false, error: e.message }, 500, origin); } }

// 获取选手详情
async function getPlayerDetail(env, playerId, origin = "") {
  try {
    // 选手基本信息
    const player = await env.CAMPAIGNS.prepare("SELECT * FROM players WHERE player_id = ?").bind(playerId).first();
    if (!player) return jsonResponse({ ok: false, error: "Player not found" }, 404, origin);
    
    // 获取当前赛季ID
    const currentSeason = await env.CAMPAIGNS.prepare(`
      SELECT season_id FROM seasons WHERE status = 'ongoing' ORDER BY start_date DESC LIMIT 1
    `).first();
    const currentSeasonId = currentSeason?.season_id || 'hpl_s2_2025';
    
    // 当前所属战队
    let currentTeam = null;
    try {
      const ct = await env.CAMPAIGNS.prepare(`
        SELECT r.team_id, t.canonical_name as team_name, r.season_id, r.role, s.season_type
        FROM rosters r
        JOIN teams t ON r.team_id = t.team_id
        JOIN seasons s ON r.season_id = s.season_id
        WHERE r.player_id = ? AND s.status = 'ongoing'
        LIMIT 1
      `).bind(playerId).first();
      if (ct) {
        currentTeam = {
          id: ct.team_id,
          name: ct.team_name,
          season: ct.season_id,
          role: ct.role,
          isLeague: ct.season_type !== 'cup',
          isCup: ct.season_type === 'cup'
        };
      }
    } catch(e) {}
    
    // 历史效力战队
    let teamHistory = [];
    try {
      const th = await env.CAMPAIGNS.prepare(`
        SELECT r.team_id, t.canonical_name as team_name, r.season_id, r.role, s.season_type, s.status as season_status, s.name as season_name
        FROM rosters r
        JOIN teams t ON r.team_id = t.team_id
        JOIN seasons s ON r.season_id = s.season_id
        WHERE r.player_id = ?
        ORDER BY s.start_date DESC
      `).bind(playerId).all();
      teamHistory = (th.results || []).map(x => ({
        team_id: x.team_id,
        team_name: x.team_name,
        season_id: x.season_id,
        season_name: x.season_name,
        role: x.role,
        isLeague: x.season_type !== 'cup',
        isCup: x.season_type === 'cup',
        isCurrent: x.season_status === 'ongoing'
      }));
    } catch(e) {}
    
    // 内部联赛成绩
    let internalStats = null;
    try {
      const ir = await env.CAMPAIGNS.prepare(`
        SELECT 
          SUM(total_points) as total_points, 
          SUM(points) as points,
          COUNT(*) as rounds_played,
          MAX(rank) as best_rank
        FROM internal_league_results 
        WHERE player_name = ?
      `).bind(player.nickname).first();
      if (ir && ir.total_points !== null) {
        internalStats = {
          total_points: ir.total_points,
          points: ir.points,
          rounds_played: ir.rounds_played,
          best_rank: ir.best_rank
        };
      }
    } catch(e) {}
    
    // 内部联赛历史记录
    let internalHistory = [];
    try {
      const ih = await env.CAMPAIGNS.prepare(`
        SELECT season_id, round_date, points, total_points, rank
        FROM internal_league_results 
        WHERE player_name = ?
        ORDER BY round_date DESC
        LIMIT 20
      `).bind(player.nickname).all();
      internalHistory = ih.results || [];
    } catch(e) {}
    
    return jsonResponse({ 
      ok: true, 
      data: {
        id: player.player_id,
        name: player.nickname,
        display_name: player.display_name,
        real_name: player.real_name,
        birth_year: player.birth_year,
        gender: player.gender,
        is_active: player.is_active,
        club_name: player.club_name,
        note: player.note,
        currentSeasonId,
        currentTeam: currentTeam,
        team_history: teamHistory,
        internal_stats: internalStats,
        internal_history: internalHistory
      }
    }, 200, origin);
  } catch (e) {
    return jsonResponse({ ok: false, error: e.message }, 500, origin);
  }
}
