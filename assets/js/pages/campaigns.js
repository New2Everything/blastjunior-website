/* campaigns.js (T=1.61)
   - Event list includes ALL events.
   - Default event: HPL.
   - Clean IA: left = selection, right = display.
*/

import { API, fmt } from "../api.js";

const QS = new URLSearchParams(location.search);
const DEFAULT_EVENT_ID = "hpl";

const el = {
  statusDot: document.getElementById("statusDot"),
  statusText: document.getElementById("statusText"),

  eventSelect: document.getElementById("eventSelect"),
  seasonSelect: document.getElementById("seasonSelect"),
  divisionSelect: document.getElementById("divisionSelect"),
  viewSelect: document.getElementById("viewSelect"),
  roundSelect: document.getElementById("roundSelect"),

  k_event: document.getElementById("k_event"),
  k_season: document.getElementById("k_season"),
  k_division: document.getElementById("k_division"),
  k_defaultRound: document.getElementById("k_defaultRound"),
  k_viewRound: document.getElementById("k_viewRound"),

  primaryTitle: document.getElementById("primaryTitle"),
  secondaryTitle: document.getElementById("secondaryTitle"),

  leaderboardKey: document.getElementById("leaderboardKey"),
  tableBody: document.getElementById("tableBody"),
  emptyHint: document.getElementById("emptyHint"),

  btnRefresh: document.getElementById("btnRefresh"),
};

let state = {
  events: [],
  seasons: [],
  divisions: [],
  rounds: [],
  current: {
    event_id: QS.get("event_id") || DEFAULT_EVENT_ID,
    season_id: QS.get("season_id") || null,
    division_key: QS.get("division_key") || "elite",
    view_mode: QS.get("view") || "total", // total | round
    round_key: QS.get("round_key") || null,
  }
};

function setStatus(ok, text){
  if (el.statusDot) el.statusDot.style.background = ok ? "var(--ok)" : "var(--err)";
  if (el.statusText) el.statusText.textContent = text;
}

function setQS(partial){
  const p = new URLSearchParams(location.search);
  for (const [k,v] of Object.entries(partial)){
    if (v === null || v === undefined || v === "") p.delete(k);
    else p.set(k, String(v));
  }
  history.replaceState({}, "", `${location.pathname}?${p.toString()}`);
}

function optionize(sel, items, getValue, getLabel){
  sel.innerHTML = "";
  for (const it of items){
    const opt = document.createElement("option");
    opt.value = getValue(it);
    opt.textContent = getLabel(it);
    sel.appendChild(opt);
  }
}

function chooseDefaultSeason(seasons){
  const ongoing = seasons.find(s => (s.status||"") === "ongoing");
  if (ongoing) return ongoing.season_id;
  // fallback: latest year then first
  const sorted = [...seasons].sort((a,b) => (b.year||0) - (a.year||0));
  return sorted[0]?.season_id || null;
}

async function loadEvents(){
  state.events = await API.events();
  optionize(el.eventSelect, state.events, e => e.event_id, e => `${e.name_zh || e.event_id}`);
  // ensure default selection exists
  if (!state.events.some(e => e.event_id === state.current.event_id)){
    state.current.event_id = DEFAULT_EVENT_ID;
  }
  el.eventSelect.value = state.current.event_id;
  el.k_event.textContent = (state.events.find(e => e.event_id === state.current.event_id)?.name_zh) || state.current.event_id;
}

async function loadSeasons(){
  state.seasons = await API.seasons(state.current.event_id);
  optionize(el.seasonSelect, state.seasons, s => s.season_id, s => `${s.name || s.season_id}${s.status ? ` (${s.status})` : ""}`);

  if (!state.current.season_id || !state.seasons.some(s => s.season_id === state.current.season_id)){
    state.current.season_id = chooseDefaultSeason(state.seasons);
  }
  el.seasonSelect.value = state.current.season_id || "";

  const season = state.seasons.find(s => s.season_id === state.current.season_id);
  el.k_season.textContent = season ? `${season.name || season.season_id}` : "-";
}

async function loadDivisions(){
  state.divisions = await API.divisions(state.current.season_id);
  optionize(el.divisionSelect, state.divisions, d => d.division_key, d => `${d.name} (${d.division_key})`);

  if (!state.divisions.some(d => d.division_key === state.current.division_key)){
    // prefer elite else first
    state.current.division_key = state.divisions.find(d => d.division_key === "elite")?.division_key || state.divisions[0]?.division_key || "";
  }
  el.divisionSelect.value = state.current.division_key;

  const division = state.divisions.find(d => d.division_key === state.current.division_key);
  el.k_division.textContent = division ? division.name : "-";
}

