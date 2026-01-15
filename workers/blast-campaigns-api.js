/**
 * Cloudflare Workers - blast-campaigns-api (Public API)
 * Binding:
 *   - D1 Database: env.DB
 *
 * Routes (public):
 *   GET /api/public/health
 *   GET /api/public/seasons
 *   GET /api/public/divisions?season_id=...
 *   GET /api/public/players
 *   GET /api/public/teams?season_id=... (optional)
 *   GET /api/public/leaderboards?season_id=...        ✅ NEW: list leaderboard_keys for a season
 *   GET /api/public/leaderboard?season_id=...&leaderboard_key=...   ✅ FIXED: includes 0-point teams
 *   GET /api/public/team?team_id=...&season_id=... (season optional)
 *   GET /api/public/rounds?season_id=...&leaderboard_key=... (optional)
 *   GET /api/public/round?component_id=...
 *
 * Notes:
 * - CORS enabled for read-only usage
 * - Uses safe parameter binding for SQL
 */

export default {
  async fetch(request, env, ctx) {
    try {
      const url = new URL(request.url);

      // CORS preflight
      if (request.method === "OPTIONS") return corsPreflight();

      // Basic routing
      if (!url.pathname.startsWith("/api/public/")) {
        return json({ ok: false, error: "Not Found" }, 404);
      }

      // Only allow GET for public API
      if (request.method !== "GET") {
        return json({ ok: false, error: "Method Not Allowed" }, 405);
      }

      const path = url.pathname;

      if (path === "/api/public/health") {
        return json({ ok: true, service: "blast-campaigns-api", ts: new Date().toISOString() });
      }

      if (path === '/api/public/events') return handleEvents(env);


      if (path === "/api/public/seasons") {
        return handleSeasons(url, env);
      }

      if (path === "/api/public/divisions") {
        const season_id = mustParam(url, "season_id");
        return handleDivisions(env, season_id);
      }

      // ✅ players list (you asked: “players 清单接口不能少”)
      if (path === "/api/public/players") {
        return handlePlayers(env);
      }

      if (path === "/api/public/player") {
        const player_id = mustParam(url, "player_id");
        return handlePlayer(env, { player_id });
      }

      if (path === "/api/public/teams") {
        const season_id = url.searchParams.get("season_id"); // optional
        return handleTeams(env, season_id);
      }

      // ✅ NEW: list leaderboard keys available for a season
      if (path === "/api/public/leaderboards") {
        const season_id = mustParam(url, "season_id");
        return handleLeaderboards(env, { season_id });
      }

      // ✅ FIXED leaderboard: include 0-point teams
      if (path === "/api/public/leaderboard") {
        const season_id = mustParam(url, "season_id");
        const leaderboard_key = mustParam(url, "leaderboard_key");
        return handleLeaderboard(env, { season_id, leaderboard_key });
      }

      if (path === "/api/public/team") {
        const team_id = mustParam(url, "team_id");
        const season_id = url.searchParams.get("season_id"); // optional
        return handleTeamDetail(env, { team_id, season_id });
      }

      if (path === "/api/public/rounds") {
        const season_id = mustParam(url, "season_id");
        const leaderboard_key = url.searchParams.get("leaderboard_key"); // optional
        return handleRounds(env, { season_id, leaderboard_key });
      }

      if (path === "/api/public/round") {
        const component_id = mustParam(url, "component_id");
        return handleRoundDetail(env, { component_id });
      }

      return json({ ok: false, error: "Not Found" }, 404);
    } catch (err) {
      return json({ ok: false, error: err?.message || String(err) }, 500);
    }
  },
};

/* ----------------------------- Handlers ----------------------------- */

async function handleEvents(env) {
  const sql = `
    SELECT event_id, name_zh, name_en
    FROM events
    ORDER BY event_id ASC
  `;
  const rs = await env.DB.prepare(sql).all();
  return json(rs.results || []);
}


