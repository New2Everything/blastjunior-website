import { escapeHtml } from "./utils.js";

export function renderSeasonOptions(selectEl, seasons, currentSeasonId) {
  selectEl.innerHTML = seasons
    .map(s => {
      const label = `${s.name ?? s.season_id}${s.start_date ? " · " + s.start_date : ""}${s.status ? " · " + s.status : ""}`;
      const selected = s.season_id === currentSeasonId ? "selected" : "";
      return `<option value="${escapeHtml(s.season_id)}" ${selected}>${escapeHtml(label)}</option>`;
    })
    .join("");
}

export function renderLeaderboardOptions(selectEl, leaderboards, currentKey) {
  selectEl.innerHTML = leaderboards
    .map(l => {
      const key = l.leaderboard_key;
      const label = `${key} (${l.component_count})`;
      const selected = key === currentKey ? "selected" : "";
      return `<option value="${escapeHtml(key)}" ${selected}>${escapeHtml(label)}</option>`;
    })
    .join("");
}

export function renderTable(tbodyEl, rows) {
  tbodyEl.innerHTML = rows.map(r => `
    <tr data-team-id="${escapeHtml(r.team_id)}">
      <td class="col-rank">${r.rank ?? ""}</td>
      <td class="col-team">${escapeHtml(r.team_name ?? "")}</td>
      <td class="col-points">${Number(r.points ?? 0)}</td>
    </tr>
  `).join("");
}

export function openDrawer(drawerEl) {
  drawerEl.classList.add("open");
}
export function closeDrawer(drawerEl) {
  drawerEl.classList.remove("open");
}
