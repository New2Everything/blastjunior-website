import { api } from "../api.js";
import { qs, getParam } from "../utils.js";
import { renderSeasonOptions } from "../ui.js";
import { escapeHtml } from "../utils.js";

const teamId = getParam("team_id");
const seasonIdFromUrl = getParam("season_id");

const seasonSelect = qs("#seasonSelect");
const teamTitle = qs("#teamTitle");
const teamSub = qs("#teamSub");
const statusPill = qs("#statusPill");

const overviewEl = qs("#overview");
const rosterEl = qs("#roster");
const breakdownEl = qs("#breakdown");
const historyEl = qs("#history");

let seasonsData = null;
let currentSeasonId = null;

async function init() {
  if (!teamId) {
    teamTitle.textContent = "缺少 team_id";
    return;
  }

  statusPill.textContent = "Loading…";

  seasonsData = await api.seasons();
  currentSeasonId = seasonIdFromUrl || seasonsData.current_season_id || seasonsData.seasons?.[0]?.season_id;

  renderSeasonOptions(seasonSelect, seasonsData.seasons, currentSeasonId);
  seasonSelect.addEventListener("change", async () => {
    currentSeasonId = seasonSelect.value;
    await loadTeam();
  });

  await loadTeam();
  statusPill.textContent = "OK";
}

async function loadTeam() {
  statusPill.textContent = "Loading team…";
  const data = await api.team(teamId, currentSeasonId);

  const name = data.team?.canonical_name || data.team?.name || teamId;
  teamTitle.textContent = name;
  teamSub.textContent = `team_id = ${teamId} · season = ${currentSeasonId}`;

  // overview: registrations + season points
  const regs = (data.registrations || []).filter(r => !currentSeasonId || r.season_id === currentSeasonId);
  const seasonTotal = (data.season_totals || []).find(x => x.season_id === currentSeasonId);

  overviewEl.innerHTML = `
    <div class="kv">
      <div class="k">Season points</div><div><b>${Number(seasonTotal?.points || 0)}</b></div>
      <div class="k">Registrations</div><div>${escapeHtml(String(regs.length))}</div>
    </div>
    ${regs.length ? `<hr/>` : ""}
    ${regs.map(r => `<div class="pill">${escapeHtml(r.season_id)} · ${escapeHtml(r.status || "active")}</div>`).join(" ")}
  `;

  // roster
  const roster = (data.roster || []).filter(x => x.season_id === currentSeasonId);
  rosterEl.innerHTML = roster.length
    ? roster.map(x => `<div>${escapeHtml(x.nickname || x.display_name || x.player_id)}${x.role ? ` <span class="pill">${escapeHtml(x.role)}</span>` : ""}</div>`).join("")
    : `<div class="pill">暂无队员记录</div>`;

  // breakdown
  const comps = (data.component_points || []).filter(x => x.season_id === currentSeasonId);
  breakdownEl.innerHTML = comps.length
    ? comps.map(x => `<div>${escapeHtml(x.name || x.component_id)}：<b>${Number(x.points || 0)}</b> <span class="pill">${escapeHtml(x.leaderboard_key || "")}</span></div>`).join("")
    : `<div class="pill">暂无得分构成</div>`;

  // history
  const totals = (data.season_totals || []);
  historyEl.innerHTML = totals.length
    ? totals.map(x => `<div>${escapeHtml(x.season_id)}：<b>${Number(x.points || 0)}</b></div>`).join("")
    : `<div class="pill">暂无历史</div>`;

  statusPill.textContent = "OK";
}

init().catch(err => {
  statusPill.textContent = "ERROR";
  teamTitle.textContent = err.message;
  console.error(err);
});
