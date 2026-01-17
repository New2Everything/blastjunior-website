const KEY = "blast_bundle_store_v1";

function load() {
  try {
    return JSON.parse(localStorage.getItem(KEY) || "{}") || {};
  } catch {
    return {};
  }
}

function save(obj) {
  localStorage.setItem(KEY, JSON.stringify(obj));
}

export function upsertTeams(teams = []) {
  const st = load();
  st.teams = st.teams || {};
  for (const t of teams) {
    if (!t?.team_id) continue;
    st.teams[t.team_id] = {
      team_id: t.team_id,
      team_name: t.team_name || t.name || st.teams[t.team_id]?.team_name || t.team_id
    };
  }
  save(st);
}

export function upsertPlayers(players = []) {
  const st = load();
  st.players = st.players || {};
  for (const p of players) {
    if (!p?.player_id) continue;
    st.players[p.player_id] = {
      player_id: p.player_id,
      nickname: p.nickname || p.display_name || st.players[p.player_id]?.nickname || p.player_id,
      name: p.name || st.players[p.player_id]?.name || ""
    };
  }
  save(st);
}

export function listTeams() {
  const st = load();
  const arr = Object.values(st.teams || {});
  arr.sort((a, b) => (a.team_name || "").localeCompare(b.team_name || "", "zh"));
  return arr;
}

export function listPlayers() {
  const st = load();
  const arr = Object.values(st.players || {});
  arr.sort((a, b) => (a.nickname || "").localeCompare(b.nickname || "", "zh"));
  return arr;
}
