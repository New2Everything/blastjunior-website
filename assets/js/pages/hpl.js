import { apiGet } from "../api.js";
import { qs, setStatus, escapeHtml } from "../utils.js";

const app = qs("#app");
const statusEl = qs("#status");

const seasonSelect = qs("#seasonSelect");
const lbSelect = qs("#lbSelect");
const refreshBtn = qs("#refreshBtn");

const subtitle = qs("#subtitle");
const seasonPill = qs("#seasonPill");
const countPill = qs("#countPill");
const tbody = qs("#tbody");

// drawer
const drawerOverlay = qs("#drawerOverlay");
const drawer = qs("#drawer");
const drawerCloseBtn = qs("#drawerCloseBtn");
const drawerTitle = qs("#drawerTitle");
const drawerSub = qs("#drawerSub");
const drawerTbody = qs("#drawerTbody");

function openDrawer() { document.body.classList.add("drawerOpen"); }
function closeDrawer() { document.body.classList.remove("drawerOpen"); }
drawerOverlay.addEventListener("click", closeDrawer);
drawerCloseBtn.addEventListener("click", closeDrawer);

async function loadSeasons() {
  const data = await apiGet("/api/public/seasons");
  const list = data?.seasons || [];
  const current = data?.current_season_id || list?.[0]?.season_id;

  seasonSelect.innerHTML = list.map(s => {
    const label = `${s.name || s.season_id} · ${s.start_date || "—"} · ${s.status || "—"}`;
    return `<option value="${escapeHtml(s.season_id)}">${escapeHtml(label)}</option>`;
  }).join("");

  if (current) seasonSelect.value = current;
  return current;
}

async function loadLeaderboards(seasonId) {
  const data = await apiGet(`/api/public/leaderboards?season_id=${encodeURIComponent(seasonId)}`);
  const list = data?.leaderboards || [];
  lbSelect.innerHTML = list.map(lb => {
    const label = `${lb.leaderboard_key} (${lb.components_count ?? "?"})`;
    return `<option value="${escapeHtml(lb.leaderboard_key)}">${escapeHtml(label)}</option>`;
  }).join("");

  if (list[0]?.leaderboard_key) lbSelect.value = list[0].leaderboard_key;
}

function renderRows(rows) {
  tbody.innerHTML = rows.map(r => {
    const teamId = r.team_id || "";
    const teamName = r.team_name || r.team || teamId;
    const rank = r.rank ?? "";
    const pts = r.points ?? r.total_points ?? "";
    return `
      <tr>
        <td class="rank">${escapeHtml(rank)}</td>
        <td class="link">
          <a href="/team?team_id=${encodeURIComponent(teamId)}" data-team-id="${escapeHtml(teamId)}">${escapeHtml(teamName)}</a>
        </td>
        <td class="num">${escapeHtml(pts)}</td>
      </tr>
    `;
  }).join("");

  // click open drawer
  tbody.querySelectorAll("a[data-team-id]").forEach(a => {
    a.addEventListener("click", async (ev) => {
      ev.preventDefault();
      const teamId = a.getAttribute("data-team-id");
      if (!teamId) return;

      try {
        setStatus(statusEl, { ok: true, text: "loading team…" });
        const team = await apiGet(`/api/public/team?team_id=${encodeURIComponent(teamId)}`);
        drawerTitle.textContent = team?.team?.name || team?.team_name || teamId;
        drawerSub.textContent = `team_id = ${teamId}`;

        const roster = team?.roster || team?.players || [];
        drawerTbody.innerHTML = roster.map(p => `
          <tr>
            <td class="link"><a href="/players?player_id=${encodeURIComponent(p.player_id || "")}">${escapeHtml(p.player_name || p.name || p.player_id || "")}</a></td>
            <td>${escapeHtml(p.role || "")}</td>
          </tr>
        `).join("");

        openDrawer();
        setStatus(statusEl, { ok: true, text: "OK" });
      } catch (e) {
        setStatus(statusEl, { ok: false, text: e?.message || String(e) });
      }
    });
  });
}

async function loadLeaderboard() {
  const seasonId = seasonSelect.value;
  const lbKey = lbSelect.value;

  subtitle.textContent = `season_id = ${seasonId}`;
  seasonPill.textContent = `season_id = ${seasonId}`;

  const data = await apiGet(`/api/public/leaderboard?season_id=${encodeURIComponent(seasonId)}&leaderboard_key=${encodeURIComponent(lbKey)}`);
  const rows = data?.rows || data?.leaderboard || [];
  renderRows(rows);
  countPill.textContent = `${rows.length} teams`;
}

async function init() {
  try {
    setStatus(statusEl, { ok: true, text: "loading…" });
    const seasonId = await loadSeasons();
    await loadLeaderboards(seasonId);
    await loadLeaderboard();
    setStatus(statusEl, { ok: true, text: "OK" });
  } catch (e) {
    setStatus(statusEl, { ok: false, text: e?.message || String(e) });
  }
}

seasonSelect.addEventListener("change", async () => {
  try {
    setStatus(statusEl, { ok: true, text: "loading leaderboards…" });
    await loadLeaderboards(seasonSelect.value);
    await loadLeaderboard();
    setStatus(statusEl, { ok: true, text: "OK" });
  } catch (e) {
    setStatus(statusEl, { ok: false, text: e?.message || String(e) });
  }
});
lbSelect.addEventListener("change", async () => {
  try {
    setStatus(statusEl, { ok: true, text: "loading leaderboard…" });
    await loadLeaderboard();
    setStatus(statusEl, { ok: true, text: "OK" });
  } catch (e) {
    setStatus(statusEl, { ok: false, text: e?.message || String(e) });
  }
});
refreshBtn.addEventListener("click", init);

init();
