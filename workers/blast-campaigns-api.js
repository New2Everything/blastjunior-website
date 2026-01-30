/**
 * BLAST Junior campaigns API (Bundle-only contract)
 * Required binding: env.DB (Cloudflare D1) bound as "DB"
 *
 * Public endpoints:
 * - GET /api/public/health
 * - GET /api/public/campaigns_bundle?event_id=&season_id=&division_key=&round_key=
 * - GET /api/public/team_bundle?team_id=
 * - GET /api/public/player_bundle?player_id= OR ?q=
 */

function qParam(url, key) {
  const v = url.searchParams.get(key);
  if (v == null) return null;
  const s = String(v).trim();
  return s === "" ? null : s;
}

function json(data, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(data, null, 2), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "access-control-allow-origin": "*",
      "access-control-allow-methods": "GET,OPTIONS",
      "access-control-allow-headers": "content-type",
      ...extraHeaders,
    },
  });
}

function corsPreflight() {
  return new Response(null, {
    status: 204,
    headers: {
      "access-control-allow-origin": "*",
      "access-control-allow-methods": "GET,OPTIONS",
      "access-control-allow-headers": "content-type",
    },
  });
}

async function firstRow(dbRes) {
  return dbRes?.results?.[0] ?? null;
}

/** Cache table columns to avoid repeated PRAGMA calls */
const __colsCache = new Map();

async function getCols(DB, table) {
  if (__colsCache.has(table)) return __colsCache.get(table);
  try {
    const res = await DB.prepare(`PRAGMA table_info(${table});`).all();
    const cols = new Set((res?.results ?? []).map(r => r.name));
    __colsCache.set(table, cols);
    return cols;
  } catch {
    const cols = new Set();
    __colsCache.set(table, cols);
    return cols;
  }
}

function pickCol(cols, candidates) {
  for (const c of candidates) if (cols.has(c)) return c;
  return null;
}

async function safeScalar(DB, sql, binds = []) {
  try {
    const row = await DB.prepare(sql).bind(...binds).first();
    if (!row) return null;
    const k = Object.keys(row)[0];
    return row[k];
  } catch {
    return null;
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") return corsPreflight();
    if (request.method !== "GET") return json({ ok: false, error: "Method Not Allowed" }, 405);

    try {
      if (!env?.DB) {
        return json(
          {
            ok: false,
            error: "Missing D1 binding env.DB",
            hint: "Check Worker bindings: D1 database should be bound as DB",
          },
          500
        );
      }

      switch (url.pathname) {
        case "/api/public/health":
          return json({ ok: true, ts: new Date().toISOString() });

        case "/api/public/campaigns_bundle":
          return await campaignsBundle(url, env.DB);

        case "/api/public/team_bundle":
          return await teamBundle(url, env.DB);

        case "/api/public/player_bundle":
          return await playerBundle(url, env.DB);

        default:
          return json({ ok: false, error: "Not Found", path: url.pathname }, 404);
      }
    } catch (err) {
      return json(
        {
          ok: false,
          error: "Internal Error",
          message: String(err?.message || err),
          stack: err?.stack ? String(err.stack).split("\n").slice(0, 10) : undefined,
        },
        500
      );
    }
  },
};

