import { getBundle } from "../api.js";
import { qs, setSearch, clearSearch, renderCrumb, tile, emptyBlock } from "../common.js";
import { listTeams, upsertPlayers } from "../store.js";

const content = document.getElementById("content");
const crumbEl = document.getElementById("crumb");

function renderTeamGrid() {
  const teams = listTeams();
  renderCrumb(crumbEl, [
    { label: "Teams" }
  ]);

  content.innerHTML = "";
  if (!teams.length) {
    content.appendChild(emptyBlock("暂无队伍"));
    return;
  }
  const grid = document.createElement("div");
  grid.className = "grid";
  for (const t of teams) {
    const card = tile({ title: t.team_name, subtitle: t.team_id, badge: "Team" });
    card.addEventListener("click", () => {
      location.href = `/team/?team_id=${encodeURIComponent(t.team_id)}`;
    });
    grid.appendChild(card);
  }
  content.appendChild(grid);
}

async function renderTeamDetail(team_id) {
  const data = await getBundle("team_bundle", { team_id });

  // Persist players seen in roster so Player page has a list even before dedicated index endpoint exists.
  upsertPlayers((data.roster || []).map(p => ({
    player_id: p.player_id,
    nickname: p.display_name,
    name: p.name
  })));

  const teamName = data.team?.name || data.team?.team_name || team_id;
  const aliases = (data.team?.aliases || []).filter(Boolean);

  renderCrumb(crumbEl, [
    { label: "Teams", href: "/team/", onClick: () => { clearSearch(["team_id"]); boot(); } },
    { label: teamName }
  ]);

  content.innerHTML = "";

  const profile = document.createElement("div");
  profile.className = "panel";
  profile.innerHTML = `
    <div class="panel-hd"><div class="h">${escape(teamName)}</div></div>
    <div class="panel-bd">
      <div class="cards-row" style="grid-template-columns:repeat(3,1fr)">
        <div class="stat"><div class="k">Aliases</div><div class="v" style="font-size:14px;">${aliases.length ? escape(aliases.join(" / ")) : "-"}</div></div>
        <div class="stat"><div class="k">Total Points</div><div class="v">${data.summary?.points_total ?? 0}</div></div>
        <div class="stat"><div class="k">Players</div><div class="v">${(data.roster||[]).length}</div></div>
      </div>
      <div style="margin-top:12px;" class="cards-row">
        <div class="stat"><div class="k">Club</div><div class="v" style="font-size:14px;">-</div></div>
        <div class="stat"><div class="k">First Seen</div><div class="v" style="font-size:14px;">-</div></div>
        <div class="stat"><div class="k">Best Rank</div><div class="v" style="font-size:14px;">-</div></div>
      </div>
    </div>
  `;

  const rosterPanel = document.createElement("div");
  rosterPanel.className = "panel";
  rosterPanel.innerHTML = `
    <div class="panel-hd"><div class="h">Roster</div></div>
    <div class="panel-bd" id="rosterGrid"></div>
  `;
  const rosterGrid = rosterPanel.querySelector("#rosterGrid");
  const rg = document.createElement("div");
  rg.className = "grid";
  rg.style.gridTemplateColumns = "repeat(4,1fr)";
  (data.roster || []).forEach(p => {
    const card = tile({ title: p.display_name || p.player_id, subtitle: p.player_id, badge: "Player" });
    card.addEventListener("click", () => {
      location.href = `/players/?player_id=${encodeURIComponent(p.player_id)}`;
    });
    rg.appendChild(card);
  });
  rosterGrid.appendChild(rg);

  const resultsPanel = document.createElement("div");
  resultsPanel.className = "panel";
  resultsPanel.innerHTML = `
    <div class="panel-hd"><div class="h">League Results</div></div>
    <div class="panel-bd"><div class="empty">-</div></div>
  `;

  const componentsPanel = document.createElement("div");
  componentsPanel.className = "panel";
  componentsPanel.innerHTML = `
    <div class="panel-hd"><div class="h">Components</div></div>
    <div class="panel-bd">
      <div class="table-card">
        <table>
          <thead><tr><th>component_id</th><th class="right">points</th></tr></thead>
          <tbody id="cpBody"></tbody>
        </table>
      </div>
    </div>
  `;
  const cpBody = componentsPanel.querySelector("#cpBody");
  const comps = data.components || [];
  cpBody.innerHTML = comps.map(c => `
    <tr><td>${escape(c.component_id)}</td><td class="right">${Number(c.points||0)}</td></tr>
  `).join("");

  const stack = document.createElement("div");
  stack.style.display = "grid";
  stack.style.gap = "14px";
  stack.appendChild(profile);
  stack.appendChild(rosterPanel);
  stack.appendChild(resultsPanel);
  stack.appendChild(componentsPanel);
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
  const team_id = qs("team_id");
  try {
    if (!team_id) {
      renderTeamGrid();
      return;
    }
    await renderTeamDetail(team_id);
  } catch {
    content.innerHTML = "";
    content.appendChild(emptyBlock("加载失败"));
  }
}

boot();
window.addEventListener("popstate", () => boot());
