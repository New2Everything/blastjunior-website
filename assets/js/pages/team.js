/* globals API */
// Step 6: Team Dashboard (Tabs + Filters + URL state)
(() => {
  const $ = (id) => document.getElementById(id);
  const qs = () => new URLSearchParams(location.search);

  const el = {
    seasonSelect: $("seasonSelect"),
    teamSelect: $("teamSelect"),
    btnBack: $("btnBack"),
    btnRefresh: $("btnRefresh"),

    headerTitle: $("teamHeaderTitle"),
    headerMeta: $("teamHeaderMeta"),
    aliasLine: $("teamAliasLine"),
    noteLine: $("teamNoteLine"),

    rosterBody: $("rosterBody"),
    regsBody: $("regsBody"),

    ptsSeason: $("ptsSeason"),
    ptsType: $("ptsType"),
    ptsQuery: $("ptsQuery"),
    ptsApply: $("ptsApply"),
    ptsReset: $("ptsReset"),
    ptsSummary: $("ptsSummary"),
    ptsTableBody: $("ptsTableBody"),

    msg: $("msg"),
    statusPill: $("statusPill"),
    statusText: $("statusText"),
  };

  function setStatus(kind, text) {
    if (el.statusPill) el.statusPill.dataset.kind = kind;
    if (el.statusText) el.statusText.textContent = text || "";
  }
  function setMsg(t){ if (el.msg) el.msg.textContent = t || ""; }

  function esc(s){
    return String(s ?? "").replace(/[&<>"']/g, (c) => ({
      "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
    }[c]));
  }

  function option(label, value){
    const o = document.createElement("option");
    o.value = value;
    o.textContent = label;
    return o;
  }

  function getQS(name){ return qs().get(name); }

  function setQS(params){
    const u = new URL(location.href);
    Object.entries(params).forEach(([k,v]) => {
      if (v === null || v === undefined || v === "") u.searchParams.delete(k);
      else u.searchParams.set(k, v);
    });
    history.replaceState({}, "", u.toString());
  }

  function activateTab(tab){
    ["roster","regs","points"].forEach(t => {
      const isOn = t === tab;
      document.getElementById(`tab-${t}`)?.classList.toggle("is-active", isOn);
      document.getElementById(`panel-${t}`)?.classList.toggle("is-active", isOn);
    });
    setQS({ tab });
  }

  function formatSeasonLabel(s){
    const parts = [s.name || s.season_id];
    if (s.year) parts.push(String(s.year));
    if (s.status) parts.push(String(s.status));
    return parts.join(" · ");
  }

  async function loadSeasons(){
    const data = await API.getJSON("/seasons", {}, { ttl: 300 });
    const seasons = Array.isArray(data) ? data : (data.seasons || []);
    el.seasonSelect.innerHTML = "";
    el.seasonSelect.appendChild(option("ALL Seasons（全部）", ""));
    for (const s of seasons){
      el.seasonSelect.appendChild(option(formatSeasonLabel(s), s.season_id));
    }
    const qsSeason = getQS("season_id") || "";
    el.seasonSelect.value = seasons.some(x => x.season_id === qsSeason) ? qsSeason : "";
    return el.seasonSelect.value;
  }

  async function loadTeams(season_id){
    const data = await API.getJSON("/teams", season_id ? { season_id } : {}, { ttl: 300 });
    const teams = data?.teams || (Array.isArray(data) ? data : []);
    el.teamSelect.innerHTML = "";
    for (const t of teams){
      const name = t.canonical_name || t.team_name || t.team_id;
      el.teamSelect.appendChild(option(name, t.team_id));
    }
    const qsTeam = getQS("team_id");
    if (qsTeam && teams.some(x => x.team_id === qsTeam)) el.teamSelect.value = qsTeam;
    else if (teams[0]?.team_id) el.teamSelect.value = teams[0].team_id;
    return el.teamSelect.value;
  }

  function renderHeader(detail){
    const team = detail?.team || {};
    const aliases = detail?.aliases || [];
    el.headerTitle.textContent = team.canonical_name || team.team_id || "";
    const parts = [];
    if (team.team_id) parts.push(`ID: ${team.team_id}`);
    if (team.home_city) parts.push(team.home_city);
    el.headerMeta.textContent = parts.join(" · ");
    const aliasText = aliases.map(a => a.alias_name).filter(Boolean).join(" / ");
    el.aliasLine.textContent = aliasText ? `Aliases: ${aliasText}` : "";
    el.noteLine.textContent = team.note ? `Note: ${team.note}` : "";
  }

  function renderRoster(rows){
    el.rosterBody.innerHTML = "";
    if (!rows.length){
      el.rosterBody.innerHTML = '<tr><td class="muted" colspan="3">暂无队员</td></tr>';
      return;
    }
    for (const r of rows){
      const name = r.nickname || r.display_name || r.real_name || r.player_id || "";
      const tr = document.createElement("tr");
      tr.classList.add("row-clickable");
      tr.dataset.playerId = r.player_id;
      tr.innerHTML = `
        <td class="strong">${esc(name)}</td>
        <td class="muted">${esc(r.role || "")}</td>
        <td class="muted mono">${esc(r.season_name || r.season_id || "")}</td>
      `;
      tr.addEventListener("click", () => {
        location.href = `/players/?player_id=${encodeURIComponent(tr.dataset.playerId)}`;
      });
      el.rosterBody.appendChild(tr);
    }
  }

  function renderRegistrations(rows){
    el.regsBody.innerHTML = "";
    if (!rows.length){
      el.regsBody.innerHTML = '<tr><td class="muted" colspan="5">暂无参赛记录</td></tr>';
      return;
    }
    for (const r of rows){
      const eventName = r.event_name_zh || r.event_name_en || r.event_name || "";
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td class="muted mono">${esc(r.season_id || "")}</td>
        <td class="strong">${esc(r.season_name || "")}</td>
        <td class="muted">${esc(eventName)}</td>
        <td class="muted">${esc(r.division || "")}</td>
        <td class="muted mono">${esc(r.status || "")}</td>
      `;
      el.regsBody.appendChild(tr);
    }
  }

  function sumPoints(rows){
    return rows.reduce((acc, r) => acc + (Number(r.points) || 0), 0);
  }

  function groupBy(rows, keyFn){
    const m = new Map();
    for (const r of rows){
      const k = keyFn(r) ?? "unknown";
      if (!m.has(k)) m.set(k, []);
      m.get(k).push(r);
    }
    return m;
  }

  function renderPoints(detail){
    const cps = detail?.component_points || [];
    const regs = detail?.registrations || [];

    // season filter options from regs
    const seasonOptions = Array.from(new Set(regs.map(r => r.season_id).filter(Boolean)));
    el.ptsSeason.innerHTML = "";
    el.ptsSeason.appendChild(option("ALL", ""));
    for (const sid of seasonOptions){
      el.ptsSeason.appendChild(option(sid, sid));
    }

    // apply url state
    const fSeason = getQS("f_season") || "";
    const fType = getQS("f_type") || "";
    const fQ = getQS("q") || "";
    el.ptsSeason.value = seasonOptions.includes(fSeason) ? fSeason : "";
    el.ptsType.value = ["","total","round","round_group"].includes(fType) ? fType : "";
    el.ptsQuery.value = fQ;

    const apply = () => {
      const season_id = el.ptsSeason.value || "";
      const type = el.ptsType.value || "";
      const q = (el.ptsQuery.value || "").trim();

      setQS({ tab: "points", f_season: season_id, f_type: type, q });

      let filtered = cps.slice();
      if (season_id) filtered = filtered.filter(r => r.season_id === season_id);
      if (type) filtered = filtered.filter(r => (r.component_type || "") === type);
      if (q) {
        const qq = q.toLowerCase();
        filtered = filtered.filter(r => {
          const a = String(r.name || "").toLowerCase();
          const b = String(r.component_id || "").toLowerCase();
          const c = String(r.leaderboard_key || "").toLowerCase();
          return a.includes(qq) || b.includes(qq) || c.includes(qq);
        });
      }

      // Summary cards
      const byType = groupBy(filtered, r => r.component_type || "unknown");
      const typeCards = Array.from(byType.entries()).map(([k, items]) => {
        const pts = sumPoints(items);
        return `<div class="card small"><div class="label">${esc(k)}</div><div class="value mono">${pts}</div></div>`;
      }).join("");

      const bySeason = groupBy(filtered, r => r.season_id || "unknown");
      const seasonCards = Array.from(bySeason.entries()).map(([k, items]) => {
        const pts = sumPoints(items);
        return `<div class="card small"><div class="label">${esc(k)}</div><div class="value mono">${pts}</div></div>`;
      }).join("");

      el.ptsSummary.innerHTML = `
        <div class="cards">
          <div class="card"><div class="label">Filtered Components</div><div class="value mono">${filtered.length}</div></div>
          <div class="card"><div class="label">Filtered Points Sum</div><div class="value mono">${sumPoints(filtered)}</div></div>
        </div>
        <div class="cards">${typeCards}</div>
        <div class="cards">${seasonCards}</div>
      `;

      // Table
      el.ptsTableBody.innerHTML = "";
      if (!filtered.length){
        el.ptsTableBody.innerHTML = '<tr><td class="muted" colspan="5">无匹配结果</td></tr>';
        return;
      }

      filtered.slice(0, 200).forEach(r => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td class="muted mono">${esc(r.season_id || "")}</td>
          <td class="strong">${esc(r.name || r.component_id || "")}</td>
          <td class="muted mono">${esc(r.component_type || "")}</td>
          <td class="mono">${esc(r.points ?? 0)}</td>
          <td class="muted mono">${esc(r.leaderboard_key || "")}</td>
        `;
        el.ptsTableBody.appendChild(tr);
      });

      if (filtered.length > 200){
        const tr = document.createElement("tr");
        tr.innerHTML = '<td class="muted" colspan="5">（仅显示前 200 条，后续可加分页）</td>';
        el.ptsTableBody.appendChild(tr);
      }
    };

    el.ptsApply.onclick = apply;
    el.ptsReset.onclick = () => {
      el.ptsSeason.value = "";
      el.ptsType.value = "";
      el.ptsQuery.value = "";
      apply();
    };

    apply();
  }

  async function loadTeamDetail(){
    const season_id = el.seasonSelect.value || "";
    const team_id = el.teamSelect.value;
    if (!team_id) return;

    setStatus("loading", "Loading...");
    setMsg("");

    try{
      const detail = await API.getJSON(
        "/team",
        season_id ? { team_id, season_id } : { team_id },
        { ttl: 60 }
      );

      renderHeader(detail);
      renderRoster(detail?.roster || []);
      renderRegistrations(detail?.registrations || []);
      renderPoints(detail);

      setQS({ team_id, season_id });
      setStatus("ok", "OK");
    }catch(e){
      console.error(e);
      setStatus("error", "ERROR");
      setMsg(String(e?.message || e));
    }
  }

  async function init(){
    await loadSeasons();
    await loadTeams(el.seasonSelect.value || "");
    await loadTeamDetail();

    // tabs
    const t = getQS("tab") || "roster";
    activateTab(["roster","regs","points"].includes(t) ? t : "roster");
    document.getElementById("tab-roster")?.addEventListener("click", () => activateTab("roster"));
    document.getElementById("tab-regs")?.addEventListener("click", () => activateTab("regs"));
    document.getElementById("tab-points")?.addEventListener("click", () => activateTab("points"));
  }

  el.seasonSelect.addEventListener("change", async () => {
    await loadTeams(el.seasonSelect.value || "");
    await loadTeamDetail();
  });
  el.teamSelect.addEventListener("change", loadTeamDetail);

  el.btnBack?.addEventListener("click", () => {
    const u = new URL(location.href);
    const from = u.searchParams.get("from");
    const ret = u.searchParams.get("return");
    if (from === "campaigns" && ret) {
      try { location.href = decodeURIComponent(ret); return; } catch (_) {}
    }
    location.href = "/campaigns/";
  });
el.btnRefresh?.addEventListener("click", loadTeamDetail);

  init();
})();