async function campaignsBundle(url, DB) {
  const q = url.searchParams;

  // Accept empty query params; default event is "hpl"
  const event_id_in = (q.get("event_id") || "").trim();
  const season_id_in = (q.get("season_id") || "").trim();
  const division_key_in = (q.get("division_key") || "").trim();
  const round_key_in = (q.get("round_key") || "").trim();

  const defaultEventId = "hpl";

  const eventsCols = await getCols(DB, "events");
  const seasonsCols = await getCols(DB, "seasons");
  const divisionsCols = await getCols(DB, "divisions");
  const scCols = await getCols(DB, "score_components");
  const regCols = await getCols(DB, "registrations");

  // 1) Events (always return full list)
  const ev_name_zh = pickCol(eventsCols, ["name_zh", "nameZh", "name_cn", "name"]);
  const ev_name_en = pickCol(eventsCols, ["name_en", "nameEn"]);
  const ev_level = pickCol(eventsCols, ["level"]);
  const ev_freq = pickCol(eventsCols, ["frequency"]);
  const ev_url = pickCol(eventsCols, ["official_url", "url"]);
  const ev_desc = pickCol(eventsCols, ["description", "desc"]);

  const evSelect = [
    "event_id",
    ev_name_zh ? `${ev_name_zh} AS name_zh` : "NULL AS name_zh",
    ev_name_en ? `${ev_name_en} AS name_en` : "NULL AS name_en",
    ev_level ? `${ev_level} AS level` : "NULL AS level",
    ev_freq ? `${ev_freq} AS frequency` : "NULL AS frequency",
    ev_url ? `${ev_url} AS official_url` : "NULL AS official_url",
    ev_desc ? `${ev_desc} AS description` : "NULL AS description",
  ].join(", ");

  const eventsRes = await DB.prepare(
    `SELECT ${evSelect} FROM events ORDER BY event_id ASC`
  ).all();

  const events = (eventsRes?.results ?? []).map((e) => ({
    ...e,
    name: e.name_zh || e.name_en || e.event_id,
  }));

  const chosenEventId =
    (event_id_in && events.find((e) => e.event_id === event_id_in))
      ? event_id_in
      : (events.find((e) => e.event_id === defaultEventId)?.event_id || events[0]?.event_id || defaultEventId);

  // 2) Seasons under event
  const s_name = pickCol(seasonsCols, ["name", "season_name"]);
  const s_year = pickCol(seasonsCols, ["year"]);
  const s_status = pickCol(seasonsCols, ["status"]);
  const s_start = pickCol(seasonsCols, ["start_date", "start"]);
  const s_end = pickCol(seasonsCols, ["end_date", "end"]);
  const s_notes = pickCol(seasonsCols, ["notes", "note"]);

  const seasonsSelect = [
    "season_id",
    "event_id",
    s_name ? `${s_name} AS name` : "season_id AS name",
    s_year ? `${s_year} AS year` : "NULL AS year",
    s_start ? `${s_start} AS start_date` : "NULL AS start_date",
    s_end ? `${s_end} AS end_date` : "NULL AS end_date",
    s_status ? `${s_status} AS status` : "NULL AS status",
    s_notes ? `${s_notes} AS notes` : "NULL AS notes",
  ].join(", ");

  const seasonsRes = await DB.prepare(
    `SELECT ${seasonsSelect}
     FROM seasons
     WHERE event_id = ?
     ORDER BY ${s_year ? "year DESC," : ""} season_id DESC`
  ).bind(chosenEventId).all();

  const seasons = seasonsRes?.results ?? [];
  const chosenSeasonId =
    (season_id_in && seasons.find((s) => s.season_id === season_id_in))
      ? season_id_in
      : (seasons[0]?.season_id ?? null);

  // 3) Divisions under season
  const d_name = pickCol(divisionsCols, ["name", "division_name"]);
  const d_lb = pickCol(divisionsCols, ["leaderboard_key", "leaderboardKey"]);
  const d_sort = pickCol(divisionsCols, ["sort_order", "sort", "order"]);

  const divisionsSelect = [
    "division_key",
    "season_id",
    d_name ? `${d_name} AS name` : "division_key AS name",
    d_lb ? `${d_lb} AS leaderboard_key` : "NULL AS leaderboard_key",
    d_sort ? `${d_sort} AS sort_order` : "NULL AS sort_order",
  ].join(", ");

  let divisions = [];
  let chosenDivisionKey = null;
  let chosenDivision = null;

  if (chosenSeasonId) {
    const divisionsRes = await DB.prepare(
      `SELECT ${divisionsSelect}
       FROM divisions
       WHERE season_id = ?
       ORDER BY ${d_sort ? "sort_order ASC," : ""} division_key ASC`
    ).bind(chosenSeasonId).all();

    divisions = divisionsRes?.results ?? [];
    chosenDivisionKey =
      (division_key_in && divisions.find((d) => d.division_key === division_key_in))
        ? division_key_in
        : (divisions[0]?.division_key ?? null);

    chosenDivision = chosenDivisionKey ? (divisions.find((d) => d.division_key === chosenDivisionKey) ?? null) : null;
  }

  // 4) Rounds under division.leaderboard_key
  const sc_name = pickCol(scCols, ["name"]);
  const sc_type = pickCol(scCols, ["component_type", "type"]);
  const sc_sort = pickCol(scCols, ["sort_order", "sort", "order"]);
  const sc_start = pickCol(scCols, ["start_date", "start"]);
  const sc_end = pickCol(scCols, ["end_date", "end"]);
  const sc_season = pickCol(scCols, ["season_id"]);

  let rounds = [];
  let chosenRoundKey = null;

  if (chosenDivision?.leaderboard_key) {
    const scSelect = [
      "component_id",
      "leaderboard_key",
      sc_name ? `${sc_name} AS name` : "component_id AS name",
      sc_type ? `${sc_type} AS component_type` : "NULL AS component_type",
      sc_start ? `${sc_start} AS start_date` : "NULL AS start_date",
      sc_end ? `${sc_end} AS end_date` : "NULL AS end_date",
      sc_sort ? `${sc_sort} AS sort_order` : "NULL AS sort_order",
    ].join(", ");

    const scWhere = [`leaderboard_key = ?`];
    const scBinds = [chosenDivision.leaderboard_key];
    if (sc_season && seasonsCols.has("season_id") && scCols.has("season_id")) {
      // Only add if score_components has season_id and seasons is present (guard)
      scWhere.push(`season_id = ?`);
      scBinds.push(chosenSeasonId);
    }

    const roundsRes = await DB.prepare(
      `SELECT ${scSelect}
       FROM score_components
       WHERE ${scWhere.join(" AND ")}
       ORDER BY ${sc_sort ? "sort_order ASC," : ""} component_id ASC`
    ).bind(...scBinds).all();

    rounds = (roundsRes?.results ?? []).map((r) => ({
      ...r,
      round_key: r.component_id,
      type: r.component_type,
    }));

    // Default: last component
    chosenRoundKey =
      (round_key_in && rounds.find((r) => r.round_key === round_key_in))
        ? round_key_in
        : (rounds.length ? rounds[rounds.length - 1].round_key : null);
  }

  // 5) Leaderboard (table)
  const leaderboard = (chosenSeasonId && chosenDivision)
    ? await computeLeaderboard({
        DB,
        season_id: chosenSeasonId,
        division_key: chosenDivision.division_key,
        leaderboard_key: chosenDivision.leaderboard_key,
        round_key: chosenRoundKey,
      })
    : [];

  // --- Overview (best-effort; safe if columns are missing) ---
  const overview = { teams_total: leaderboard.length };

  // Event overview: seasons_total, teams_total, last_update
  overview.event = {
    seasons_total: seasons.length,
    teams_total: (regCols.has("team_id") && regCols.has("season_id") && seasonsCols.has("event_id"))
      ? await safeScalar(
          DB,
          `SELECT COUNT(DISTINCT r.team_id) AS n
           FROM registrations r
           JOIN seasons s ON s.season_id = r.season_id
           WHERE s.event_id = ?`,
          [chosenEventId]
        )
      : null,
    last_update: null,
  };

  // Season overview
  overview.season = {
    divisions_total: divisions.length,
    teams_total: (regCols.has("team_id") && regCols.has("season_id"))
      ? await safeScalar(DB, `SELECT COUNT(DISTINCT team_id) AS n FROM registrations WHERE season_id = ?`, [chosenSeasonId])
      : null,
    start: null,
    end: null,
  };

  if (scCols.size && chosenSeasonId) {
    // Only if score_components exists and has sortable/time-ish columns
    const startExpr = sc_start ? `MIN(${sc_start})` : (sc_sort ? `MIN(${sc_sort})` : null);
    const endExpr = sc_end ? `MAX(${sc_end})` : (sc_sort ? `MAX(${sc_sort})` : null);

    if (startExpr) {
      overview.season.start = await safeScalar(DB, `SELECT ${startExpr} AS v FROM score_components ${sc_season ? "WHERE season_id = ?" : ""}`, sc_season ? [chosenSeasonId] : []);
    }
    if (endExpr) {
      overview.season.end = await safeScalar(DB, `SELECT ${endExpr} AS v FROM score_components ${sc_season ? "WHERE season_id = ?" : ""}`, sc_season ? [chosenSeasonId] : []);
    }
  }

  // Division overview
  const div_rounds = rounds.filter(r => String(r.type || "").toLowerCase() === "round");
  const div_groups = rounds.filter(r => String(r.type || "").toLowerCase() === "round_group");
  overview.division = {
    rounds_count: div_rounds.length,
    round_groups_count: div_groups.length,
    current_round_key: div_rounds.length ? div_rounds[div_rounds.length - 1].round_key : null,
    recent_component_key: rounds.length ? rounds[rounds.length - 1].round_key : null,
  };

  // Round overview (best-effort)
  overview.round = {
    teams_total: (regCols.has("team_id") && regCols.has("season_id"))
      ? await safeScalar(
          DB,
          `SELECT COUNT(DISTINCT team_id) AS n
           FROM registrations
           WHERE season_id = ?
             ${regCols.has("division") && chosenDivision?.division_key ? "AND (division IS NULL OR division = ?)" : ""}`,
          regCols.has("division") && chosenDivision?.division_key ? [chosenSeasonId, chosenDivision.division_key] : [chosenSeasonId]
        )
      : null,
  };

  const context = {
    event_id: chosenEventId,
    season_id: chosenSeasonId,
    division_key: chosenDivision?.division_key ?? null,
    round_key: chosenRoundKey,
  };

  return json({
    ok: true,
    context,
    selectors: { events, seasons, divisions, rounds },
    overview,
    table: leaderboard,

    // legacy (kept for transition)
    selected: context,
    events,
    seasons,
    divisions,
    rounds,
    leaderboard,
  });
}

