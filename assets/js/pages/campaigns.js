/* globals API */
// Step 7: Campaigns page — division switch, round selection, explain cards, shareable URL, and team link context
(() => {
  const $ = (id) => document.getElementById(id);
  const qs = () => new URLSearchParams(location.search);

  const el = {
    seasonSelect: $("seasonSelect"),
    divisionSelect: $("divisionSelect"),
    roundSelect: $("roundSelect"),
    tableBody: $("tableBody"),
    infoCards: $("infoCards"),
    infoExplain: $("infoExplain"),

    btnRefresh: $("btnRefresh"),
    msg: $("msg"),
    statusPill: $("statusPill"),
    statusText: $("statusText"),
  };

  function setStatus(kind, text){
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

  function card(label, value, sub=""){
    return `
      <div class="card">
        <div class="label">${esc(label)}</div>
        <div class="value mono">${esc(value)}</div>
        ${sub ? `<div class="sub muted">${esc(sub)}</div>` : ""}
      </div>
    `;
  }

  function renderExplain({ event, season, division, lastRound, selectedRound }){
    const topN = 20;

    const cards = [
      card("Event", event?.name_zh || event?.name_en || event?.event_id || "HPL"),
      card("Season", season?.name || season?.season_id || "unknown", season?.status || ""),
      card("Division", division?.name || division?.division_key || "elite"),
      card("Default Round", lastRound?.name || lastRound?.leaderboard_key || "unknown", "Top20 默认口径"),
      card("Viewing Round", selectedRound?.name || selectedRound?.leaderboard_key || "unknown", `榜单展示 Top ${topN}`),
    ].join("");

    if (el.infoCards) el.infoCards.innerHTML = `<div class="cards">${cards}</div>`;
    if (el.infoExplain){
      el.infoExplain.textContent =
        "说明：本页 Top 20 默认展示该 Division 的「最后一个 Round」积分（last_round）。你也可以从 Round 下拉中切换查看其它 Round 的 Top 20。点击 Team 将进入 Team 档案页（Team 页不处理 Round 选择）。";
    }
  }

  async function loadBootstrap(){
    // locked to HPL ongoing in your backend bootstrap
    const boot = await API.getJSON("/bootstrap", {}, { ttl: 60 });
    return boot;
  }

  async function loadDivisions(season_id){
    const data = await API.getJSON("/divisions", { season_id }, { ttl: 300 });
    return data?.divisions || [];
  }

  async function loadRounds(season_id, division_key){
    const data = await API.getJSON("/rounds_bundle", { season_id, division_key }, { ttl: 60 });
    // expect: rounds + last_round
    return data;
  }

  async function loadLeaderboard(season_id, leaderboard_key){
    const data = await API.getJSON("/leaderboard_bundle", { season_id, leaderboard_key }, { ttl: 30 });
    return data;
  }

  function renderLeaderboard({ rows, season_id, returnTo }){
    el.tableBody.innerHTML = "";
    const top = (rows || []).slice(0, 20);

    if (!top.length){
      el.tableBody.innerHTML = '<tr><td class="muted" colspan="3">暂无数据</td></tr>';
      return;
    }

    top.forEach((r, idx) => {
      const tr = document.createElement("tr");
      tr.classList.add("row-clickable");
      tr.dataset.teamId = r.team_id;
      tr.innerHTML = `
        <td class="mono">${idx + 1}</td>
        <td class="strong">${esc(r.team_name || r.team_id || "")}</td>
        <td class="mono">${esc(r.points ?? 0)}</td>
      `;
      tr.addEventListener("click", () => {
        const team_id = tr.dataset.teamId;
        const url =
          `/team/?team_id=${encodeURIComponent(team_id)}` +
          `&season_id=${encodeURIComponent(season_id)}` +
          `&from=campaigns` +
          `&tab=roster` +
          `&return=${encodeURIComponent(returnTo)}`;
        location.href = url;
      });
      el.tableBody.appendChild(tr);
    });
  }

  function fillSeasonSelect(season){
    el.seasonSelect.innerHTML = "";
    el.seasonSelect.appendChild(option(season?.name || season?.season_id || "season", season?.season_id || ""));
    el.seasonSelect.value = season?.season_id || "";
    // fixed ongoing season: disable manual changing (division switch is allowed)
    el.seasonSelect.disabled = true;
  }

  function fillDivisionSelect(divisions, selectedKey){
    el.divisionSelect.innerHTML = "";
    divisions.forEach(d => {
      const label = d.name ? `${d.name} (${d.division_key})` : d.division_key;
      el.divisionSelect.appendChild(option(label, d.division_key));
    });
    if (divisions.some(d => d.division_key === selectedKey)) el.divisionSelect.value = selectedKey;
    else el.divisionSelect.value = divisions[0]?.division_key || "";
  }

  function fillRoundSelect(rounds, selectedKey){
    el.roundSelect.innerHTML = "";
    rounds.forEach(r => {
      const label = r.name ? `${r.name}` : r.leaderboard_key;
      el.roundSelect.appendChild(option(label, r.leaderboard_key));
    });
    if (rounds.some(r => r.leaderboard_key === selectedKey)) el.roundSelect.value = selectedKey;
    else el.roundSelect.value = rounds[0]?.leaderboard_key || "";
  }

  async function refreshAll(){
    setStatus("loading", "Loading...");
    setMsg("");

    try{
      const boot = await loadBootstrap();
      const season = boot?.season;
      const event = boot?.event;
      const defaultDivision = boot?.division; // likely elite

      const season_id = season?.season_id;
      if (!season_id) throw new Error("bootstrap missing season_id");

      fillSeasonSelect(season);

      // divisions for this season
      const divisions = await loadDivisions(season_id);

      const urlDivisionKey = getQS("division_key");
      const division_key = urlDivisionKey || defaultDivision?.division_key || "elite";
      fillDivisionSelect(divisions, division_key);

      // rounds for division
      const roundsBundle = await loadRounds(season_id, el.divisionSelect.value);
      const rounds = roundsBundle?.rounds || [];
      const lastRound = roundsBundle?.last_round || rounds[rounds.length - 1] || null;

      // selected round for viewing
      const urlRoundKey = getQS("round_key");
      const selectedRoundKey = urlRoundKey || lastRound?.leaderboard_key || rounds[0]?.leaderboard_key || "";
      fillRoundSelect(rounds, selectedRoundKey);

      // persist URL state
      setQS({
        season_id,
        division_key: el.divisionSelect.value,
        round_key: el.roundSelect.value,
      });

      // load leaderboard for selected round
      const board = await loadLeaderboard(season_id, el.roundSelect.value);
      const rows = board?.rows || board?.leaderboard || [];

      const selectedRound = rounds.find(r => r.leaderboard_key === el.roundSelect.value) || null;

      renderExplain({
        event,
        season,
        division: divisions.find(d => d.division_key === el.divisionSelect.value) || defaultDivision,
        lastRound,
        selectedRound,
      });

      const returnTo = `${location.pathname}${location.search}`;
      renderLeaderboard({ rows, season_id, returnTo });

      setStatus("ok", "OK");
    }catch(e){
      console.error(e);
      setStatus("error", "ERROR");
      setMsg(String(e?.message || e));
    }
  }

  // events
  el.btnRefresh?.addEventListener("click", refreshAll);
  el.divisionSelect?.addEventListener("change", async () => {
    // changing division resets round to last_round of new division
    setQS({ division_key: el.divisionSelect.value, round_key: "" });
    await refreshAll();
  });
  el.roundSelect?.addEventListener("change", async () => {
    setQS({ round_key: el.roundSelect.value });
    await refreshAll();
  });

  refreshAll();
})();