async function handleSeasons(url, env) {
  const eventId = url.searchParams.get('event_id'); // 可选

  let sql = `
    SELECT
      season_id,
      event_id,
      name,
      year,
      start_date,
      end_date,
      status,
      notes
    FROM seasons
  `;
  const binds = [];

  if (eventId) {
    sql += ` WHERE event_id = ? `;
    binds.push(eventId);
  }

  sql += ` ORDER BY year DESC, start_date DESC, season_id DESC `;

  const rs = await env.DB.prepare(sql).bind(...binds).all();
  return json(rs.results || []);
}


async function handleDivisions(env, season_id) {
  const rows = await env.DB.prepare(
    `
    SELECT division_id, season_id, division_key, name, sort_order, notes, leaderboard_key, created_at, updated_at
    FROM divisions
    WHERE season_id = ?
    ORDER BY sort_order ASC, name ASC
    `
  )
    .bind(season_id)
    .all();

  return json({ season_id, divisions: rows.results || [] });
}

async function handlePlayers(env) {
  const rows = await env.DB.prepare(
    `
    SELECT
      player_id,
      nickname,
      display_name,
      real_name,
      birth_year,
      gender,
      club_name,
      joined_at,
      is_active,
      notes,
      created_at,
      updated_at
    FROM players
    ORDER BY
      CASE WHEN is_active IS NULL THEN 1 ELSE 0 END,
      is_active DESC,
      CASE WHEN nickname IS NULL THEN 1 ELSE 0 END,
      nickname COLLATE NOCASE ASC,
      player_id ASC
    `
  ).all();

  return json({ players: rows.results || [] });
}

async function handleTeams(env, season_id) {
  if (season_id) {
    const rows = await env.DB.prepare(
      `
      SELECT
        t.team_id,
        t.canonical_name,
        t.club_id,
        t.first_seen_season_id,
        t.note,
        t.created_at,
        t.updated_at,
        r.registration_id,
        r.division,
        r.status
      FROM registrations r
      JOIN teams t ON t.team_id = r.team_id
      WHERE r.season_id = ?
      ORDER BY t.canonical_name COLLATE NOCASE ASC
      `
    )
      .bind(season_id)
      .all();

    return json({ season_id, teams: rows.results || [] });
  }

  const rows = await env.DB.prepare(
    `
    SELECT team_id, canonical_name, club_id, first_seen_season_id, note, created_at, updated_at
    FROM teams
    ORDER BY canonical_name COLLATE NOCASE ASC
    `
  ).all();

  return json({ teams: rows.results || [] });
}

/**
 * ✅ FIXED:
 * - include 0-point teams
 * - leaderboard_key condition moved into JOIN score_components
 */
async function handleLeaderboard(env, { season_id, leaderboard_key }) {
  const sql = `
    SELECT
      t.team_id,
      t.canonical_name AS team_name,
      r.registration_id,
      COALESCE(SUM(CASE WHEN c.component_id IS NOT NULL THEN tcp.points ELSE 0 END), 0) AS points
    FROM registrations r
    JOIN teams t ON t.team_id = r.team_id

    LEFT JOIN team_component_points tcp
      ON tcp.registration_id = r.registration_id

    LEFT JOIN score_components c
      ON c.component_id = tcp.component_id
      AND c.source_season_id = r.season_id
      AND (
        c.leaderboard_key = ?
        OR c.leaderboard_key LIKE ? || '_%'
      )

    WHERE r.season_id = ?
      AND (r.status IS NULL OR r.status <> 'cancelled')

    GROUP BY t.team_id, t.canonical_name, r.registration_id
    ORDER BY points DESC, t.canonical_name COLLATE NOCASE ASC
  `;

  const rows = await env.DB
    .prepare(sql)
    .bind(leaderboard_key, leaderboard_key, season_id)
    .all();

  const ranked = addRankWithTies(rows.results || [], "points");

  return json({
    season_id,
    leaderboard_key,
    rows: ranked,
  });
}


