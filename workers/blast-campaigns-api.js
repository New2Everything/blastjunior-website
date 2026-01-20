/**
 * BLAST Junior campaigns API (Bundle-only contract)
 *
 * Required binding: env.DB (Cloudflare D1)
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
            hint: "Check your Worker bindings: D1 database should be bound as DB",
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
      // Always JSON, so the browser network panel shows useful data.
      return json(
        {
          ok: false,
          error: "Internal Error",
          message: String(err?.message || err),
          // stack is sometimes available in Workers; safe to include for debugging.
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

  // 1) Events (always return full list)
  const eventsRes = await DB.prepare(
    `SELECT event_id, name_zh, name_en, level, frequency, official_url, description
     FROM events
     ORDER BY event_id ASC`
  ).all();

  const events = (eventsRes?.results ?? []).map((e) => ({
    ...e,
    name: e.name_zh || e.name_en || e.event_id,
  }));

  const chosenEventId = (event_id_in && events.find((e) => e.event_id === event_id_in))
    ? event_id_in
    : (events.find((e) => e.event_id === defaultEventId)?.event_id || events[0]?.event_id || defaultEventId);

  // 2) Seasons under event
  const seasonsRes = await DB.prepare(
    `SELECT season_id, event_id, name, year, start_date, end_date, status, notes
     FROM seasons
     WHERE event_id = ?
     ORDER BY year DESC, season_id DESC`
  ).bind(chosenEventId).all();

  const seasons = seasonsRes?.results ?? [];
  const chosenSeasonId = (season_id_in && seasons.find((s) => s.season_id === season_id_in))
    ? season_id_in
    : (seasons[0]?.season_id ?? null);

  // Early: no seasons
  if (!chosenSeasonId) {
    const context = { event_id: chosenEventId, season_id: null, division_key: null, round_key: null };
    return json({
      ok: true,
      context,
      selectors: { events, seasons: [], divisions: [], rounds: [] },
      overview: { teams_total: 0 },
      table: [],
      // legacy
      selected: context,
      events,
      seasons: [],
      divisions: [],
      rounds: [],
      leaderboard: [],
    });
  }

  // 3) Divisions under season
  const divisionsRes = await DB.prepare(
    `SELECT division_key, season_id, name, leaderboard_key, sort_order, notes
     FROM divisions
     WHERE season_id = ?
     ORDER BY sort_order ASC, division_key ASC`
  ).bind(chosenSeasonId).all();

  const divisions = divisionsRes?.results ?? [];
  const chosenDivisionKey = (division_key_in && divisions.find((d) => d.division_key === division_key_in))
    ? division_key_in
    : (divisions[0]?.division_key ?? null);

  const chosenDivision = chosenDivisionKey
    ? (divisions.find((d) => d.division_key === chosenDivisionKey) ?? null)
    : null;

  // Early: no divisions
  if (!chosenDivision) {
    const context = { event_id: chosenEventId, season_id: chosenSeasonId, division_key: null, round_key: null };
    return json({
      ok: true,
      context,
      selectors: { events, seasons, divisions: [], rounds: [] },
      overview: { teams_total: 0 },
      table: [],
      // legacy
      selected: context,
      events,
      seasons,
      divisions: [],
      rounds: [],
      leaderboard: [],
    });
  }

  // 4) Rounds/groups in score_components under division.leaderboard_key
  const roundsRes = await DB.prepare(
    `SELECT component_id, leaderboard_key, name, component_type, start_date, end_date, sort_order, notes
     FROM score_components
     WHERE leaderboard_key = ?
     ORDER BY sort_order ASC, component_id ASC`
  ).bind(chosenDivision.leaderboard_key).all();

  const rounds = (roundsRes?.results ?? []).map((r) => ({
    ...r,
    round_key: r.component_id,
    type: r.component_type,
  }));

  // Default: last item
  const chosenRoundKey = (round_key_in && rounds.find((r) => r.round_key === round_key_in))
    ? round_key_in
    : (rounds.length ? rounds[rounds.length - 1].round_key : null);

  // 5) Leaderboard (table)
  const leaderboard = await computeLeaderboard({
    DB,
    season_id: chosenSeasonId,
    division_key: chosenDivision.division_key,
    leaderboard_key: chosenDivision.leaderboard_key,
    round_key: chosenRoundKey,
  });

  const context = {
    event_id: chosenEventId,
    season_id: chosenSeasonId,
    division_key: chosenDivision.division_key,
    round_key: chosenRoundKey,
  };

  return json({
    ok: true,
    context,
    selectors: { events, seasons, divisions, rounds },
    overview: { teams_total: leaderboard.length },
    table: leaderboard,

    // legacy
    selected: context,
    events,
    seasons,
    divisions,
    rounds,
    leaderboard,
  });
}

async function computeLeaderboard
({ DB, season_id, division_key, leaderboard_key, round_key }) {
  // registrations: which teams are participating in a season (+division if populated)
  // team_component_points: points per registration_id per component_id
  // score_components: defines which component_id belongs to a leaderboard_key

  // Include teams with zero points.
  // IMPORTANT: schema uses teams.canonical_name, team_component_points.registration_id (not team_id).

  if (round_key) {
    const res = await DB.prepare(
      `SELECT
         r.team_id,
         t.canonical_name AS team_name,
         COALESCE(SUM(CASE WHEN tcp.component_id = ? THEN tcp.points ELSE 0 END), 0) AS points
       FROM registrations r
       JOIN teams t ON t.team_id = r.team_id
       LEFT JOIN team_component_points tcp ON tcp.registration_id = r.registration_id
       WHERE r.season_id = ?
         AND (r.division IS NULL OR r.division = ?)
       GROUP BY r.team_id, t.canonical_name
       ORDER BY points DESC, r.team_id ASC`
    )
      .bind(round_key, season_id, division_key)
      .all();

    return (res?.results ?? []).map((x, idx) => ({
      rank: idx + 1,
      team_id: x.team_id,
      team_name: x.team_name,
      points: Number(x.points ?? 0),
    }));
  }

  // Total points within this division's leaderboard scope.
  const res = await DB.prepare(
    `SELECT
       r.team_id,
       t.canonical_name AS team_name,
       COALESCE(SUM(CASE WHEN sc.component_id IS NOT NULL THEN tcp.points ELSE 0 END), 0) AS points
     FROM registrations r
     JOIN teams t ON t.team_id = r.team_id
     LEFT JOIN team_component_points tcp ON tcp.registration_id = r.registration_id
     LEFT JOIN score_components sc
       ON sc.component_id = tcp.component_id
      AND sc.leaderboard_key = ?
     WHERE r.season_id = ?
       AND (r.division IS NULL OR r.division = ?)
     GROUP BY r.team_id, t.canonical_name
     ORDER BY points DESC, r.team_id ASC`
  )
    .bind(leaderboard_key, season_id, division_key)
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

  const team = await firstRow(
    await DB.prepare(
      `SELECT team_id, canonical_name, club_id, first_seen_season_id, note
       FROM teams
       WHERE team_id = ?`
    )
      .bind(team_id)
      .all()
  );

  if (!team) return json({ ok: false, error: "Team not found", team_id }, 404);

  const aliasesRes = await DB.prepare(
    `SELECT alias_name, from_date, to_date, note
     FROM team_aliases
     WHERE team_id = ?
     ORDER BY created_at ASC`
  )
    .bind(team_id)
    .all();

  const rosterRes = await DB.prepare(
    `SELECT
       r.season_id,
       r.player_id,
       p.nickname,
       p.real_name,
       p.birth_year,
       p.club_name
     FROM rosters r
     JOIN players p ON p.player_id = r.player_id
     WHERE r.team_id = ?
     ORDER BY r.season_id DESC, p.nickname ASC, r.player_id ASC`
  )
    .bind(team_id)
    .all();

  const registrationsRes = await DB.prepare(
    `SELECT
       r.registration_id,
       r.season_id,
       s.name AS season_name,
       s.year,
       s.status,
       r.division,
       r.status AS registration_status
     FROM registrations r
     JOIN seasons s ON s.season_id = r.season_id
     WHERE r.team_id = ?
     ORDER BY s.year DESC, r.season_id DESC`
  )
    .bind(team_id)
    .all();

  const pointsRes = await DB.prepare(
    `SELECT
       rg.season_id,
       tcp.component_id,
       sc.name AS component_name,
       sc.component_type,
       SUM(tcp.points) AS points
     FROM registrations rg
     JOIN team_component_points tcp ON tcp.registration_id = rg.registration_id
     LEFT JOIN score_components sc ON sc.component_id = tcp.component_id
     WHERE rg.team_id = ?
     GROUP BY rg.season_id, tcp.component_id, sc.name, sc.component_type
     ORDER BY rg.season_id DESC, points DESC, tcp.component_id ASC`
  )
    .bind(team_id)
    .all();

  return json({
    ok: true,
    team,
    aliases: aliasesRes?.results ?? [],
    roster: rosterRes?.results ?? [],
    registrations: registrationsRes?.results ?? [],
    points: (pointsRes?.results ?? []).map((x) => ({
      ...x,
      points: Number(x.points ?? 0),
    })),
  });
}

async function playerBundle(url, DB) {
  const player_id = qParam(url, "player_id");
  const q = qParam(url, "q");

  let player = null;
  if (player_id) {
    player = await firstRow(
      await DB.prepare(
        `SELECT player_id, nickname, display_name, real_name, birth_year, is_active, notes, club_name, joined_at
         FROM players
         WHERE player_id = ?`
      )
        .bind(player_id)
        .all()
    );
  } else if (q) {
    // Search by nickname / real_name / display_name, but return the best match
    const res = await DB.prepare(
      `SELECT player_id, nickname, display_name, real_name, birth_year, is_active, notes, club_name, joined_at
       FROM players
       WHERE player_id = ?
          OR nickname LIKE ?
          OR real_name LIKE ?
          OR display_name LIKE ?
       ORDER BY (player_id = ?) DESC, nickname ASC
       LIMIT 1`
    )
      .bind(q, `%${q}%`, `%${q}%`, `%${q}%`, q)
      .all();
    player = res?.results?.[0] ?? null;
  }

  if (!player) return json({ ok: false, error: "Player not found", player_id, q }, 404);

  const rostersRes = await DB.prepare(
    `SELECT
       r.season_id,
       r.team_id,
       t.canonical_name AS team_name
     FROM rosters r
     JOIN teams t ON t.team_id = r.team_id
     WHERE r.player_id = ?
     ORDER BY r.season_id DESC, r.team_id ASC`
  )
    .bind(player.player_id)
    .all();

  // Seasons the player appeared in (via rosters)
  const seasonsRes = await DB.prepare(
    `SELECT DISTINCT
       r.season_id,
       s.event_id,
       s.name AS season_name,
       s.year,
       s.status
     FROM rosters r
     JOIN seasons s ON s.season_id = r.season_id
     WHERE r.player_id = ?
     ORDER BY s.year DESC, r.season_id DESC`
  )
    .bind(player.player_id)
    .all();

  return json({
    ok: true,
    player,
    rosters: rostersRes?.results ?? [],
    seasons: seasonsRes?.results ?? [],
  });
}