async function loadRounds(){
  // rounds are score_components with component_type=round/round_group under the base leaderboard key.
  const division = state.divisions.find(d => d.division_key === state.current.division_key);
  if (!division){ state.rounds = []; return; }

  const bundle = await API.roundsBundle(state.current.season_id, division.leaderboard_key);
  state.rounds = bundle.rounds || [];
  optionize(el.roundSelect, state.rounds, r => r.component_id, r => r.name || r.component_id);

  const last = bundle.last_round || null;
  if (!state.current.round_key || !state.rounds.some(r => r.component_id === state.current.round_key)){
    // default: last_round
    state.current.round_key = last;
  }
  if (state.current.round_key) el.roundSelect.value = state.current.round_key;

  el.k_defaultRound.textContent = last ? (state.rounds.find(r => r.component_id === last)?.name || last) : "-";
  el.k_viewRound.textContent = state.current.view_mode === "round"
    ? (state.rounds.find(r => r.component_id === state.current.round_key)?.name || state.current.round_key || "-")
    : "(Total)";
}

function pickLeaderboardKey(){
  const division = state.divisions.find(d => d.division_key === state.current.division_key);
  if (!division) return null;

  // total = division.leaderboard_key, round = round_key (which itself is a leaderboard_key in DB for round_group cases)
  // NOTE: In DB, round_group rows have leaderboard_key like hpl_s2_2025_elite.
  // But our roundSelect uses component_id; we need resolve to leaderboard_key.
  if (state.current.view_mode === "total") return division.leaderboard_key;

  const roundComp = state.rounds.find(r => r.component_id === state.current.round_key);
  return roundComp?.leaderboard_key || null;
}

async function renderLeaderboard(){
  const lb = pickLeaderboardKey();
  el.leaderboardKey.value = lb || "";

  if (!lb){
    el.tableBody.innerHTML = "";
    el.emptyHint.style.display = "block";
    el.primaryTitle.textContent = "Top 20";
    el.secondaryTitle.textContent = "请选择 Event / Season / Division";
    return;
  }

  el.emptyHint.style.display = "none";
  const data = await API.leaderboardBundle(lb, { limit: 20 });
  const rows = data.rows || [];

  el.primaryTitle.textContent = "Top 20";
  // small, non-explanatory summary
  const countText = rows.length ? `${rows.length} teams` : "0 teams";
  el.secondaryTitle.textContent = `${lb} · ${countText}`;

  el.tableBody.innerHTML = "";
  for (const r of rows){
    const tr = document.createElement("tr");

    const tdRank = document.createElement("td");
    tdRank.textContent = String(r.rank || "-");

    const tdTeam = document.createElement("td");
    const a = document.createElement("a");
    a.href = `/team/?team_id=${encodeURIComponent(r.team_id)}`;
    a.textContent = r.team_name || r.team_id;
    tdTeam.appendChild(a);

    const tdPts = document.createElement("td");
    tdPts.style.textAlign = "right";
    tdPts.textContent = fmt.num(r.points);

    tr.appendChild(tdRank);
    tr.appendChild(tdTeam);
    tr.appendChild(tdPts);
    el.tableBody.appendChild(tr);
  }
}

function syncUI(){
  el.viewSelect.value = state.current.view_mode;
  el.roundSelect.disabled = (state.current.view_mode !== "round");
  setQS({
    event_id: state.current.event_id,
    season_id: state.current.season_id,
    division_key: state.current.division_key,
    view: state.current.view_mode,
    round_key: (state.current.view_mode === "round") ? state.current.round_key : null,
  });
}

async function fullReload(){
  try{
    setStatus(true, "Loading");
    await loadEvents();
    await loadSeasons();
    await loadDivisions();
    await loadRounds();
    syncUI();
    await renderLeaderboard();
    setStatus(true, "OK");
  }catch(e){
    console.error(e);
    setStatus(false, "ERROR");
  }
}

function wire(){
  el.eventSelect.addEventListener("change", async () => {
    state.current.event_id = el.eventSelect.value;
    state.current.season_id = null;
    await fullReload();
  });

  el.seasonSelect.addEventListener("change", async () => {
    state.current.season_id = el.seasonSelect.value;
    await fullReload();
  });

  el.divisionSelect.addEventListener("change", async () => {
    state.current.division_key = el.divisionSelect.value;
    await fullReload();
  });

  el.viewSelect.addEventListener("change", async () => {
    state.current.view_mode = el.viewSelect.value;
    await fullReload();
  });

  el.roundSelect.addEventListener("change", async () => {
    state.current.round_key = el.roundSelect.value;
    await fullReload();
  });

  el.btnRefresh.addEventListener("click", () => fullReload());
}

wire();
fullReload();