async function handleTeamDetail(env, { team_id, season_id }) {
  const team = await env.DB.prepare(
    `
    SELECT team_id, canonical_name, club_id, first_seen_season_id, note, created_at, updated_at
    FROM teams
    WHERE team_id = ?
    `
  )
    .bind(team_id)
    .first();

  if (!team) return json({ ok: false, error: "team not found" }, 404);

  const aliases = await env.DB.prepare(
    `
    SELECT alias_id, team_id, alias_name, from_date, to_date, note, created_at
    FROM team_aliases
    WHERE team_id = ?
    ORDER BY created_at ASC
    `
  )
    .bind(team_id)
    .all();

  const regBinds = [team_id];
  let regWhere = `WHERE r.team_id = ?`;
  if (season_id) {
    regWhere += ` AND r.season_id = ?`;
    regBinds.push(season_id);
  }

  const registrations = await env.DB.prepare(
    `
    SELECT r.registration_id, r.season_id, r.team_id, r.club_id, r.division, r.status, r.note, r.created_at
    FROM registrations r
    ${regWhere}
    ORDER BY r.created_at DESC
    `
  )
    .bind(...regBinds)
    .all();

  const rosterBinds = [team_id];
  let rosterWhere = `WHERE ro.team_id = ?`;
  if (season_id) {
    rosterWhere += ` AND ro.season_id = ?`;
    rosterBinds.push(season_id);
  }

  const roster = await env.DB.prepare(
    `
    SELECT
      ro.roster_id,
      ro.season_id,
      ro.team_id,
      ro.player_id,
      ro.role,
      ro.notes,
      ro.created_at,
      p.nickname,
      p.display_name,
      p.real_name,
      p.club_name,
      p.is_active
    FROM rosters ro
    LEFT JOIN players p ON p.player_id = ro.player_id
    ${rosterWhere}
    ORDER BY ro.season_id DESC, ro.created_at ASC
    `
  )
    .bind(...rosterBinds)
    .all();

  const totals = await env.DB.prepare(
    `
    SELECT
      r.season_id,
      COALESCE(SUM(tcp.points), 0) AS points
    FROM registrations r
    LEFT JOIN team_component_points tcp ON tcp.registration_id = r.registration_id
    LEFT JOIN score_components c
      ON c.component_id = tcp.component_id
      AND c.source_season_id = r.season_id
    WHERE r.team_id = ?
    GROUP BY r.season_id
    ORDER BY r.season_id DESC
    `
  )
    .bind(team_id)
    .all();

  const detailBinds = [team_id];
  let detailWhere = `WHERE r.team_id = ?`;
  if (season_id) {
    detailWhere += ` AND r.season_id = ?`;
    detailBinds.push(season_id);
  }

  const componentPoints = await env.DB.prepare(
    `
    SELECT
      r.season_id,
      r.registration_id,
      c.component_id,
      c.name,
      c.component_type,
      c.start_date,
      c.end_date,
      c.sort_order,
      c.leaderboard_key,
      COALESCE(SUM(tcp.points), 0) AS points
    FROM registrations r
    LEFT JOIN team_component_points tcp ON tcp.registration_id = r.registration_id
    LEFT JOIN score_components c
      ON c.component_id = tcp.component_id
      AND c.source_season_id = r.season_id
    ${detailWhere}
    GROUP BY r.season_id, r.registration_id, c.component_id, c.name, c.component_type, c.start_date, c.end_date, c.sort_order, c.leaderboard_key
    ORDER BY r.season_id DESC, c.sort_order ASC, c.start_date ASC, c.component_id ASC
    `
  )
    .bind(...detailBinds)
    .all();

  return json({
    team,
    aliases: aliases.results || [],
    registrations: registrations.results || [],
    roster: roster.results || [],
    season_totals: totals.results || [],
    component_points: componentPoints.results || [],
  });
}

async function handleRounds(url, env) {
  const leaderboardKey = url.searchParams.get('leaderboard_key');
  const seasonId = url.searchParams.get('season_id');
  const mode = url.searchParams.get('mode') || 'round'; // round | round_group

  if (!leaderboardKey) return json({ error: 'Missing required param: leaderboard_key' }, 400);
  if (!seasonId) return json({ error: 'Missing required param: season_id' }, 400);

  const likeKey = leaderboardKey + '%';
  const wantType = mode === 'round_group' ? 'round_group' : 'round';

  const sql = `
    SELECT
      component_id,
      leaderboard_key,
      name,
      component_type,
      start_date,
      end_date,
      sort_order
    FROM score_components
    WHERE leaderboard_key LIKE ?
      AND source_season_id = ?
      AND component_type = ?
    ORDER BY sort_order ASC, start_date ASC, component_id ASC
  `;

  const rs = await env.DB.prepare(sql).bind(likeKey, seasonId, wantType).all();
  return json(rs.results || []);
}



