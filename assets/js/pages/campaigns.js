import { api } from "../api.js";
import { qs } from "../utils.js";
import { renderSeasonOptions, renderLeaderboardOptions, renderTable, openDrawer, closeDrawer } from "../ui.js";
import { escapeHtml } from "../utils.js";

const seasonSelect = qs("#seasonSelect");
const lbSelect = qs("#lbSelect");
const tableBody = qs("#tableBody");
const subtitle = qs("#subtitle");
const metaPill = qs("#metaPill");
const statusPill = qs("#statusPill");

const drawer = qs("#teamDrawer");
const closeBtn = qs("#closeDrawer");
const dTeamName = qs("#dTeamName");
const dTeamSub = qs("#dTeamSub");
const drawerBody = qs("#drawerBody");

closeBtn.addEventListener("click", () => closeDrawer(drawer));

let seasonsData = null;
let currentSeasonId = null;
let currentLbKey = null;

async function init() {
  statusPill.textContent = "Loading…";

  seasonsData = await api.seasons();
  currentSeasonId = seasonsData.current_season_id || seasonsData.seasons?.[0]?.season_id;

  renderSeasonOptions(seasonSelect, seasonsData.seasons, currentSeasonId);
  seasonSelect.addEventListener("change", async () => {
    currentSeasonId = seasonSelect.value;
    await loadLeaderboardsAndBoard();
  });

  await loadLeaderboardsAndBoard();
  statusPill.textContent = "OK";
}

async function loadLeaderboardsAndBoard() {
  subtitle.textContent = `season_id = ${currentSeasonId}`;
  const lbs = await api.leaderboards(currentSeasonId);
  currentLbKey = lbs.leaderboards?.[0]?.leaderboard_key || null;

  renderLeaderboardOptions(lbSelect, lbs.leaderboards || [], currentLbKey);
  lbSelect.addEventListener("change", async () => {
    currentLbKey = lbSelect.value;
    await loadBoard();
  }, { once: true });

  await loadBoard();
}

async function loadBoard() {
  statusPill.textContent = "Loading board…";
  const data = await api.leaderboard(currentSeasonId, currentLbKey);
  metaPill.textContent = `${data.rows?.length ?? 0} teams`;
  renderTable(tableBody, data.rows || []);

  // row click → drawer
  tableBody.querySelectorAll("tr").forEach(tr => {
    tr.addEventListener("click", async () => {
      const teamId = tr.getAttribute("data-team-id");
      await openTeam(teamId);
    });
  });

  statusPill.textContent = "OK";
}

async function openTeam(teamId) {
  openDrawer(drawer);
  drawerBody.textContent = "加载中…";
  const data = await api.team(teamId, currentSeasonId);

  dTeamName.textContent = data.team?.canonical_name || data.team?.name || teamId;
  dTeamSub.textContent = `team_id = ${teamId} · season = ${currentSeasonId}`;

  const roster = (data.roster || []).map(x => `<div>${escapeHtml(x.nickname || x.display_name || x.player_id)}${x.role ? ` <span class="pill">${escapeHtml(x.role)}</span>` : ""}</div>`).join("") || "<div class='pill'>暂无</div>";
  const totals = (data.season_totals || []).map(x => `<div>${escapeHtml(x.season_id)}：<b>${Number(x.points || 0)}</b></div>`).join("") || "<div class='pill'>暂无</div>";
  const comps = (data.component_points || []).slice(0, 20).map(x => `<div>${escapeHtml(x.name || x.component_id)}：<b>${Number(x.points || 0)}</b> <span class="pill">${escapeHtml(x.leaderboard_key || "")}</span></div>`).join("") || "<div class='pill'>暂无</div>";

  drawerBody.innerHTML = `
    <div class="kv">
      <div class="k">Roster</div><div></div>
    </div>
    ${roster}
    <hr/>
    <div class="kv">
      <div class="k">Season totals</div><div></div>
    </div>
    ${totals}
    <hr/>
    <div class="kv">
      <div class="k">Component points (top 20)</div><div></div>
    </div>
    ${comps}
    <hr/>
    <a class="btn primary" href="./team.html?team_id=${encodeURIComponent(teamId)}&season_id=${encodeURIComponent(currentSeasonId)}">打开独立队伍页</a>
  `;
}

init().catch(err => {
  statusPill.textContent = "ERROR";
  subtitle.textContent = err.message;
  console.error(err);
});
