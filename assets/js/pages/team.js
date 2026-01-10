// assets/js/pages/team.js
(async () => {
  const $ = (id) => document.getElementById(id);

  const seasonSelect = $("seasonSelect");
  const teamSelect = $("teamSelect");
  const msg = $("msg");
  const statusPill = $("statusPill");
  const statusText = $("statusText");

  const rosterBody = $("rosterBody");
  const pointsBody = $("pointsBody");

  function setStatus(kind, text) {
    statusPill.dataset.kind = kind;
    statusText.textContent = text;
  }
  function setMsg(t) { msg.textContent = t || ""; }

  function option(label, value) {
    const o = document.createElement("option");
    o.value = value;
    o.textContent = label;
    return o;
  }

  function getQS(name) {
    const u = new URL(location.href);
    return u.searchParams.get(name);
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[c]));
  }

  async function loadSeasons() {
    const data = await API.apiGet("/api/public/seasons", { timeoutMs: 12000, retry: 1 });
    const seasons = data?.seasons || [];
    const current = data?.current_season_id || seasons[0]?.season_id || "";

    seasonSelect.innerHTML = "";
    for (const s of seasons) {
      const label = `${s.name || s.season_id} · ${s.start_date || ""}${s.status ? ` · ${s.status}` : ""}`.replace(/\s+/g, " ").trim();
      seasonSelect.appendChild(option(label, s.season_id));
    }

    seasonSelect.value = getQS("season_id") || current || seasonSelect.value;
    return seasonSelect.value;
  }

  async function loadTeams(season_id) {
    const data = await API.apiGet(`/api/public/teams?season_id=${encodeURIComponent(season_id)}`, { timeoutMs: 12000, retry: 1 });
    const teams = data?.teams || [];

    teamSelect.innerHTML = "";
    for (const t of teams) {
      teamSelect.appendChild(option(t.team_name || t.team_id, t.team_id));
    }

    teamSelect.value = getQS("team_id") || teams[0]?.team_id || teamSelect.value;
    return teamSelect.value;
  }

  function renderRoster(rows) {
    rosterBody.innerHTML = "";
    for (const r of rows) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td class="strong">${escapeHtml(r.player_name ?? "")}</td>
        <td class="muted">${escapeHtml(r.alias ?? "")}</td>
      `;
      rosterBody.appendChild(tr);
    }
  }

  function renderPoints(rows) {
    pointsBody.innerHTML = "";
    for (const r of rows) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td class="muted mono">${escapeHtml(r.leaderboard_key ?? "")}</td>
        <td class="strong">${escapeHtml(r.component_name ?? "")}</td>
        <td class="mono">${escapeHtml(r.points ?? "")}</td>
        <td class="muted mono">${escapeHtml(r.created_at ?? "")}</td>
      `;
      pointsBody.appendChild(tr);
    }
  }

  async function reloadAll() {
    setStatus("loading", "Loading...");
    setMsg("");
    try {
      const season_id = await loadSeasons();
      const team_id = await loadTeams(season_id);

      const roster = await API.apiGet(
        `/api/public/roster?season_id=${encodeURIComponent(season_id)}&team_id=${encodeURIComponent(team_id)}`,
        { timeoutMs: 12000, retry: 1 }
      );
      renderRoster(roster?.rows || []);

      const points = await API.apiGet(
        `/api/public/team_points?season_id=${encodeURIComponent(season_id)}&team_id=${encodeURIComponent(team_id)}`,
        { timeoutMs: 12000, retry: 1 }
      );
      renderPoints(points?.rows || []);

      setStatus("ok", "OK");
    } catch (e) {
      setStatus("error", "ERROR");
      setMsg(String(e?.message || e));
    }
  }

  seasonSelect.addEventListener("change", reloadAll);
  teamSelect.addEventListener("change", reloadAll);
  $("btnBack").addEventListener("click", () => location.href = "/campaigns");
  $("btnRefresh").addEventListener("click", reloadAll);

  await reloadAll();
})();