async function handleRoundDetail(env, { component_id }) {
  const component = await env.DB.prepare(
    `
    SELECT
      component_id,
      source_season_id,
      leaderboard_key,
      name,
      component_type,
      start_date,
      end_date,
      sort_order,
      notes,
      created_at
    FROM score_components
    WHERE component_id = ?
    `
  )
    .bind(component_id)
    .first();

  if (!component) return json({ ok: false, error: "component not found" }, 404);

  const rows = await env.DB.prepare(
    `
    SELECT
      r.season_id,
      r.division,
      r.registration_id,
      t.team_id,
      t.canonical_name AS team_name,
      COALESCE(SUM(tcp.points), 0) AS points
    FROM team_component_points tcp
    JOIN registrations r ON r.registration_id = tcp.registration_id
    JOIN teams t ON t.team_id = r.team_id
    JOIN score_components c ON c.component_id = tcp.component_id
    WHERE tcp.component_id = ?
      AND c.source_season_id = r.season_id
    GROUP BY r.season_id, r.division, r.registration_id, t.team_id, t.canonical_name
    ORDER BY points DESC, t.canonical_name COLLATE NOCASE ASC
    `
  )
    .bind(component_id)
    .all();

  const ranked = addRankWithTies(rows.results || [], "points");

  return json({ component, rows: ranked });
}

async function handlePlayer(env, { player_id }) {
  const player = await env.DB.prepare(
    `
    SELECT
      player_id,
      nickname,
      display_name,
      real_name,
      birth_year,
      gender,
      club_name,
      joined_at,
      is_active,
      notes,
      created_at,
      updated_at
    FROM players
    WHERE player_id = ?
    `
  ).bind(player_id).first();

  if (!player) return json({ ok: false, error: "player not found" }, 404);

  // 该球员出现在哪些 rosters（含队名、赛季）
  const rosters = await env.DB.prepare(
    `
    SELECT
      ro.roster_id,
      ro.season_id,
      ro.team_id,
      t.canonical_name AS team_name,
      ro.role,
      ro.notes,
      ro.created_at
    FROM rosters ro
    LEFT JOIN teams t ON t.team_id = ro.team_id
    WHERE ro.player_id = ?
    ORDER BY ro.season_id DESC, ro.created_at DESC
    `
  ).bind(player_id).all();

  return json({
    player,
    rosters: rosters.results || []
  });
}


/* ----------------------------- Utilities ----------------------------- */

function mustParam(url, key) {
  const v = url.searchParams.get(key);
  if (!v) throw new Error(`Missing required param: ${key}`);
  return v;
}

function addRankWithTies(rows, pointsKey) {
  let rank = 0;
  let lastPoints = null;
  let seen = 0;

  return rows.map((r) => {
    seen += 1;
    const pts = Number(r[pointsKey] ?? 0);
    if (lastPoints === null || pts !== lastPoints) {
      rank = seen;
      lastPoints = pts;
    }
    return { rank, ...r, [pointsKey]: pts };
  });
}

function corsHeaders() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Access-Control-Max-Age": "86400",
  };
}

function corsPreflight() {
  return new Response(null, { status: 204, headers: corsHeaders() });
}

function json(data, status = 200, extraHeaders = {}) {
  const headers = {
    "Content-Type": "application/json; charset=utf-8",
    "X-Content-Type-Options": "nosniff",

    // ✅ 建议：public API 用短缓存（消掉你截图里 cache-control 相关“错误/警告”）
    // 如果你怕缓存影响调试：临时改成 "no-store" 也行，但会继续出现“不推荐”的提示
    "Cache-Control": "public, max-age=60",

    ...corsHeaders(),
    ...extraHeaders,
  };

  return new Response(JSON.stringify(data, null, 2), { status, headers });
}

