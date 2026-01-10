import { api } from "../api.js";
import { qs } from "../utils.js";
import { escapeHtml } from "../utils.js";
import { openDrawer, closeDrawer } from "../ui.js";

const qInput = qs("#q");
const tbody = qs("#tbody");
const subtitle = qs("#subtitle");
const countPill = qs("#countPill");
const metaPill = qs("#metaPill");
const statusPill = qs("#statusPill");

const drawer = qs("#playerDrawer");
const closeBtn = qs("#closeDrawer");
const dTitle = qs("#dTitle");
const dSub = qs("#dSub");
const drawerBody = qs("#drawerBody");

closeBtn.addEventListener("click", () => closeDrawer(drawer));

let allPlayers = [];

function norm(s) {
  return String(s ?? "").trim().toLowerCase();
}

function matchPlayer(p, q) {
  if (!q) return true;
  const hay = [
    p.player_id,
    p.nickname,
    p.display_name,
    p.real_name,
    p.club_name,
  ].map(norm).join(" | ");
  return hay.includes(q);
}

function renderList(players) {
  tbody.innerHTML = players.map(p => `
    <tr data-player-id="${escapeHtml(p.player_id)}">
      <td>${escapeHtml(p.nickname || "")}</td>
      <td>${escapeHtml(p.display_name || "")}</td>
      <td>${escapeHtml(p.real_name || "")}</td>
      <td class="col-points">${escapeHtml(p.player_id)}</td>
    </tr>
  `).join("");

  tbody.querySelectorAll("tr").forEach(tr => {
    tr.addEventListener("click", async () => {
      const playerId = tr.getAttribute("data-player-id");
      await openPlayer(playerId);
    });
  });
}

async function openPlayer(playerId) {
  openDrawer(drawer);
  drawerBody.textContent = "加载中…";
  statusPill.textContent = "Loading player…";

  const data = await api.player(playerId);
  const p = data.player;

  dTitle.textContent = p.nickname || p.display_name || p.player_id;
  dSub.textContent = `player_id = ${p.player_id}`;

  const profile = `
    <div class="kv">
      <div class="k">Nickname</div><div>${escapeHtml(p.nickname || "")}</div>
      <div class="k">Display</div><div>${escapeHtml(p.display_name || "")}</div>
      <div class="k">Real name</div><div>${escapeHtml(p.real_name || "")}</div>
      <div class="k">Gender</div><div>${escapeHtml(p.gender || "")}</div>
      <div class="k">Birth year</div><div>${escapeHtml(p.birth_year || "")}</div>
      <div class="k">Club</div><div>${escapeHtml(p.club_name || "")}</div>
      <div class="k">Active</div><div>${escapeHtml(String(p.is_active ?? ""))}</div>
    </div>
  `;

  const rosters = (data.rosters || []);
  const rosterHtml = rosters.length
    ? `
      <table class="table">
        <thead>
          <tr>
            <th>Season</th>
            <th>Team</th>
            <th>Role</th>
          </tr>
        </thead>
        <tbody>
          ${rosters.map(r => `
            <tr>
              <td>${escapeHtml(r.season_id || "")}</td>
              <td>
                <a href="./team.html?team_id=${encodeURIComponent(r.team_id)}&season_id=${encodeURIComponent(r.season_id || "")}">
                  ${escapeHtml(r.team_name || r.team_id)}
                </a>
              </td>
              <td>${escapeHtml(r.role || "")}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `
    : `<div class="pill">暂无 rosters 记录</div>`;

  drawerBody.innerHTML = `
    <div class="pill">Profile</div>
    <div style="margin-top:10px;">${profile}</div>
    <hr/>
    <div class="pill">Rosters (历史参赛轨迹)</div>
    <div style="margin-top:10px;">${rosterHtml}</div>
  `;

  statusPill.textContent = "OK";
}

function applyFilter() {
  const q = norm(qInput.value);
  const filtered = allPlayers.filter(p => matchPlayer(p, q));
  renderList(filtered);
  countPill.textContent = `${filtered.length} / ${allPlayers.length}`;
}

async function init() {
  statusPill.textContent = "Loading…";
  subtitle.textContent = "从 /api/public/players 拉取中…";

  const data = await api.players();
  allPlayers = data.players || [];

  metaPill.textContent = `Total: ${allPlayers.length}`;
  subtitle.textContent = "输入关键词筛选，点击行查看详情";
  qInput.addEventListener("input", applyFilter);

  applyFilter();
  statusPill.textContent = "OK";
}

init().catch(err => {
  statusPill.textContent = "ERROR";
  subtitle.textContent = err.message;
  console.error(err);
});
