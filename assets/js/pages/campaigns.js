/* campaigns.js
 * 方案A：Event → Season → Division → LeaderboardKey → Leaderboard 表格
 * 目标：不动现有 CSS 响应式；只替换数据流与展示逻辑
 */

(function () {
  const $ = (id) => document.getElementById(id);

  const els = {
    statusPill: $("statusPill"),
    errBox: $("errBox"),

    eventSelect: $("eventSelect"),
    seasonSelect: $("seasonSelect"),
    divisionSelect: $("divisionSelect"),
    leaderboardSelect: $("leaderboardSelect"),

    refreshBtn: $("refreshBtn"),
    openTeamBtn: $("openTeamBtn"),
    openPlayersBtn: $("openPlayersBtn"),

    mainTitle: $("mainTitle"),
    mainSub: $("mainSub"),
    metaPill: $("metaPill"),

    lbBody: $("lbBody"),
  };

  const state = {
    events: [],
    seasons: [],
    divisions: [],
    leaderboards: [],

    event_id: null,
    season_id: null,
    division_id: null,
    division_leaderboard_key: null,

    leaderboard_key: null,
  };

  // -----------------------------
  // UI helpers
  // -----------------------------
  function setStatus(ok, text) {
    els.statusPill.classList.toggle("ok", !!ok);
    els.statusPill.classList.toggle("bad", !ok);
    els.statusPill.textContent = text || (ok ? "OK" : "ERROR");
  }

  function setError(msg) {
    if (!msg) {
      els.errBox.style.display = "none";
      els.errBox.textContent = "";
      return;
    }
    els.errBox.style.display = "block";
    els.errBox.textContent = msg;
  }

  function setLoading(isLoading) {
    if (isLoading) {
      setStatus(true, "Loading...");
    } else {
      // 不要强行改成 OK，由调用方决定最终状态
    }
  }

  function setSelectOptions(selectEl, items, { valueKey, labelKey, placeholder }) {
    selectEl.innerHTML = "";
    if (placeholder) {
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = placeholder;
      selectEl.appendChild(opt);
    }
    for (const it of items) {
      const opt = document.createElement("option");
      opt.value = it[valueKey];
      opt.textContent = it[labelKey];
      selectEl.appendChild(opt);
    }
  }

  function setTableRows(rows) {
    if (!rows || rows.length === 0) {
      els.lbBody.innerHTML = `<tr><td colspan="3" class="muted">暂无数据</td></tr>`;
      return;
    }
    const html = rows
      .map((r, idx) => {
        const rank = idx + 1;
        const teamName = escapeHtml(r.team_name ?? r.canonical_name ?? r.team ?? r.team_id ?? "unknown");
        const points = (r.points ?? 0);
        const teamId = r.team_id ?? "";
        return `
          <tr class="row-click" data-team-id="${escapeAttr(teamId)}" title="点击查看队伍详情">
            <td>${rank}</td>
            <td>${teamName}</td>
            <td>${points}</td>
          </tr>
        `;
      })
      .join("");
    els.lbBody.innerHTML = html;

    // 行点击 → team.html
    els.lbBody.querySelectorAll("tr.row-click").forEach((tr) => {
      tr.addEventListener("click", () => {
        const team_id = tr.getAttribute("data-team-id");
        if (!team_id || !state.season_id) return;
        const url = `/team?season_id=${encodeURIComponent(state.season_id)}&team_id=${encodeURIComponent(team_id)}`;
        window.location.href = url;
      });
    });
  }

  function escapeHtml(s) {
    return String(s)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }
  function escapeAttr(s) {
    return escapeHtml(s).replaceAll("`", "&#096;");
  }

  function updateMeta() {
    const parts = [];
    if (state.event_id) parts.push(`event=${state.event_id}`);
    if (state.season_id) parts.push(`season=${state.season_id}`);
    if (state.division_id) parts.push(`division=${state.division_id}`);
    if (state.leaderboard_key) parts.push(`lb=${state.leaderboard_key}`);
    els.metaPill.textContent = parts.length ? parts.join(" · ") : "—";

    // 主标题/副标题
    const season = state.seasons.find((s) => s.season_id === state.season_id);
    const div = state.divisions.find((d) => d.division_id === state.division_id);
    const divName = div?.name || div?.division_key || "";
    els.mainTitle.textContent = "积分榜";
    els.mainSub.textContent = [
      season ? `season: ${season.season_id} (${season.name || ""})` : null,
      divName ? `division: ${divName}` : null,
      state.leaderboard_key ? `leaderboard_key: ${state.leaderboard_key}` : null,
    ]
      .filter(Boolean)
      .join(" · ") || "请选择 Event / Season / Division";
  }

  function syncQueryString() {
    const params = new URLSearchParams();
    if (state.event_id) params.set("event_id", state.event_id);
    if (state.season_id) params.set("season_id", state.season_id);
    if (state.division_id) params.set("division_id", state.division_id);
    if (state.leaderboard_key) params.set("leaderboard_key", state.leaderboard_key);
    const newUrl = `${window.location.pathname}?${params.toString()}`;
    window.history.replaceState({}, "", newUrl);
  }

  function readQueryString() {
    const params = new URLSearchParams(window.location.search);
    const q = {
      event_id: params.get("event_id"),
      season_id: params.get("season_id"),
      division_id: params.get("division_id"),
      leaderboard_key: params.get("leaderboard_key"),
    };
    return q;
  }

  // -----------------------------
  // Data loaders (API)
  // -----------------------------
  async function loadEvents() {
    // 优先：/api/public/events（如果你 Worker 还没加，这里会 fallback）
    try {
      const data = await apiGet("/api/public/events");
      if (Array.isArray(data?.items)) return data.items;
      if (Array.isArray(data)) return data;
      return [];
    } catch (_) {
      return null; // 触发 fallback
    }
  }

  async function loadSeasons(event_id) {
    const data = await apiGet(`/api/public/seasons?event_id=${encodeURIComponent(event_id)}`);
    return data.items || [];
  }

  async function loadDivisions(season_id) {
    const data = await apiGet(`/api/public/divisions?season_id=${encodeURIComponent(season_id)}`);
    return data.items || [];
  }

  async function loadLeaderboards(season_id) {
    const data = await apiGet(`/api/public/leaderboards?season_id=${encodeURIComponent(season_id)}`);
    return data.items || [];
  }

  async function loadLeaderboardRows(season_id, leaderboard_key) {
    const data = await apiGet(
      `/api/public/leaderboard?season_id=${encodeURIComponent(season_id)}&leaderboard_key=${encodeURIComponent(leaderboard_key)}`
    );
    return data.items || [];
  }

  // -----------------------------
  // Selection logic
  // -----------------------------
  function chooseDefaultEvent(q) {
    // 你希望 campaigns 默认看到 HPL 过滤结果
    // 所以默认 event_id = "hpl"（若存在），否则选第一个
    if (q?.event_id && state.events.some((e) => e.event_id === q.event_id)) return q.event_id;
    if (state.events.some((e) => e.event_id === "hpl")) return "hpl";
    return state.events[0]?.event_id || null;
  }

  function chooseDefaultSeason(q) {
    if (q?.season_id && state.seasons.some((s) => s.season_id === q.season_id)) return q.season_id;
    // 默认：ongoing 优先，其次最新 year
    const ongoing = state.seasons.find((s) => s.status === "ongoing");
    if (ongoing) return ongoing.season_id;
    const sorted = [...state.seasons].sort((a, b) => (b.year || 0) - (a.year || 0));
    return sorted[0]?.season_id || null;
  }

  function chooseDefaultDivision(q) {
    if (q?.division_id && state.divisions.some((d) => d.division_id === q.division_id)) return q.division_id;
    // 默认：sort_order 最小（通常主赛道靠前），否则第一个
    const sorted = [...state.divisions].sort((a, b) => (a.sort_order || 999) - (b.sort_order || 999));
    return sorted[0]?.division_id || null;
  }

  function filterLeaderboardsByDivision(div) {
    // 核心：用 division.leaderboard_key 作为 base key
    const base = (div?.leaderboard_key || "").trim();
    state.division_leaderboard_key = base || null;

    if (!base) return state.leaderboards;

    // 规则：等于 base 或者以 base + "_" 开头（前缀归属）
    const prefix = base + "_";
    return state.leaderboards.filter((lb) => {
      const k = (lb.leaderboard_key || "").trim();
      return k === base || k.startsWith(prefix);
    });
  }

  function chooseDefaultLeaderboardKey(q, filtered) {
    if (q?.leaderboard_key && filtered.some((x) => x.leaderboard_key === q.leaderboard_key)) return q.leaderboard_key;

    // 优先：正好等于 division base key（代表“总榜/总积分”）
    const base = state.division_leaderboard_key;
    if (base && filtered.some((x) => x.leaderboard_key === base)) return base;

    // 否则：最小 sort_order/最早日期/第一个
    const sorted = [...filtered].sort((a, b) => {
      const so = (a.min_sort_order || a.sort_order || 999) - (b.min_sort_order || b.sort_order || 999);
      if (so !== 0) return so;
      return String(a.leaderboard_key).localeCompare(String(b.leaderboard_key));
    });
    return sorted[0]?.leaderboard_key || null;
  }

  // -----------------------------
  // Main flow
  // -----------------------------
  async function init() {
    setError("");
    setStatus(true, "Loading...");
    setLoading(true);

    const q = readQueryString();

    // 1) Events
    let events = await loadEvents();
    if (events === null) {
      // fallback：如果没有 events API，就从 seasons 聚合 event_id（名称=event_id）
      // 为了不额外拉全量 seasons，这里直接给一个保底：仅 HPL
      events = [{ event_id: "hpl", name_zh: "HPL 超级联赛", name_en: "HADO Pro League" }];
    }
    state.events = events;

    setSelectOptions(els.eventSelect, state.events, {
      valueKey: "event_id",
      labelKey: "name_zh",
      placeholder: "请选择赛事…",
    });

    state.event_id = chooseDefaultEvent(q);
    els.eventSelect.value = state.event_id || "";

    // 2) Seasons
    await refreshSeasons(q);

    // 绑定事件
    bindEvents();

    setLoading(false);
  }

  async function refreshSeasons(q) {
    if (!state.event_id) return;

    setStatus(true, "Loading...");
    setError("");

    state.seasons = await loadSeasons(state.event_id);

    // season label：你之前是 “name · date · status”
    const seasonItems = state.seasons.map((s) => ({
      ...s,
      display:
        `${s.name || s.season_id}` +
        (s.start_date ? ` · ${s.start_date}` : "") +
        (s.status ? ` · ${s.status}` : ""),
    }));

    setSelectOptions(els.seasonSelect, seasonItems, {
      valueKey: "season_id",
      labelKey: "display",
      placeholder: "请选择赛季…",
    });

    state.season_id = chooseDefaultSeason(q);
    els.seasonSelect.value = state.season_id || "";

    await refreshDivisions(q);
  }

  async function refreshDivisions(q) {
    if (!state.season_id) return;

    setStatus(true, "Loading...");
    setError("");

    state.divisions = await loadDivisions(state.season_id);

    const divisionItems = state.divisions.map((d) => ({
      ...d,
      display: `${d.name || d.division_key || d.division_id}`,
    }));

    setSelectOptions(els.divisionSelect, divisionItems, {
      valueKey: "division_id",
      labelKey: "display",
      placeholder: "请选择组别…",
    });

    state.division_id = chooseDefaultDivision(q);
    els.divisionSelect.value = state.division_id || "";

    await refreshLeaderboards(q);
  }

  async function refreshLeaderboards(q) {
    if (!state.season_id) return;

    setStatus(true, "Loading...");
    setError("");

    state.leaderboards = await loadLeaderboards(state.season_id);

    const div = state.divisions.find((d) => d.division_id === state.division_id);
    const filtered = filterLeaderboardsByDivision(div);

    const lbItems = filtered.map((lb) => ({
      ...lb,
      display: `${lb.leaderboard_key}${lb.component_count ? ` (${lb.component_count})` : ""}`,
    }));

    setSelectOptions(els.leaderboardSelect, lbItems, {
      valueKey: "leaderboard_key",
      labelKey: "display",
      placeholder: "请选择榜单口径…",
    });

    state.leaderboard_key = chooseDefaultLeaderboardKey(q, filtered);
    els.leaderboardSelect.value = state.leaderboard_key || "";

    await refreshLeaderboardTable();
  }

  async function refreshLeaderboardTable() {
    updateMeta();
    syncQueryString();

    if (!state.season_id || !state.leaderboard_key) {
      setTableRows([]);
      setStatus(true, "OK");
      return;
    }

    try {
      setStatus(true, "Loading...");
      const rows = await loadLeaderboardRows(state.season_id, state.leaderboard_key);
      setTableRows(rows);
      setStatus(true, "OK");
      setError("");
    } catch (err) {
      console.error(err);
      setStatus(false, "ERROR");
      setError(err?.message || "Failed to fetch");
      setTableRows([]);
    } finally {
      updateMeta();
      syncQueryString();
    }
  }

  function bindEvents() {
    els.eventSelect.addEventListener("change", async () => {
      state.event_id = els.eventSelect.value || null;

      // 清空下游选择
      state.season_id = null;
      state.division_id = null;
      state.leaderboard_key = null;

      els.seasonSelect.value = "";
      els.divisionSelect.value = "";
      els.leaderboardSelect.value = "";

      await refreshSeasons({});
    });

    els.seasonSelect.addEventListener("change", async () => {
      state.season_id = els.seasonSelect.value || null;

      state.division_id = null;
      state.leaderboard_key = null;

      els.divisionSelect.value = "";
      els.leaderboardSelect.value = "";

      await refreshDivisions({});
    });

    els.divisionSelect.addEventListener("change", async () => {
      state.division_id = els.divisionSelect.value || null;

      state.leaderboard_key = null;
      els.leaderboardSelect.value = "";

      await refreshLeaderboards({});
    });

    els.leaderboardSelect.addEventListener("change", async () => {
      state.leaderboard_key = els.leaderboardSelect.value || null;
      await refreshLeaderboardTable();
    });

    els.refreshBtn.addEventListener("click", async () => {
      const q = readQueryString();
      // 按当前选项刷新（不重置）
      try {
        setStatus(true, "Loading...");
        await refreshLeaderboards(q);
      } catch (e) {
        setStatus(false, "ERROR");
        setError(e?.message || "Failed to refresh");
      }
    });

    els.openTeamBtn.addEventListener("click", () => {
      if (!state.season_id) return;
      window.location.href = `/team?season_id=${encodeURIComponent(state.season_id)}`;
    });

    els.openPlayersBtn.addEventListener("click", () => {
      // players 页本身支持 season_id（可选）
      const url = state.season_id
        ? `/players?season_id=${encodeURIComponent(state.season_id)}`
        : `/players`;
      window.location.href = url;
    });
  }

  // boot
  init().catch((err) => {
    console.error(err);
    setStatus(false, "ERROR");
    setError(err?.message || "Init failed");
  });
})();
