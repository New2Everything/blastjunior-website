import { getBundle } from "../api.js";
import { qs, clearSearch, renderCrumb, tile, emptyBlock } from "../common.js";
import { listPlayers } from "../store.js";

const content = document.getElementById("content");
const crumbEl = document.getElementById("crumb");
const search = document.getElementById("search");

function renderPlayerGrid(filterText = "") {
  const all = listPlayers();
  const f = String(filterText || "").trim().toLowerCase();
  const players = f
    ? all.filter(p => (p.player_id || "").toLowerCase().includes(f) || (p.nickname || "").toLowerCase().includes(f))
    : all;

  renderCrumb(crumbEl, [{ label: "Players" }]);
  content.innerHTML = "";
  if (!players.length) {
    content.appendChild(emptyBlock("暂无队员"));
    return;
  }
  const grid = document.createElement("div");
  grid.className = "grid";
  for (const p of players) {
    const card = tile({ title: p.nickname || p.player_id, subtitle: p.player_id, badge: "Player" });
    card.addEventListener("click", () => {
      location.href = `/players/?player_id=${encodeURIComponent(p.player_id)}`;
    });
    grid.appendChild(card);
  }
  content.appendChild(grid);
}

async function renderPlayerDetail(player_id) {
  const data = await getBundle("player_bundle", { player_id });
  const nick = data.player?.nickname || data.player?.name || player_id;

  renderCrumb(crumbEl, [
    { label: "Players", href: "/players/", onClick: () => { clearSearch(["player_id"]); boot(); } },
    { label: nick }
  ]);

  content.innerHTML = "";

  const profile = document.createElement("div");
  profile.className = "panel";
  profile.innerHTML = `
    <div class="panel-hd"><div class="h">${escape(nick)}</div></div>
    <div class="panel-bd">
      <div class="cards-row">
        <div class="stat"><div class="k">Age</div><div class="v" style="font-size:14px;">-</div></div>
        <div class="stat"><div class="k">Teams</div><div class="v">${data.summary?.teams_played ?? 0}</div></div>
        <div class="stat"><div class="k">Best Rank</div><div class="v" style="font-size:14px;">-</div></div>
      </div>
    </div>
  `;

  const teamsPanel = document.createElement("div");
  teamsPanel.className = "panel";
  teamsPanel.innerHTML = `
    <div class="panel-hd"><div class="h">Teams Joined</div></div>
    <div class="panel-bd" id="teamGrid"></div>
  `;
  const tg = teamsPanel.querySelector("#teamGrid");
  const grid = document.createElement("div");
  grid.className = "grid";
  grid.style.gridTemplateColumns = "repeat(4,1fr)";
  const seen = new Set();
  (data.rosters || []).forEach(r => {
    if (!r.team_id || seen.has(r.team_id)) return;
    seen.add(r.team_id);
    const card = tile({ title: r.team_name || r.team_id, subtitle: r.team_id, badge: "Team" });
    card.addEventListener("click", () => {
      location.href = `/team/?team_id=${encodeURIComponent(r.team_id)}`;
    });
    grid.appendChild(card);
  });
  tg.appendChild(grid);

  const leaguesPanel = document.createElement("div");
  leaguesPanel.className = "panel";
  leaguesPanel.innerHTML = `
    <div class="panel-hd"><div class="h">League Results</div></div>
    <div class="panel-bd"><div class="empty">-</div></div>
  `;

  const stack = document.createElement("div");
  stack.style.display = "grid";
  stack.style.gap = "14px";
  stack.appendChild(profile);
  stack.appendChild(teamsPanel);
  stack.appendChild(leaguesPanel);
  content.appendChild(stack);
}

function escape(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

async function boot() {
  const player_id = qs("player_id");
  try {
    if (!player_id) {
      renderPlayerGrid(search?.value || "");
      return;
    }
    await renderPlayerDetail(player_id);
  } catch {
    content.innerHTML = "";
    content.appendChild(emptyBlock("加载失败"));
  }
}

if (search) {
  search.addEventListener("input", () => {
    if (qs("player_id")) return;
    renderPlayerGrid(search.value);
  });
  search.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      if (!qs("player_id")) renderPlayerGrid(search.value);
    }
  });
}

boot();
window.addEventListener("popstate", () => boot());