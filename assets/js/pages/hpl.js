import { api } from "../api.js";
import { qs } from "../utils.js";
import { renderSeasonOptions, renderLeaderboardOptions, renderTable, openDrawer, closeDrawer } from "../ui.js";
import { escapeHtml, fmtDate } from "../utils.js";

const seasonSelect = qs("#seasonSelect");
const lbSelect = qs("#lbSelect");
const refreshBtn = qs("#refreshBtn");
const subtitle = qs("#subtitle");
const metaPill = qs("#metaPill");
const roundMeta = qs("#roundMeta");
const statusPill = qs("#statusPill");

const tableBody = qs("#tableBody");
const roundBody = qs("#roundBody");

const teamDrawer = qs("#teamDrawer");
const closeTeamDrawer = qs("#closeTeamDrawer");
const teamDrawerBody = qs("#teamDrawerBody");
const dTeamName = qs("#dTeamName");
const dTeamSub = qs("#dTeamSub");
closeTeamDrawer.addEventListener("click", () => closeDrawer(teamDrawer));

const roundDrawer = qs("#roundDrawer");
const closeRoundDrawer = qs("#closeRoundDrawer");
const roundDrawerBody = qs("#roundDrawerBody");
const dRoundName = qs("#dRoundName");
const dRoundSub = qs("#dRoundSub");
closeRoundDrawer.addEventListener("click", () => closeDrawer(roundDrawer));

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
    await loadLeaderboards();
    await refreshAll();
  });

  refreshBtn.addEventListener("click", () => refreshAll());

  await loadLeaderboards();
  await refreshAll();
  statusPill.textContent = "OK";
}

async function loadLeaderboards() {
  subtitle.textContent = `season_id = ${currentSeasonId}`;
  const lbs = await api.leaderboards(currentSeasonId);
  currentLbKey = lbs.leaderboards?.[0]?.leaderboard_key || null;
  renderLeaderboardOptions(lbSelect, lbs.leaderboards || [], currentLbKey);

  lbSelect.addEventListener("change", async () => {
    currentLbKey = lbSelect.value;
    await refreshAll();
  }, { once: true });
}

async function refreshAll() {
  statusPill.textContent = "Loading…";
  await loadBoard();
  await loadRounds();
  statusPill.textContent = "OK";
}

async function loadBoard() {
  const data = await api.leaderboard(currentSeasonId, currentLbKey);
  metaPill.textContent = `${data.rows?.length ?? 0} teams`;
  renderTable(tableBody, data.rows || []);

  tableBody.querySelectorAll("tr").forEach(tr => {
    tr.addEventListener("click", async () => {
      const teamId = tr.getAttribute("data-team-id");
      await openTeam(teamId);
    });
  });
}

async function openTeam(teamId) {
  openDrawer(teamDrawer);
  teamDrawerBody.textContent = "加载中…";
  const data = await api.team(teamId, currentSeasonId);

  dTeamName.textContent = data.team?.canonical_name || data.team?.name || teamId;
  dTeamSub.textContent = `team_id = ${teamId} · season = ${currentSeasonId}`;

  const roster = (data.roster || []).map(x => `<div>${escapeHtml(x.nickname || x.display_name || x.player_id)}${x.role ? ` <span class="pill">${escapeHtml(x.role)}</span>` : ""}</div>`).join("") || "<div class='pill'>暂无</div>";
  const comps = (data.component_points || []).filter(x => x.leaderboard_key === currentLbKey).map(x => `<div>${escapeHtml(x.name || x.component_id)}：<b>${Number(x.points || 0)}</b></div>`).join("") || "<div class='pill'>暂无</div>";

  teamDrawerBody.innerHTML = `
    <div class="kv"><div class="k">Roster</div><div></div></div>
    ${roster}
    <hr/>
    <div class="kv"><div class="k">This leaderboard breakdown</div><div></div></div>
    ${comps}
    <hr/>
    <a class="btn primary" href="./team.html?team_id=${encodeURIComponent(teamId)}&season_id=${encodeURIComponent(currentSeasonId)}">打开独立队伍页</a>
  `;
}

async function loadRounds() {
  const data = await api.rounds(currentSeasonId, currentLbKey);
  roundMeta.textContent = `${data.rounds?.length ?? 0} rounds`;

  roundBody.innerHTML = (data.rounds || []).map(r => `
    <tr data-component-id="${escapeHtml(r.component_id)}">
      <td>${escapeHtml(r.name || r.component_id)}</td>
      <td>${escapeHtml(fmtDate(r.start_date || r.end_date || ""))}</td>
      <td><span class="pill">${escapeHtml(r.component_type || "")}</span></td>
      <td class="col-points"><button class="btn">查看</button></td>
    </tr>
  `).join("");

  roundBody.querySelectorAll("tr").forEach(tr => {
    tr.addEventListener("click", async () => {
      const componentId = tr.getAttribute("data-component-id");
      await openRound(componentId);
    });
  });
}

async function openRound(componentId) {
  openDrawer(roundDrawer);
  roundDrawerBody.textContent = "加载中…";

  const data = await api.round(componentId);
  dRoundName.textContent = data.component?.name || componentId;
  dRoundSub.textContent = `component_id = ${componentId}`;

  const rows = data.rows || [];
  const html = `
    <table class="table">
      <thead><tr><th class="col-rank">Rank</th><th>Team</th><th class="col-points">Points</th></tr></thead>
      <tbody>
        ${rows.map(r => `
          <tr data-team-id="${escapeHtml(r.team_id)}">
            <td class="col-rank">${r.rank ?? ""}</td>
            <td>${escapeHtml(r.team_name || "")}</td>
            <td class="col-points">${Number(r.points || 0)}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;

  roundDrawerBody.innerHTML = html;

  // click team inside round → open team drawer
  roundDrawerBody.querySelectorAll("tbody tr").forEach(tr => {
    tr.addEventListener("click", async () => {
      const teamId = tr.getAttribute("data-team-id");
      await openTeam(teamId);
    });
  });
}

init().catch(err => {
  statusPill.textContent = "ERROR";
  subtitle.textContent = err.message;
  console.error(err);
});
