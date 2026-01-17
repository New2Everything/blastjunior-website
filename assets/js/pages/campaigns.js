import { getBundle } from "../api.js";
import { qs, setSearch, clearSearch, renderCrumb, tile, emptyBlock } from "../common.js";
import { upsertTeams } from "../store.js";

const content = document.getElementById("content");
const crumbEl = document.getElementById("crumb");

function normalizeContext(ctx, selectors) {
  // First entry default: if no event_id in URL, default to hpl (but keep full events list)
  const event_id = ctx.event_id || qs("event_id") || "hpl";
  const season_id = ctx.season_id || qs("season_id") || selectors.seasons?.[0]?.season_id || "";
  const division_key = ctx.division_key || qs("division_key") || selectors.divisions?.[0]?.division_key || "";
  const round_key = ctx.round_key || qs("round_key") || selectors.rounds?.slice(-1)[0]?.round_key || selectors.rounds?.slice(-1)[0]?.component_id || "";
  return { event_id, season_id, division_key, round_key };
}

function nameBy(list, idKey, idVal, nameKey = "name") {
  const f = (list || []).find(x => String(x?.[idKey]) === String(idVal));
  return f?.[nameKey] || idVal || "";
}

function isLeaderboardView(p) {
  return !!(p.event_id && p.season_id && p.division_key && p.round_key);
}

function state(p) {
  if (!p.event_id) return "EVENT";
  if (p.event_id && !p.season_id) return "SEASON";
  if (p.season_id && !p.division_key) return "DIVISION";
  if (p.division_key && !p.round_key) return "ROUND";
  return "LEADERBOARD";
}

async function load() {
  // Always call bundle with current params (or default hpl handled server-side as well)
  const params = {
    event_id: qs("event_id") || "",
    season_id: qs("season_id") || "",
    division_key: qs("division_key") || "",
    round_key: qs("round_key") || ""
  };
  const data = await getBundle("campaigns_bundle", params);
  // Persist teams we have seen (helps Team page list without extra endpoints)
  upsertTeams((data.table || []).map(r => ({ team_id: r.team_id, team_name: r.team_name })));
  return data;
}

function render(data) {
  const selectors = data.selectors || {};
  const ctx = normalizeContext(data.context || {}, selectors);

  // Breadcrumb
  const items = [];
  const s = state({
    event_id: qs("event_id"),
    season_id: qs("season_id"),
    division_key: qs("division_key"),
    round_key: qs("round_key")
  });

  items.push({ label: "Events", href: "/campaigns/", onClick: () => { clearSearch(["event_id","season_id","division_key","round_key"]); boot(); } });

  if (qs("event_id")) {
    const evName = nameBy(selectors.events, "event_id", qs("event_id"), "name");
    items.push({ label: evName, href: "#", onClick: () => { clearSearch(["season_id","division_key","round_key"]); boot(); } });
  }
  if (qs("season_id")) {
    const snName = nameBy(selectors.seasons, "season_id", qs("season_id"), "name");
    items.push({ label: snName, href: "#", onClick: () => { clearSearch(["division_key","round_key"]); boot(); } });
  }
  if (qs("division_key")) {
    const dvName = nameBy(selectors.divisions, "division_key", qs("division_key"), "name");
    items.push({ label: dvName, href: "#", onClick: () => { clearSearch(["round_key"]); boot(); } });
  }
  if (qs("round_key")) {
    const rdName = nameBy(selectors.rounds, "round_key", qs("round_key"), "name");
    items.push({ label: rdName });
  }
  renderCrumb(crumbEl, items);

  content.innerHTML = "";

  // Default first entry behavior: first open defaults to HPL (but Events remains accessible via breadcrumb)
  if (!qs("event_id")) {
    setSearch({ event_id: "hpl", season_id: "", division_key: "", round_key: "" }, true);
    boot();
    return;
  }

  if (!qs("season_id")) {
    renderSeasonGrid(selectors, qs("event_id"));
    return;
  }
  if (!qs("division_key")) {
    renderDivisionGrid(selectors, qs("event_id"), qs("season_id"));
    return;
  }
  if (!qs("round_key")) {
    renderRoundGrid(selectors, qs("event_id"), qs("season_id"), qs("division_key"));
    return;
  }
  renderLeaderboard(data);
}