async function computeLeaderboard({ DB, season_id, division_key, leaderboard_key, round_key }) {
  const teamsCols = await getCols(DB, "teams");
  const regCols = await getCols(DB, "registrations");
  const tcpCols = await getCols(DB, "team_component_points");
  const scCols = await getCols(DB, "score_components");

  const teamNameCol = pickCol(teamsCols, ["canonical_name", "name", "team_name"]);
  const divisionCol = pickCol(regCols, ["division", "division_key"]);

  if (!regCols.has("team_id") || !regCols.has("season_id")) {
    return [];
  }
  if (!tcpCols.has("registration_id") || !tcpCols.has("component_id") || !tcpCols.has("points")) {
    return [];
  }

  const teamNameExpr = teamNameCol ? `t.${teamNameCol}` : `t.team_id`;
  const divisionFilter = divisionCol ? `AND (r.${divisionCol} IS NULL OR r.${divisionCol} = ?)` : "";

  if (round_key) {
    const res = await DB.prepare(
      `SELECT
         r.team_id,
         ${teamNameExpr} AS team_name,
         COALESCE(SUM(CASE WHEN tcp.component_id = ? THEN tcp.points ELSE 0 END), 0) AS points
       FROM registrations r
       JOIN teams t ON t.team_id = r.team_id
       LEFT JOIN team_component_points tcp ON tcp.registration_id = r.registration_id
       WHERE r.season_id = ?
       ${divisionFilter}
       GROUP BY r.team_id, team_name
       ORDER BY points DESC, r.team_id ASC`
    )
      .bind(round_key, season_id, ...(divisionFilter ? [division_key] : []))
      .all();

    return (res?.results ?? []).map((x, idx) => ({
      rank: idx + 1,
      team_id: x.team_id,
      team_name: x.team_name,
      points: Number(x.points ?? 0),
    }));
  }

  // Total points within this division's leaderboard scope (if score_components exists)
  if (!scCols.has("leaderboard_key") || !scCols.has("component_id")) {
    // Fallback: sum all points for season/division
    const res = await DB.prepare(
      `SELECT
         r.team_id,
         ${teamNameExpr} AS team_name,
         COALESCE(SUM(tcp.points), 0) AS points
       FROM registrations r
       JOIN teams t ON t.team_id = r.team_id
       LEFT JOIN team_component_points tcp ON tcp.registration_id = r.registration_id
       WHERE r.season_id = ?
       ${divisionFilter}
       GROUP BY r.team_id, team_name
       ORDER BY points DESC, r.team_id ASC`
    )
      .bind(season_id, ...(divisionFilter ? [division_key] : []))
      .all();

    return (res?.results ?? []).map((x, idx) => ({
      rank: idx + 1,
      team_id: x.team_id,
      team_name: x.team_name,
      points: Number(x.points ?? 0),
    }));
  }

  const res = await DB.prepare(
    `SELECT
       r.team_id,
       ${teamNameExpr} AS team_name,
       COALESCE(SUM(CASE WHEN sc.component_id IS NOT NULL THEN tcp.points ELSE 0 END), 0) AS points
     FROM registrations r
     JOIN teams t ON t.team_id = r.team_id
     LEFT JOIN team_component_points tcp ON tcp.registration_id = r.registration_id
     LEFT JOIN score_components sc
       ON sc.component_id = tcp.component_id
      AND sc.leaderboard_key = ?
     WHERE r.season_id = ?
     ${divisionFilter}
     GROUP BY r.team_id, team_name
     ORDER BY points DESC, r.team_id ASC`
  )
    .bind(leaderboard_key, season_id, ...(divisionFilter ? [division_key] : []))
    .all();

  return (res?.results ?? []).map((x, idx) => ({
    rank: idx + 1,
    team_id: x.team_id,
    team_name: x.team_name,
    points: Number(x.points ?? 0),
  }));
}

