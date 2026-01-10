(function(){
  function el(id){ return document.getElementById(id); }
  function escapeHtml(s){
    return String(s)
      .replace(/&/g,"&amp;")
      .replace(/</g,"&lt;")
      .replace(/>/g,"&gt;")
      .replace(/"/g,"&quot;")
      .replace(/'/g,"&#039;");
  }

  var statusEl, qEl, listEl, detailEl;

  function renderList(players){
    listEl.innerHTML = "";
    if (!players || !players.length){
      listEl.innerHTML = "<div class='muted'>没有匹配到球员</div>";
      return;
    }
    var ul = document.createElement("ul");
    ul.className = "list";
    for (var i=0;i<players.length;i++){
      (function(p){
        var li = document.createElement("li");
        var name = p.display_name || p.player_id || "";
        li.innerHTML =
          "<strong>" + escapeHtml(name) + "</strong>" +
          "<div class='small'>player_id = " + escapeHtml(p.player_id || "") + (p.alias ? (" · alias = " + escapeHtml(p.alias)) : "") + "</div>";
        li.addEventListener("click", function(){
          loadPlayer(p.player_id);
        });
        ul.appendChild(li);
      })(players[i]);
    }
    listEl.appendChild(ul);
  }

  function renderDetail(data){
    var rosters = data.rosters || [];
    var html = "";

    html += "<div class='kpi' style='margin-bottom:12px;'>" +
      "<div><strong>" + escapeHtml(data.display_name || data.player_id || "") + "</strong>" +
      "<div class='small'>player_id = " + escapeHtml(data.player_id || "") + "</div></div>" +
      "<div class='small'>" + (data.alias ? ("alias = " + escapeHtml(data.alias)) : "") + "</div>" +
    "</div>";

    html += "<h3 style='margin:12px 0 8px;'>Rosters</h3>";
    if (!rosters.length){
      html += "<div class='muted'>该球员暂无 rosters 记录</div>";
    } else {
      html += "<ul class='list'>";
      for (var i=0;i<rosters.length;i++){
        var r = rosters[i];
        html += "<li><strong>" + escapeHtml(r.team_name || r.team_id || "") + "</strong>" +
                "<div class='small'>team_id = " + escapeHtml(r.team_id || "") +
                (r.season_id ? (" · season_id = " + escapeHtml(r.season_id)) : "") +
                "</div></li>";
      }
      html += "</ul>";
    }

    detailEl.innerHTML = html;
  }

  function loadPlayer(playerId){
    if (!playerId) return;
    Api.setStatus(statusEl, true, "Loading player…");
    Api.fetchJson("/api/public/player", { player_id: playerId }).then(function(data){
      Api.setStatus(statusEl, true, "OK");
      renderDetail(data);
    }).catch(function(err){
      console.error(err);
      Api.setStatus(statusEl, false, "ERROR");
      detailEl.innerHTML = "<div class='muted'>加载失败：" + escapeHtml(err.message || err) + "</div>";
    });
  }

  function search(){
    var q = (qEl.value || "").trim();
    Api.setStatus(statusEl, true, "Searching…");

    // 你 Worker 里已有 GET /api/public/players
    // 我这里用 query 参数，如果你那边参数名不是 query，而是 q/name，也能很容易改
    Api.fetchJson("/api/public/players", { query: q }).then(function(data){
      Api.setStatus(statusEl, true, "OK");
      renderList(data.players || []);
    }).catch(function(err){
      console.error(err);
      Api.setStatus(statusEl, false, "ERROR");
      listEl.innerHTML = "<div class='muted'>搜索失败：" + escapeHtml(err.message || err) + "</div>";
    });
  }

  function init(){
    statusEl = el("statusBadge");
    qEl = el("q");
    listEl = el("list");
    detailEl = el("detail");

    el("backBtn").addEventListener("click", function(){ location.href="/campaigns"; });
    el("searchBtn").addEventListener("click", search);
    qEl.addEventListener("keydown", function(e){
      if (e.key === "Enter") search();
    });

    // 初次拉一遍全量（或空 query）
    search();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
