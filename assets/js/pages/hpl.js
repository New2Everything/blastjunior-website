(function(){
  function el(id){ return document.getElementById(id); }

  var statusEl, seasonSelect, leaderboardSelect, tableBody, seasonMetaEl;
  var drawerBackdrop, drawerTitle, drawerBody;

  function qs(name){
    var m = new RegExp("[?&]" + name + "=([^&]+)").exec(location.search);
    return m ? decodeURIComponent(m[1]) : "";
  }

  function setDrawer(open){
    drawerBackdrop.style.display = open ? "flex" : "none";
  }

  function openDrawer(title, html){
    drawerTitle.textContent = title;
    drawerBody.innerHTML = html;
    setDrawer(true);
  }

  function closeDrawer(){ setDrawer(false); }

  function renderSeasons(seasons, selectedId){
    seasonSelect.innerHTML = "";
    for (var i=0;i<seasons.length;i++){
      var s = seasons[i];
      var opt = document.createElement("option");
      opt.value = s.season_id;
      opt.textContent = (s.name || s.season_id) + (s.start_date ? (" · " + s.start_date) : "") + (s.status ? (" · " + s.status) : "");
      if (s.season_id === selectedId) opt.selected = true;
      seasonSelect.appendChild(opt);
    }
  }

  function renderLeaderboards(items, selectedKey){
    leaderboardSelect.innerHTML = "";
    for (var i=0;i<items.length;i++){
      var it = items[i];
      var opt = document.createElement("option");
      opt.value = it.leaderboard_key;
      opt.textContent = (it.name || it.leaderboard_key) + (it.round_count ? (" (" + it.round_count + ")") : "");
      if (it.leaderboard_key === selectedKey) opt.selected = true;
      leaderboardSelect.appendChild(opt);
    }
  }

  function renderRows(rows){
    tableBody.innerHTML = "";
    for (var i=0;i<rows.length;i++){
      var r = rows[i];
      var tr = document.createElement("tr");
      tr.setAttribute("data-team-id", r.team_id || "");
      tr.setAttribute("data-team-name", r.team_name || "");
      tr.innerHTML =
        "<td>" + String(r.rank || "") + "</td>" +
        "<td>" + escapeHtml(r.team_name || r.team_id || "") + "</td>" +
        "<td>" + String(r.points || 0) + "</td>";
      tr.addEventListener("click", function(){
        var teamId = this.getAttribute("data-team-id");
        var teamName = this.getAttribute("data-team-name");
        if (!teamId) return;
        loadTeam(teamId, teamName);
      });
      tableBody.appendChild(tr);
    }
  }

  function escapeHtml(s){
    return String(s)
      .replace(/&/g,"&amp;")
      .replace(/</g,"&lt;")
      .replace(/>/g,"&gt;")
      .replace(/"/g,"&quot;")
      .replace(/'/g,"&#039;");
  }

  function selectedSeason(){ return seasonSelect.value; }
  function selectedLeaderboard(){ return leaderboardSelect.value; }

  function loadTeam(teamId, teamName){
    var sid = selectedSeason();
    Api.setStatus(statusEl, true, "Loading team…");
    Api.fetchJson("/api/public/team", { team_id: teamId, season_id: sid }).then(function(data){
      Api.setStatus(statusEl, true, "OK");
      var roster = data.roster || [];
      var html = "";

      html += '<div class="kpi" style="margin-bottom:12px;">' +
        '<div><strong>' + escapeHtml(teamName || data.team_name || teamId) + '</strong><div class="small">team_id = ' + escapeHtml(teamId) + '</div></div>' +
        '<div class="small">season_id = ' + escapeHtml(sid) + '</div>' +
      '</div>';

      html += '<div class="btn-row" style="margin-bottom:12px;">' +
        '<a class="btn primary" href="/team?team_id=' + encodeURIComponent(teamId) + '&season_id=' + encodeURIComponent(sid) + '">打开队伍页</a>' +
      '</div>';

      html += "<h3 style='margin:12px 0 8px;'>Roster</h3>";
      if (!roster.length) {
        html += "<div class='muted'>无 roster 记录</div>";
      } else {
        html += "<ul class='list'>";
        for (var i=0;i<roster.length;i++){
          var p = roster[i];
          html += "<li><strong>" + escapeHtml(p.display_name || p.player_id) + "</strong>" +
                  "<div class='small'>player_id = " + escapeHtml(p.player_id) + (p.alias ? (" · alias = " + escapeHtml(p.alias)) : "") + "</div>" +
                  "</li>";
        }
        html += "</ul>";
      }

      openDrawer("队伍详情", html);
    }).catch(function(err){
      console.error(err);
      Api.setStatus(statusEl, false, "ERROR");
      openDrawer("队伍详情（加载失败）", "<div class='muted'>" + escapeHtml(err.message || err) + "</div>");
    });
  }

  function loadLeaderboard(){
    var sid = selectedSeason();
    var key = selectedLeaderboard();
    if (!sid || !key) return;

    Api.setStatus(statusEl, true, "Loading leaderboard…");
    Api.fetchJson("/api/public/leaderboard", { season_id: sid, leaderboard_key: key }).then(function(data){
      var rows = data.rows || [];
      el("teamCount").textContent = (data.team_count || rows.length || 0) + " teams";
      renderRows(rows);
      Api.setStatus(statusEl, true, "OK");
    }).catch(function(err){
      console.error(err);
      Api.setStatus(statusEl, false, "ERROR");
      tableBody.innerHTML = "<tr><td colspan='3' class='muted'>加载失败：" + escapeHtml(err.message || err) + "</td></tr>";
    });
  }

  function loadLeaderboardsForSeason(){
    var sid = selectedSeason();
    Api.setStatus(statusEl, true, "Loading season…");

    // 你的 Worker 目前如果没有单独的 /leaderboards，我们就用 /rounds 来凑（它能列出 component/round 列表）
    Api.fetchJson("/api/public/rounds", { season_id: sid }).then(function(data){
      var items = data.rounds || [];
      // rounds 里通常会有 leaderboard_key / name / round_count
      // 如果你的字段名略有不同，这里也能兜底显示 leaderboard_key
      var preferKey = qs("leaderboard_key") || (items[0] ? (items[0].leaderboard_key || "") : "");
      renderLeaderboards(items, preferKey);
      seasonMetaEl.textContent = "season_id = " + sid;
      Api.setStatus(statusEl, true, "OK");
      loadLeaderboard();
    }).catch(function(err){
      console.error(err);
      Api.setStatus(statusEl, false, "ERROR");
      seasonMetaEl.textContent = String(err.message || err);
    });
  }

  function boot(){
    Api.setStatus(statusEl, true, "Loading…");
    Api.fetchJson("/api/public/seasons").then(function(data){
      var seasons = data.seasons || [];
      var sid = qs("season_id") || data.current_season_id || (seasons[0] ? seasons[0].season_id : "");
      renderSeasons(seasons, sid);
      loadLeaderboardsForSeason();
    }).catch(function(err){
      console.error(err);
      Api.setStatus(statusEl, false, "ERROR");
      seasonMetaEl.textContent = String(err.message || err);
    });
  }

  function init(){
    statusEl = el("statusBadge");
    seasonSelect = el("seasonSelect");
    leaderboardSelect = el("leaderboardSelect");
    tableBody = el("lbBody");
    seasonMetaEl = el("seasonMeta");

    drawerBackdrop = el("drawerBackdrop");
    drawerTitle = el("drawerTitle");
    drawerBody = el("drawerBody");
    el("drawerClose").addEventListener("click", closeDrawer);
    drawerBackdrop.addEventListener("click", function(e){
      if (e.target === drawerBackdrop) closeDrawer();
    });

    el("refreshBtn").addEventListener("click", boot);
    el("backBtn").addEventListener("click", function(){ location.href="/campaigns"; });

    seasonSelect.addEventListener("change", function(){
      // 更新 URL，方便分享
      var sid = selectedSeason();
      history.replaceState({}, "", "/hpl?season_id=" + encodeURIComponent(sid));
      loadLeaderboardsForSeason();
    });

    leaderboardSelect.addEventListener("change", function(){
      var sid = selectedSeason();
      var key = selectedLeaderboard();
      history.replaceState({}, "", "/hpl?season_id=" + encodeURIComponent(sid) + "&leaderboard_key=" + encodeURIComponent(key));
      loadLeaderboard();
    });

    boot();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