async function teamBundle(url, DB) {
  const team_id = qParam(url, "team_id");
  if (!team_id) return json({ ok: false, error: "team_id is required" }, 400);

  const teamsCols = await getCols(DB, "teams");
  const teamNameCol = pickCol(teamsCols, ["canonical_name", "name", "team_name"]);
  const clubCol = pickCol(teamsCols, ["club_name", "club_id", "club"]);
  const firstSeenCol = pickCol(teamsCols, ["first_seen_season_id", "first_seen", "first_season_id"]);
  const noteCol = pickCol(teamsCols, ["note", "notes"]);

  const team = await firstRow(
    await DB.prepare(
      `SELECT
         team_id,
         ${teamNameCol ? `${teamNameCol} AS team_name` : "team_id AS team_name"},
         ${clubCol ? `${clubCol} AS club` : "NULL AS club"},
         ${firstSeenCol ? `${firstSeenCol} AS first_seen_season_id` : "NULL AS first_seen_season_id"},
         ${noteCol ? `${noteCol} AS note` : "NULL AS note"}
       FROM teams
       WHERE team_id = ?`
    ).bind(team_id).all()
  );

  if (!team) return json({ ok: false, error: "Team not found", team_id }, 404);

  const aliasesCols = await getCols(DB, "team_aliases");
  const aliasNameCol = pickCol(aliasesCols, ["alias_name", "name", "alias"]);
  const aliasFromCol = pickCol(aliasesCols, ["from_date", "from"]);
  const aliasToCol = pickCol(aliasesCols, ["to_date", "to"]);
  const aliasNoteCol = pickCol(aliasesCols, ["note", "notes"]);

  const aliasesRes = aliasesCols.size
    ? await DB.prepare(
        `SELECT
           ${aliasNameCol ? `${aliasNameCol} AS alias_name` : "NULL AS alias_name"},
           ${aliasFromCol ? `${aliasFromCol} AS from_date` : "NULL AS from_date"},
           ${aliasToCol ? `${aliasToCol} AS to_date` : "NULL AS to_date"},
           ${aliasNoteCol ? `${aliasNoteCol} AS note` : "NULL AS note"}
         FROM team_aliases
         WHERE team_id = ?`
      ).bind(team_id).all()
    : { results: [] };

  const rostersCols = await getCols(DB, "rosters");
  const playersCols = await getCols(DB, "players");

  const pNick = pickCol(playersCols, ["nickname", "display_name", "name"]);
  const pReal = pickCol(playersCols, ["real_name"]);
  const pBirth = pickCol(playersCols, ["birth_year", "birthYear"]);
  const pClub = pickCol(playersCols, ["club_name", "club"]);

  const rosterRes = (rostersCols.has("player_id") && rostersCols.has("team_id"))
    ? await DB.prepare(
        `SELECT
           ${rostersCols.has("season_id") ? "r.season_id," : "NULL AS season_id,"}
           r.player_id,
           ${pNick ? `p.${pNick} AS nickname` : "p.player_id AS nickname"},
           ${pReal ? `p.${pReal} AS real_name` : "NULL AS real_name"},
           ${pBirth ? `p.${pBirth} AS birth_year` : "NULL AS birth_year"},
           ${pClub ? `p.${pClub} AS club_name` : "NULL AS club_name"}
         FROM rosters r
         JOIN players p ON p.player_id = r.player_id
         WHERE r.team_id = ?
         ORDER BY ${rostersCols.has("season_id") ? "r.season_id DESC," : ""} nickname ASC, r.player_id ASC`
      ).bind(team_id).all()
    : { results: [] };

  const regCols = await getCols(DB, "registrations");
  const seasonsCols = await getCols(DB, "seasons");
  const sName = pickCol(seasonsCols, ["name", "season_name"]);
  const sYear = pickCol(seasonsCols, ["year"]);
  const sStatus = pickCol(seasonsCols, ["status"]);

  const registrationsRes = (regCols.has("team_id") && regCols.has("season_id"))
    ? await DB.prepare(
        `SELECT
           ${regCols.has("registration_id") ? "r.registration_id," : "NULL AS registration_id,"}
           r.season_id,
           ${sName ? `s.${sName} AS season_name` : "s.season_id AS season_name"},
           ${sYear ? `s.${sYear} AS year` : "NULL AS year"},
           ${sStatus ? `s.${sStatus} AS status` : "NULL AS status"},
           ${pickCol(regCols, ["division", "division_key"]) ? `r.${pickCol(regCols, ["division", "division_key"])} AS division` : "NULL AS division"}
         FROM registrations r
         JOIN seasons s ON s.season_id = r.season_id
         WHERE r.team_id = ?
         ORDER BY ${sYear ? "s.year DESC," : ""} r.season_id DESC`
      ).bind(team_id).all()
    : { results: [] };

  const tcpCols = await getCols(DB, "team_component_points");
  const scCols = await getCols(DB, "score_components");
  const scName = pickCol(scCols, ["name"]);

  const pointsRes = (regCols.has("team_id") && regCols.has("registration_id") && tcpCols.has("registration_id"))
    ? await DB.prepare(
        `SELECT
           rg.season_id,
           tcp.component_id,
           ${scName ? "sc.name AS component_name," : "NULL AS component_name,"}
           ${pickCol(scCols, ["component_type", "type"]) ? `sc.${pickCol(scCols, ["component_type", "type"])} AS component_type,` : "NULL AS component_type,"}
           SUM(tcp.points) AS points
         FROM registrations rg
         JOIN team_component_points tcp ON tcp.registration_id = rg.registration_id
         LEFT JOIN score_components sc ON sc.component_id = tcp.component_id
         WHERE rg.team_id = ?
         GROUP BY rg.season_id, tcp.component_id
         ORDER BY rg.season_id DESC, points DESC, tcp.component_id ASC`
      ).bind(team_id).all()
    : { results: [] };

  // Minimal summary (safe): participations count based on registrations
  const summary = {
    participations: (registrationsRes?.results ?? []).length,
    best_rank: null,
    champion_count: 0,
    podium_count: 0,
  };

  return json({
    ok: true,
    summary,
    team,
    aliases: aliasesRes?.results ?? [],
    roster: rosterRes?.results ?? [],
    registrations: registrationsRes?.results ?? [],
    points: (pointsRes?.results ?? []).map((x) => ({ ...x, points: Number(x.points ?? 0) })),
  });
}

