// /assets/js/pages/campaigns.js
const $ = (id) => document.getElementById(id);

const els = {
  status: $("statusPill"),
  subtitle: $("subtitle"),

  eventSelect: $("eventSelect"),
  seasonSelect: $("seasonSelect"),
  divisionSelect: $("divisionSelect"),
  viewSelect: $("viewSelect"),

  roundField: $("roundField"),
  groupField: $("groupField"),
  roundSelect: $("roundSelect"),
  groupSelect: $("groupSelect"),

  refreshBtn: $("refreshBtn"),

  tbody: $("leaderboardBody"),
};

const EVENT_LABELS = {
  hpl: "HPL 超级联赛",
  world_cup: "HADO WORLD CUP",
  cjk_u15: "中日韩青少年邀请赛（U15）",
  jp_league: "日本国内联赛",
};

let seasons = [];
let divisions = [];
let rounds = []; // from /rounds
let state = {
  eventId: "",
  seasonId: "",
  divisionId: "",
  divisionKey: "",
  divisionLeaderboardKey: "", // division.leaderboard_key
  view: "total",
  roundComponentId: "",
  groupComponentId: "",
};

function setStatus(text, kind = "idle") {
  els.status.textContent = text;

  // 复用你现有的 pill 样式，不新增颜色体系；只加 class 让你未来好扩展
  els.status.classList.remove("ok", "warn", "err", "loading");
  if (kind === "ok") els.status.classList.add("ok");
  if (kind === "warn") els.status.classList.add("warn");
  if (kind === "err") els.status.classList.add("err");
  if (kind === "loading") els.status.classList.add("loading");
}

function safeArr(obj, keys) {
  for (const k of keys) {
    if (obj && Array.isArray(obj[k])) return obj[k];
  }
  return [];
}

function fillSelect(sel, items, { getValue, getLabel, placeholder = "请选择…" } = {}) {
  sel.innerHTML = "";
  const opt0 = document.createElement("option");
  opt0.value = "";
  opt0.textContent = placeholder;
  sel.appendChild(opt0);

  for (const it of items) {
    const opt = document.createElement("option");
    opt.value = getValue(it);
    opt.textContent = getLabel(it);
    sel.appendChild(opt);
  }
}

function renderEmpty(msg = "—") {
  els.tbody.innerHTML = `<tr><td colspan="3" class="muted">${msg}</td></tr>`;
}

function toRowsLeaderboard(resp) {
  // 兼容各种字段名：rows / leaderboard / data
  const rows = safeArr(resp, ["rows", "leaderboard", "data", "items"]);
  // 尝试归一化：rank/team/points
  return rows.map((r, idx) => {
    const rank = r.rank ?? r.ranking ?? r.pos ?? (idx + 1);
    const team =
      r.team_name ??
      r.team ??
      r.name ??
      r.team_display ??
      r.registration_name ??
      r.registration_id ??
      "—";
    const points = r.points ?? r.score ?? r.total_points ?? r.value ?? 0;
    return { rank, team, points };
  });
}

function renderLeaderboard(rows) {
  if (!rows || rows.length === 0) {
    renderEmpty("暂无数据");
    return;
  }
  els.tbody.innerHTML = rows
    .map(
      (r) => `
      <tr>
        <td>${escapeHtml(String(r.rank))}</td>
        <td>${escapeHtml(String(r.team))}</td>
        <td style="text-align:right;">${escapeHtml(String(r.points))}</td>
      </tr>`
    )
    .join("");
}

