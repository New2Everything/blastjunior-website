/* globals API */
(() => {
  const $ = (id) => document.getElementById(id);

  const el = {
    event: $("eventSelect"),
    season: $("seasonSelect"),
    division: $("divisionSelect"),
    view: $("viewSelect"),
    round: $("roundSelect"),
    lbKeyBox: $("lbKeyBox"),
    btnRefresh: $("btnRefresh"),
    tableBody: $("tableBody"),
    titleLine: $("titleLine"),
    metaLine: $("metaLine"),
    statusDot: $("statusDot"),
    statusText: $("statusText"),
  };

  const state = {
    events: [],
    seasons: [],
    divisions: [],
    leaderboards: [],
    current: { event_id: "", season_id: "", division_id: "", baseKey: "", mode: "total" },
  };

  function setStatus(kind, text) {
    el.statusText.textContent = text;
    el.statusDot.classList.toggle("err", kind === "error");
  }

  function opt(value, label) {
    const o = document.createElement("option");
    o.value = value;
    o.textContent = label;
    return o;
  }

  function fillSelect(selectEl, items, { valueKey, labelFn, placeholder }) {
    selectEl.innerHTML = "";
    if (placeholder) selectEl.appendChild(opt("", placeholder));
    for (const it of items) selectEl.appendChild(opt(it[valueKey], labelFn(it)));
  }

  async function loadEvents() {
    const data = await API.getJSON("/api/public/events");
    state.events = data.events || [];
    fillSelect(el.event, state.events, {
      valueKey: "event_id",
      labelFn: (e) => e.name_zh || e.name_en || e.event_id,
      placeholder: "请选择赛事…",
    });
  }

  async function loadSeasons(event_id) {
    const data = await API.getJSON("/api/public/seasons", { event_id });
    state.seasons = data.seasons || [];
    fillSelect(el.season, state.seasons, {
      valueKey: "season_id",
      labelFn: (s) => {
        const y = s.year ? String(s.year) : "";
        const st = s.status ? String(s.status) : "";
        const name = s.name || s.season_id;
        return [name, y && `· ${y}`, st && `· ${st}`].filter(Boolean).join(" ");
      },
      placeholder: "请选择赛季…",
    });
  }

  async function loadDivisions(season_id) {
    const data = await API.getJSON("/api/public/divisions", { season_id });
    state.divisions = data.divisions || [];
    fillSelect(el.division, state.divisions, {
      valueKey: "division_id",
      labelFn: (d) => d.name || d.division_id,
      placeholder: "请选择组别…",
    });
  }

  async function loadLeaderboards(season_id) {
    const data = await API.getJSON("/api/public/leaderboards", { season_id });
    state.leaderboards = data.leaderboards || [];
  }

  function recomputeRoundSelect() {
    const baseKey = state.current.baseKey;
    const keys = (state.leaderboards || []).map(x => x.leaderboard_key).filter(Boolean);
    const subs = keys.filter(k => k.startsWith(baseKey + "_"));
    el.round.innerHTML = "";
    if (!subs.length) {
      el.round.appendChild(opt("", "（无场次/分组可选）"));
      el.round.disabled = true;
      return;
    }
    el.round.appendChild(opt("", "请选择场次/分组…"));
    subs.forEach(k => el.round.appendChild(opt(k, k.replace(baseKey + "_", ""))));
    el.round.disabled = false;
  }

  async function renderLeaderboard(leaderboard_key) {
    if (!state.current.season_id || !leaderboard_key) return;

    setStatus("ok", "Loading…");
    el.tableBody.innerHTML = '<tr><td class="muted" colspan="3">Loading…</td></tr>';

    const data = await API.getJSON("/api/public/leaderboard", {
      season_id: state.current.season_id,
      leaderboard_key,
    });

    const rows = data.rows || [];

    const ev = state.events.find(x => x.event_id === state.current.event_id);
    const se = state.seasons.find(x => x.season_id === state.current.season_id);
    const dv = state.divisions.find(x => x.division_id === state.current.division_id);

    $("titleLine").textContent = [
      ev?.name_zh || ev?.name_en || ev?.event_id,
      se?.name || se?.season_id,
      dv?.name || dv?.division_id
    ].filter(Boolean).join(" · ");
    $("metaLine").textContent = leaderboard_key;

    if (!rows.length) {
      el.tableBody.innerHTML = '<tr><td class="muted" colspan="3">暂无数据</td></tr>';
      setStatus("ok", "OK");
      return;
    }

    el.tableBody.innerHTML = rows.map(r => `
      <tr>
        <td>${r.rank ?? ""}</td>
        <td>${String(r.team_name ?? r.team_id ?? "").replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;")}</td>
        <td>${r.points ?? 0}</td>
      </tr>
    `).join("");

    setStatus("ok", "OK");
  }

  async function onEventChange() {
    const event_id = el.event.value;
    state.current.event_id = event_id;

    fillSelect(el.season, [], { valueKey: "season_id", labelFn: () => "", placeholder: "请选择赛季…" });
    fillSelect(el.division, [], { valueKey: "division_id", labelFn: () => "", placeholder: "请选择组别…" });
    el.lbKeyBox.value = "";
    el.round.innerHTML = "";
    el.round.disabled = true;

    if (!event_id) return;
    await loadSeasons(event_id);
  }

  async function onSeasonChange() {
    const season_id = el.season.value;
    state.current.season_id = season_id;

    fillSelect(el.division, [], { valueKey: "division_id", labelFn: () => "", placeholder: "请选择组别…" });
    el.lbKeyBox.value = "";
    el.round.innerHTML = "";
    el.round.disabled = true;

    if (!season_id) return;
    await Promise.all([loadDivisions(season_id), loadLeaderboards(season_id)]);
  }

  async function onDivisionChange() {
    const division_id = el.division.value;
    state.current.division_id = division_id;

    const dv = state.divisions.find(x => x.division_id === division_id);
    state.current.baseKey = dv?.leaderboard_key || "";
    el.lbKeyBox.value = state.current.baseKey;

    recomputeRoundSelect();
    if (state.current.baseKey) await renderLeaderboard(state.current.baseKey);
  }

  async function onViewChange() {
    const mode = el.view.value;
    state.current.mode = mode;

    if (!state.current.baseKey) return;

    if (mode === "total") return renderLeaderboard(state.current.baseKey);
    recomputeRoundSelect();
    // round 模式默认还是显示 base，避免空白
    return renderLeaderboard(state.current.baseKey);
  }

  async function onRoundChange() {
    const k = el.round.value;
    if (!k) return;
    return renderLeaderboard(k);
  }

  async function refreshAll() {
    try {
      setStatus("ok", "Loading…");
      await loadEvents();
      if (state.events.length === 1) {
        el.event.value = state.events[0].event_id;
        await onEventChange();
      }
      setStatus("ok", "OK");
    } catch (e) {
      console.error(e);
      setStatus("error", "ERROR");
      el.tableBody.innerHTML = '<tr><td class="muted" colspan="3">Failed to fetch</td></tr>';
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    el.event.addEventListener("change", () => onEventChange().catch(console.error));
    el.season.addEventListener("change", () => onSeasonChange().catch(console.error));
    el.division.addEventListener("change", () => onDivisionChange().catch(console.error));
    el.view.addEventListener("change", () => onViewChange().catch(console.error));
    el.round.addEventListener("change", () => onRoundChange().catch(console.error));
    el.btnRefresh.addEventListener("click", () => refreshAll());
    refreshAll();
  });
})();