async function playerBundle(url, DB) {
  const player_id = qParam(url, "player_id");
  const q = qParam(url, "q");

  const playersCols = await getCols(DB, "players");
  const pNick = pickCol(playersCols, ["nickname", "display_name", "name"]);
  const pDisp = pickCol(playersCols, ["display_name"]);
  const pReal = pickCol(playersCols, ["real_name"]);
  const pBirth = pickCol(playersCols, ["birth_year", "birthYear"]);
  const pActive = pickCol(playersCols, ["is_active", "active"]);
  const pNotes = pickCol(playersCols, ["notes", "note"]);
  const pClub = pickCol(playersCols, ["club_name", "club"]);
  const pJoined = pickCol(playersCols, ["joined_at", "created_at"]);

  const playerSelect = [
    "player_id",
    pNick ? `${pNick} AS nickname` : "player_id AS nickname",
    pDisp ? `${pDisp} AS display_name` : "NULL AS display_name",
    pReal ? `${pReal} AS real_name` : "NULL AS real_name",
    pBirth ? `${pBirth} AS birth_year` : "NULL AS birth_year",
    pActive ? `${pActive} AS is_active` : "NULL AS is_active",
    pNotes ? `${pNotes} AS notes` : "NULL AS notes",
    pClub ? `${pClub} AS club_name` : "NULL AS club_name",
    pJoined ? `${pJoined} AS joined_at` : "NULL AS joined_at",
  ].join(", ");

  let player = null;
  if (player_id) {
    player = await firstRow(await DB.prepare(`SELECT ${playerSelect} FROM players WHERE player_id = ?`).bind(player_id).all());
  } else if (q) {
    const like = `%${q}%`;
    const clauses = ["player_id = ?"];
    const binds = [q];

    if (pNick) { clauses.push(`${pNick} LIKE ?`); binds.push(like); }
    if (pReal) { clauses.push(`${pReal} LIKE ?`); binds.push(like); }
    if (pDisp) { clauses.push(`${pDisp} LIKE ?`); binds.push(like); }

    const res = await DB.prepare(
      `SELECT ${playerSelect}
       FROM players
       WHERE ${clauses.join(" OR ")}
       ORDER BY (player_id = ?) DESC
       LIMIT 1`
    ).bind(...binds, q).all();
    player = res?.results?.[0] ?? null;
  }

  if (!player) return json({ ok: false, error: "Player not found", player_id, q }, 404);

  const rostersCols = await getCols(DB, "rosters");
  const teamsCols = await getCols(DB, "teams");
  const teamNameCol = pickCol(teamsCols, ["canonical_name", "name", "team_name"]);

  const rostersRes = (rostersCols.has("player_id") && rostersCols.has("team_id"))
    ? await DB.prepare(
        `SELECT
           ${rostersCols.has("season_id") ? "r.season_id," : "NULL AS season_id,"}
           r.team_id,
           ${teamNameCol ? `t.${teamNameCol} AS team_name` : "t.team_id AS team_name"}
         FROM rosters r
         JOIN teams t ON t.team_id = r.team_id
         WHERE r.player_id = ?
         ORDER BY ${rostersCols.has("season_id") ? "r.season_id DESC," : ""} r.team_id ASC`
      ).bind(player.player_id).all()
    : { results: [] };

  const seasonsCols = await getCols(DB, "seasons");
  const sEvent = pickCol(seasonsCols, ["event_id"]);
  const sName = pickCol(seasonsCols, ["name", "season_name"]);
  const sYear = pickCol(seasonsCols, ["year"]);
  const sStatus = pickCol(seasonsCols, ["status"]);

  const seasonsRes = (rostersCols.has("player_id") && rostersCols.has("season_id"))
    ? await DB.prepare(
        `SELECT DISTINCT
           r.season_id
           ${sEvent ? ", s.event_id" : ", NULL AS event_id"}
           ${sName ? `, s.${sName} AS season_name` : ", s.season_id AS season_name"}
           ${sYear ? `, s.${sYear} AS year` : ", NULL AS year"}
           ${sStatus ? `, s.${sStatus} AS status` : ", NULL AS status"}
         FROM rosters r
         JOIN seasons s ON s.season_id = r.season_id
         WHERE r.player_id = ?
         ORDER BY ${sYear ? "s.year DESC," : ""} r.season_id DESC`
      ).bind(player.player_id).all()
    : { results: [] };

  const summary = {
    participations: (seasonsRes?.results ?? []).length,
    teams_played: await (async () => {
      if (!rostersCols.has("player_id") || !rostersCols.has("team_id")) return 0;
      const x = await safeScalar(DB, `SELECT COUNT(DISTINCT team_id) AS n FROM rosters WHERE player_id = ?`, [player.player_id]);
      return x ?? 0;
    })(),
    best_rank: null,
    champion_count: 0,
    podium_count: 0,
  };

  return json({
    ok: true,
    summary,
    player,
    rosters: rostersRes?.results ?? [],
    seasons: seasonsRes?.results ?? [],
  });
}
