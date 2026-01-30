import { API } from "../api.js";

const el = {
  q: document.getElementById("q"),
  btnSearch: document.getElementById("btnSearch"),
  result: document.getElementById("result"),
  hint: document.getElementById("hint"),
  statusDot: document.getElementById("statusDot"),
  statusText: document.getElementById("statusText"),
};

function setStatus(ok, text){
  if (el.statusDot) el.statusDot.style.background = ok ? "var(--ok)" : "var(--err)";
  if (el.statusText) el.statusText.textContent = text;
}

function escapeHTML(s){
  return String(s).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"','&quot;');
}

function renderPlayerDetail(p){
  el.result.innerHTML = `
    <div class="card" style="box-shadow:none">
      <div class="card-inner">
        <div class="split" style="align-items:center;justify-content:space-between">
          <div>
            <div style="font-size:20px;font-weight:900">${escapeHTML(p.nickname || p.display_name || p.player_id)}</div>
            <div class="muted" style="margin-top:4px">ID: ${escapeHTML(p.player_id || "-")}</div>
            <div class="muted">姓名: ${escapeHTML(p.real_name || "-")}</div>
            <div class="muted">俱乐部: ${escapeHTML(p.club_name || "-")}</div>
          </div>
          <a class="btn" href="/team/?team_id=${encodeURIComponent(p.team_id || "")}" style="visibility:${p.team_id?"visible":"hidden"}">Team</a>
        </div>



<div class="cards-row" style="margin-top:14px;">
  <div class="stat"><div class="k">Entries</div><div class="v">${p.summary?.participations ?? 0}</div></div>
  <div class="stat"><div class="k">Best Rank</div><div class="v">${p.summary?.best_rank ?? "-"}</div></div>
  <div class="stat"><div class="k">Champions</div><div class="v">${p.summary?.champion_count ?? 0}</div></div>
  <div class="stat"><div class="k">Podiums</div><div class="v">${p.summary?.podium_count ?? 0}</div></div>
  <div class="stat"><div class="k">Teams</div><div class="v">${p.summary?.teams_played ?? 0}</div></div>
</div>

${Array.isArray(p.results) && p.results.length ? `
  <div style="margin-top:16px">
    <div class="section-title">联赛成绩</div>
    <div style="overflow:auto">
      <table class="table">
        <thead><tr><th>SEASON</th><th>DIVISION</th><th class="right">RANK</th><th class="right">POINTS</th><th>TEAM</th></tr></thead>
        <tbody>
          ${p.results.map(r => `
            <tr>
              <td>${escapeHTML(r.season_id)}</td>
              <td>${escapeHTML(r.division_name || r.division_key)}</td>
              <td class="right">${escapeHTML(String(r.rank))}</td>
              <td class="right">${escapeHTML(String(r.points))}</td>
              <td><a href="/team/?team_id=${encodeURIComponent(r.team_id)}">${escapeHTML(r.team_name || r.team_id)}</a></td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  </div>
` : ""}

        ${Array.isArray(p.rosters) && p.rosters.length ? `
          <div style="margin-top:16px">
            <div class="section-title">出现在哪些队伍/赛季</div>
            <div style="overflow:auto">
              <table class="table">
                <thead><tr><th>SEASON</th><th>TEAM</th><th>TEAM_ID</th></tr></thead>
                <tbody>
                  ${p.rosters.map(r => `
                    <tr>
                      <td>${escapeHTML(r.season_id)}</td>
                      <td><a href="/team/?team_id=${encodeURIComponent(r.team_id)}">${escapeHTML(r.team_name || r.team_id)}</a></td>
                      <td class="muted">${escapeHTML(r.team_id)}</td>
                    </tr>
                  `).join("")}
                </tbody>
              </table>
            </div>
          </div>
        ` : ""}
      </div>
    </div>
  `;
}

function renderLookupList(list){
  el.result.innerHTML = `
    <div style="overflow:auto">
      <table class="table">
        <thead><tr><th>PLAYER_ID</th><th>昵称</th><th>姓名</th><th>俱乐部</th></tr></thead>
        <tbody>
          ${list.map(p => `
            <tr>
              <td><a href="#" data-player-id="${escapeHTML(p.player_id)}">${escapeHTML(p.player_id)}</a></td>
              <td>${escapeHTML(p.nickname || "-")}</td>
              <td>${escapeHTML(p.real_name || "-")}</td>
              <td class="muted">${escapeHTML(p.club_name || "-")}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    </div>
  `;

  el.result.querySelectorAll("a[data-player-id]").forEach(a => {
    a.addEventListener("click", async (ev) => {
      ev.preventDefault();
      await loadDetail(a.getAttribute("data-player-id"));
    });
  });
}

async function loadDetail(player_id){
  const d = await API.playerDetail(player_id);
  renderPlayerDetail(d);
}

function looksLikePlayerId(q){
  const s = q.trim();
  if (!s) return false;
  // ids in this project look like lx_002; treat any token containing '_' as id
  if (s.includes("_")) return true;
  // also allow exact alnum with dash
  return /^\w{2,30}$/.test(s) && /^[a-z]/i.test(s);
}

async function onSearch(){
  const q = el.q.value.trim();
  if (!q){
    el.hint.textContent = "请输入关键词";
    return;
  }

  try{
    setStatus(true, "Loading");

    if (looksLikePlayerId(q)){
      await loadDetail(q);
      el.hint.textContent = "";
      setStatus(true, "OK");
      return;
    }

    const list = await API.playerLookup(q);
    if (!list || list.length === 0){
      el.result.innerHTML = `<div class="muted">没有找到结果</div>`;
    } else if (list.length === 1){
      await loadDetail(list[0].player_id);
    } else {
      renderLookupList(list);
    }

    el.hint.textContent = "";
    setStatus(true, "OK");
  }catch(e){
    console.error(e);
    el.result.innerHTML = `<div class="muted">查询失败</div>`;
    setStatus(false, "ERROR");
  }
}

el.btnSearch.addEventListener("click", onSearch);
el.q.addEventListener("keydown", (e) => { if (e.key === "Enter") onSearch(); });

// deep link: /players/?q=...
const qs = new URLSearchParams(location.search);
const preset = qs.get("q");
if (preset){
  el.q.value = preset;
  onSearch();
}