function renderEventGrid(selectors) {
  const events = selectors.events || [];
  if (!events.length) {
    content.appendChild(emptyBlock());
    return;
  }
  const grid = document.createElement("div");
  grid.className = "grid";

  for (const ev of events) {
    const t = tile({ title: ev.name || ev.event_id, subtitle: ev.event_id, badge: "Event" });
    t.addEventListener("click", () => {
      setSearch({ event_id: ev.event_id, season_id: "", division_key: "", round_key: "" }, false);
      boot();
    });
    grid.appendChild(t);
  }
  content.appendChild(grid);
}

function renderSeasonGrid(selectors) {
  const seasons = selectors.seasons || [];
  if (!seasons.length) {
    content.appendChild(emptyBlock());
    return;
  }
  const grid = document.createElement("div");
  grid.className = "grid";
  for (const s of seasons) {
    const t = tile({ title: s.name || s.season_id, subtitle: s.status || "", badge: "Season" });
    t.addEventListener("click", () => {
      setSearch({ season_id: s.season_id, division_key: "", round_key: "" }, false);
      boot();
    });
    grid.appendChild(t);
  }
  content.appendChild(grid);
}

function renderDivisionGrid(selectors) {
  const divisions = selectors.divisions || [];
  if (!divisions.length) {
    content.appendChild(emptyBlock());
    return;
  }
  const grid = document.createElement("div");
  grid.className = "grid";
  for (const d of divisions) {
    const t = tile({ title: d.name || d.division_key, subtitle: d.division_key, badge: "Division" });
    t.addEventListener("click", () => {
      setSearch({ division_key: d.division_key, round_key: "" }, false);
      boot();
    });
    grid.appendChild(t);
  }
  content.appendChild(grid);
}

function renderRoundGrid(selectors) {
  const rounds = selectors.rounds || [];
  if (!rounds.length) {
    content.appendChild(emptyBlock());
    return;
  }
  const grid = document.createElement("div");
  grid.className = "grid";
  for (const r of rounds) {
    const key = r.round_key || r.component_id;
    const t = tile({ title: r.name || key, subtitle: r.type || r.component_type || "", badge: "Round" });
    t.addEventListener("click", () => {
      setSearch({ round_key: key }, false);
      boot();
    });
    grid.appendChild(t);
  }
  content.appendChild(grid);
}

function renderLeaderboard(data) {
  const panel = document.createElement("div");
  panel.className = "panel";
  panel.innerHTML = `
    <div class="panel-hd">
      <div class="h">Leaderboard</div>
    </div>
    <div class="panel-bd">
      <div class="cards-row" style="margin-bottom:12px;">
        <div class="stat"><div class="k">Teams</div><div class="v">${data.overview?.teams_total ?? (data.table||[]).length}</div></div>
        <div class="stat"><div class="k">Total Points</div><div class="v">${(data.table||[]).reduce((s,r)=>s+Number(r.points||0),0)}</div></div>
        <div class="stat"><div class="k">Round</div><div class="v">${data.context?.round_key ?? qs("round_key") ?? ""}</div></div>
      </div>
      <div class="table-card">
        <table>
          <thead>
            <tr>
              <th style="width:72px;">RANK</th>
              <th>TEAM</th>
              <th style="width:120px;" class="right">POINTS</th>
            </tr>
          </thead>
          <tbody id="lbBody"></tbody>
        </table>
      </div>
    </div>
  `;

  const tbody = panel.querySelector("#lbBody");
  const rows = data.table || [];
  tbody.innerHTML = rows.map(r => `
    <tr class="rowlink" data-team-id="${r.team_id}">
      <td>${r.rank}</td>
      <td>${escape(r.team_name)}</td>
      <td class="right">${Number(r.points||0)}</td>
    </tr>
  `).join("");

  tbody.addEventListener("click", (e) => {
    const tr = e.target.closest("tr[data-team-id]");
    if (!tr) return;
    const team_id = tr.getAttribute("data-team-id");
    location.href = `/team/?team_id=${encodeURIComponent(team_id)}`;
  });

  content.appendChild(panel);
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
  try {
    const data = await load();
    render(data);
  } catch {
    content.innerHTML = "";
    content.appendChild(emptyBlock("加载失败"));
  }
}

// First view default (HPL) without locking user: keep event grid but prefetch uses default on server-side.
boot();

window.addEventListener("popstate", () => boot());