function escapeHtml(s) {
  return s
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function loadSeasons() {
  setStatus("Loading…", "loading");
  renderEmpty("加载中…");

  const resp = await window.API.apiGet("/api/public/seasons");
  seasons = safeArr(resp, ["seasons", "rows", "data", "items"]);

  // 从 seasons 派生 events（因为当前 public API 没有 /events）
  const eventMap = new Map();
  for (const s of seasons) {
    if (!s.event_id) continue;
    if (!eventMap.has(s.event_id)) {
      eventMap.set(s.event_id, {
        event_id: s.event_id,
        name: EVENT_LABELS[s.event_id] || s.event_id,
      });
    }
  }
  const eventList = Array.from(eventMap.values()).sort((a, b) =>
    String(a.name).localeCompare(String(b.name))
  );

  fillSelect(els.eventSelect, eventList, {
    getValue: (e) => e.event_id,
    getLabel: (e) => e.name,
    placeholder: "请选择赛事（Event）",
  });

  els.eventSelect.disabled = false;
  els.seasonSelect.disabled = true;
  els.divisionSelect.disabled = true;
  els.viewSelect.disabled = true;

  setStatus("OK", "ok");
  els.subtitle.textContent = "请选择 Event / Season / Division";
  renderEmpty("—");
}

function onEventChange() {
  state.eventId = els.eventSelect.value;
  state.seasonId = "";
  state.divisionId = "";
  state.divisionKey = "";
  state.divisionLeaderboardKey = "";
  divisions = [];
  rounds = [];

  els.seasonSelect.disabled = !state.eventId;
  els.divisionSelect.disabled = true;
  els.viewSelect.disabled = true;

  // reset round/group UI
  els.roundField.style.display = "none";
  els.groupField.style.display = "none";
  els.roundSelect.disabled = true;
  els.groupSelect.disabled = true;

  if (!state.eventId) {
    fillSelect(els.seasonSelect, [], { getValue: () => "", getLabel: () => "", placeholder: "先选 Event" });
    fillSelect(els.divisionSelect, [], { getValue: () => "", getLabel: () => "", placeholder: "先选 Season" });
    renderEmpty("—");
    els.subtitle.textContent = "请选择 Event / Season / Division";
    return;
  }

  const seasonList = seasons
    .filter((s) => s.event_id === state.eventId)
    .sort((a, b) => String(b.year ?? "").localeCompare(String(a.year ?? "")));

  fillSelect(els.seasonSelect, seasonList, {
    getValue: (s) => s.season_id,
    getLabel: (s) => {
      const name = s.name ?? s.season_id;
      const year = s.year ? ` · ${s.year}` : "";
      const status = s.status ? ` · ${s.status}` : "";
      return `${name}${year}${status}`;
    },
    placeholder: "请选择赛季（Season）",
  });

  fillSelect(els.divisionSelect, [], { getValue: () => "", getLabel: () => "", placeholder: "先选 Season" });
  renderEmpty("—");
  els.subtitle.textContent = "请选择 Season / Division";
}

async function onSeasonChange() {
  state.seasonId = els.seasonSelect.value;
  state.divisionId = "";
  state.divisionKey = "";
  state.divisionLeaderboardKey = "";
  divisions = [];
  rounds = [];

  els.divisionSelect.disabled = !state.seasonId;
  els.viewSelect.disabled = true;

  els.roundField.style.display = "none";
  els.groupField.style.display = "none";
  els.roundSelect.disabled = true;
  els.groupSelect.disabled = true;

  if (!state.seasonId) {
    fillSelect(els.divisionSelect, [], { getValue: () => "", getLabel: () => "", placeholder: "先选 Season" });
    renderEmpty("—");
    els.subtitle.textContent = "请选择 Division";
    return;
  }

  try {
    setStatus("Loading…", "loading");
    renderEmpty("加载 divisions…");

    const resp = await window.API.apiGet("/api/public/divisions", { season_id: state.seasonId });
    divisions = safeArr(resp, ["divisions", "rows", "data", "items"]);

    divisions.sort((a, b) => (a.sort_order ?? 999) - (b.sort_order ?? 999));

    fillSelect(els.divisionSelect, divisions, {
      getValue: (d) => d.division_id,
      getLabel: (d) => d.name ?? d.division_id,
      placeholder: "请选择组别（Division）",
    });

    setStatus("OK", "ok");
    renderEmpty("请选择 Division");
    els.subtitle.textContent = "请选择 Division";
  } catch (e) {
    setStatus("ERROR", "err");
    renderEmpty(`Failed to load divisions: ${e.message}`);
  }
}

function getSelectedDivision() {
  const div = divisions.find((d) => d.division_id === state.divisionId);
  return div || null;
}

async function loadRoundsIfNeeded() {
  if (!state.seasonId) return;
  if (rounds && rounds.length > 0) return;

  const resp = await window.API.apiGet("/api/public/rounds", {
    season_id: state.seasonId,
    leaderboard_key: state.seasonId, // 你的数据里 round 的 leaderboard_key = season_id（比如 hpl_s2_2025）
  });
  rounds = safeArr(resp, ["rounds", "rows", "data", "items"]);
}

function pickRoundOptionsForSeason() {
  // 仅 round（例如 hpl_s2_2025_r01 / r02 / pvp_r01）
  const list = rounds.filter((r) => {
    const t = r.component_type || r.type;
    return t === "round" || (r.component_id && /_r\d+/.test(r.component_id) && !/_r\d+_/.test(r.component_id));
  });

  // 按 sort_order / start_date
  list.sort((a, b) => (a.sort_order ?? 999) - (b.sort_order ?? 999));
  return list;
}

function pickGroupOptionsForRound(roundId, divisionKey) {
  // round_group（例如 hpl_s2_2025_r01_elite / _rookie / pvp）
  const list = rounds.filter((r) => {
    const t = r.component_type || r.type;
    if (t !== "round_group") return false;
    const cid = r.component_id || "";
    if (!cid.startsWith(roundId + "_")) return false;
    if (!divisionKey) return true;
    return cid.endsWith("_" + divisionKey); // elite / rookie / pvp
  });

  list.sort((a, b) => (a.sort_order ?? 999) - (b.sort_order ?? 999));
  return list;
}

async function loadLeaderboardTotalForDivision(div) {
  const divisionKey = div.division_key || div.divisionId || "";
  const leaderboardKey = div.leaderboard_key || "";

  const resp = await window.API.apiGet("/api/public/leaderboard", {
    season_id: state.seasonId,
    division: divisionKey,
    leaderboard_key: leaderboardKey,
  });

  return toRowsLeaderboard(resp);
}

async function loadLeaderboardForComponent(componentId) {
  const resp = await window.API.apiGet("/api/public/round", {
    component_id: componentId,
  });
  return toRowsLeaderboard(resp);
}

async function onDivisionChange() {
  state.divisionId = els.divisionSelect.value;
  state.view = "total";
  state.roundComponentId = "";
  state.groupComponentId = "";

  els.viewSelect.disabled = !state.divisionId;
  els.viewSelect.value = "total";

  els.roundField.style.display = "none";
  els.groupField.style.display = "none";
  els.roundSelect.disabled = true;
  els.groupSelect.disabled = true;

  if (!state.divisionId) {
    renderEmpty("—");
    els.subtitle.textContent = "请选择 Division";
    return;
  }

  const div = getSelectedDivision();
  if (!div) {
    renderEmpty("Division not found");
    return;
  }

  state.divisionKey = div.division_key || "";
  state.divisionLeaderboardKey = div.leaderboard_key || "";

  const seasonObj = seasons.find((s) => s.season_id === state.seasonId);
  els.subtitle.textContent = `${EVENT_LABELS[state.eventId] || state.eventId} · ${seasonObj?.name || state.seasonId} · ${div.name || div.division_id}`;

  try {
    setStatus("Loading…", "loading");
    renderEmpty("加载总积分…");

    // 1) 默认：总积分
    const rows = await loadLeaderboardTotalForDivision(div);
    renderLeaderboard(rows);

    // 2) 预取 rounds（给“按场次/分组”用）
    await loadRoundsIfNeeded();

    setStatus("OK", "ok");
  } catch (e) {
    setStatus("ERROR", "err");
    renderEmpty(`Failed: ${e.message}`);
  }
}

async function onViewChange() {
  state.view = els.viewSelect.value;

  if (!state.divisionId) return;

  const div = getSelectedDivision();
  if (!div) return;

  if (state.view === "total") {
    els.roundField.style.display = "none";
    els.groupField.style.display = "none";
    els.roundSelect.disabled = true;
    els.groupSelect.disabled = true;

    try {
      setStatus("Loading…", "loading");
      renderEmpty("加载总积分…");
      const rows = await loadLeaderboardTotalForDivision(div);
      renderLeaderboard(rows);
      setStatus("OK", "ok");
    } catch (e) {
      setStatus("ERROR", "err");
      renderEmpty(`Failed: ${e.message}`);
    }
    return;
  }

  // round / group 两种都需要 rounds 下拉
  els.roundField.style.display = "";
  els.roundSelect.disabled = false;

  try {
    setStatus("Loading…", "loading");
    await loadRoundsIfNeeded();

    const roundOptions = pickRoundOptionsForSeason();
    fillSelect(els.roundSelect, roundOptions, {
      getValue: (r) => r.component_id,
      getLabel: (r) => r.name || r.component_id,
      placeholder: "请选择场次（Round）",
    });

    els.groupField.style.display = state.view === "group" ? "" : "none";
    if (state.view !== "group") {
      fillSelect(els.groupSelect, [], { getValue: () => "", getLabel: () => "", placeholder: "—" });
      els.groupSelect.disabled = true;
    }

    renderEmpty("请选择 Round");
    setStatus("OK", "ok");
  } catch (e) {
    setStatus("ERROR", "err");
    renderEmpty(`Failed to load rounds: ${e.message}`);
  }
}

async function onRoundChange() {
  state.roundComponentId = els.roundSelect.value;
  state.groupComponentId = "";

  if (!state.roundComponentId) {
    renderEmpty("请选择 Round");
    els.groupSelect.disabled = true;
    return;
  }

  if (state.view === "round") {
    try {
      setStatus("Loading…", "loading");
      renderEmpty("加载场次积分…");
      const rows = await loadLeaderboardForComponent(state.roundComponentId);
      renderLeaderboard(rows);
      setStatus("OK", "ok");
    } catch (e) {
      setStatus("ERROR", "err");
      renderEmpty(`Failed: ${e.message}`);
    }
    return;
  }

  if (state.view === "group") {
    const div = getSelectedDivision();
    const divisionKey = div?.division_key || "";

    const groupOptions = pickGroupOptionsForRound(state.roundComponentId, divisionKey);
    fillSelect(els.groupSelect, groupOptions, {
      getValue: (g) => g.component_id,
      getLabel: (g) => g.name || g.component_id,
      placeholder: "请选择分组（Group）",
    });
    els.groupSelect.disabled = false;

    renderEmpty("请选择 Group");
  }
}

async function onGroupChange() {
  state.groupComponentId = els.groupSelect.value;

  if (!state.groupComponentId) {
    renderEmpty("请选择 Group");
    return;
  }

  try {
    setStatus("Loading…", "loading");
    renderEmpty("加载分组积分…");
    const rows = await loadLeaderboardForComponent(state.groupComponentId);
    renderLeaderboard(rows);
    setStatus("OK", "ok");
  } catch (e) {
    setStatus("ERROR", "err");
    renderEmpty(`Failed: ${e.message}`);
  }
}

async function refreshAll() {
  // 保守刷新：不动布局，只重拉数据
  try {
    await loadSeasons();
    // reset selects (keep nothing selected)
    els.eventSelect.value = "";
    onEventChange();
  } catch (e) {
    setStatus("ERROR", "err");
    renderEmpty(`Refresh failed: ${e.message}`);
  }
}

// ---------- wire up ----------
els.eventSelect.addEventListener("change", onEventChange);
els.seasonSelect.addEventListener("change", onSeasonChange);
els.divisionSelect.addEventListener("change", onDivisionChange);

els.viewSelect.addEventListener("change", onViewChange);
els.roundSelect.addEventListener("change", onRoundChange);
els.groupSelect.addEventListener("change", onGroupChange);

els.refreshBtn.addEventListener("click", refreshAll);

// init
(async function main() {
  try {
    // 默认进入 campaigns 时：event 预选 hpl（你想“默认看见 HPL 过滤的图”）
    await loadSeasons();

    // 如果存在 hpl，就默认选中
    const hasHpl = Array.from(els.eventSelect.options).some((o) => o.value === "hpl");
    if (hasHpl) {
      els.eventSelect.value = "hpl";
      onEventChange();
    }
  } catch (e) {
    setStatus("ERROR", "err");
    renderEmpty(e.message);
  }
})();
