// assets/js/pages/hpl.js
(async () => {
  const $ = (id) => document.getElementById(id);

  const seasonSelect = $("seasonSelect");
  const leaderboardSelect = $("leaderboardSelect");
  const tableBody = $("tableBody");
  const titleSeason = $("titleSeason");
  const pillCount = $("pillCount");
  const msg = $("msg");
  const statusPill = $("statusPill");
  const statusText = $("statusText");

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

  async function loadSeasons() {
    const data = await API.apiGet("/api/public/seasons", { timeoutMs: 12000, retry: 1 });
    const seasons = data?.seasons || [];
    const current = data?.current_season_id || seasons[0]?.season_id || "";

    seasonSelect.innerHTML = "";
    for (const s of seasons) {
      const label = `${s.name || s.season_id} · ${s.start_date || ""}${s.status ? ` · ${s.status}` : ""}`.replace(/\s+/g, " ").trim();
      seasonSelect.appendChild(option(label, s.season_id));
    }

    const qsSeason = getQS("season_id");
    seasonSelect.value = qsSeason || current || seasonSelect.value;

    return seasonSelect.value;
  }

  async function loadLeaderboards(season_id) {
    const data = await API.apiGet(`/api/public/leaderboards?season_id=${encodeURIComponent(season_id)}`, { timeoutMs: 12000, retry: 1 });
    const lbs = data?.leaderboards || [];

    leaderboardSelect.innerHTML = "";
    for (const lb of lbs) {
      const label = `${lb.leaderboard_key}${lb.team_count != null ? ` (${lb.team_count})` : ""}`;
      leaderboardSelect.appendChild(option(label, lb.leaderboard_key));
    }

    // 默认选第一个
    leaderboardSelect.value = lbs[0]?.leaderboard_key || leaderboardSelect.value;
    return leaderboardSelect.value;
  }

  function renderTable(rows) {
    tableBody.innerHTML = "";
    for (const r of rows) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td class="mono">${r.rank ?? ""}</td>
        <td class="strong">${escapeHtml(r.team_name ?? "")}</td>
        <td class="mono">${r.points ?? ""}</td>
      `;
      tableBody.appendChild(tr);
    }
  }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[c]));
  }

  async function reloadAll() {
    setStatus("loading", "Loading...");
    setMsg("");
    try {
      const season_id = await loadSeasons();
      titleSeason.textContent = `season_id = ${season_id}`;

      const leaderboard_key = await loadLeaderboards(season_id);

      const data = await API.apiGet(
        `/api/public/leaderboard?leaderboard_key=${encodeURIComponent(leaderboard_key)}`,
        { timeoutMs: 12000, retry: 1 }
      );

      renderTable(data?.rows || []);
      pillCount.textContent = `${data?.team_count ?? (data?.rows?.length ?? 0)} teams`;

      setStatus("ok", "OK");
    } catch (e) {
      setStatus("error", "ERROR");
      setMsg(String(e?.message || e));
    }
  }

  seasonSelect.addEventListener("change", reloadAll);
  leaderboardSelect.addEventListener("change", reloadAll);
  $("btnBack").addEventListener("click", () => location.href = "/campaigns");
  $("btnRefresh").addEventListener("click", reloadAll);

  await reloadAll();
})();
