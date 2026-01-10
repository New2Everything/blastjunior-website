(function(){
  function el(id){ return document.getElementById(id); }
  function qs(name){
    var m = new RegExp("[?&]" + name + "=([^&]+)").exec(location.search);
    return m ? decodeURIComponent(m[1]) : "";
  }
  function escapeHtml(s){
    return String(s)
      .replace(/&/g,"&amp;")
      .replace(/</g,"&lt;")
      .replace(/>/g,"&gt;")
      .replace(/"/g,"&quot;")
      .replace(/'/g,"&#039;");
  }

  var statusEl, seasonSelect, teamSelect, hintEl, rosterEl, pointsBody;

  function renderSeasons(seasons, selected){
    seasonSelect.innerHTML = "";
    for (var i=0;i<seasons.length;i++){
      var s = seasons[i];
      var opt = document.createElement("option");
      opt.value = s.season_id;
      opt.textContent = (s.name || s.season_id) + (s.start_date ? (" · " + s.start_date) : "") + (s.status ? (" · " + s.status) : "");
      if (s.season_id === selected) opt.selected = true;
      seasonSelect.appendChild(opt);
    }
  }

  function renderTeams(teams, selectedId){
    teamSelect.innerHTML = "";
    var opt0 = document.createElement("option");
    opt0.value = "";
    opt0.textContent = "请选择队伍";
    teamSelect.appendChild(opt0);

    for (var i=0;i<teams.length;i++){
      var t = teams[i];
      var opt = document.createElement("option");
      opt.value = t.team_id;
      opt.textContent = (t.team_name || t.team_id);
      if (t.team_id === selectedId) opt.selected = true;
      teamSelect.appendChild(opt);
    }
  }

  function renderRoster(roster){
    if (!roster || !roster.length){
      rosterEl.innerHTML = "<div class='muted'>暂无 roster</div>";
      return;
    }
    var html = "<ul class='list'>";
    for (var i=0;i<roster.length;i++){
      var p = roster[i];
      html += "<li><strong>" + escapeHtml(p.display_name || p.player_id) + "</strong>" +
              "<div class='small'>player_id = " + escapeHtml(p.player_id) + (p.alias ? (" · alias = " + escapeHtml(p.alias)) : "") + "</div>" +
              "</li>";
    }
    html += "</ul>";
    rosterEl.innerHTML = html;
  }

  function renderPoints(points){
    pointsBody.innerHTML = "";
    if (!points || !points.length){
      pointsBody.innerHTML = "<tr><td colspan='4' class='muted'>暂无积分明细</td></tr>";
      return;
    }
    for (var i=0;i<points.length;i++){
      var x = points[i];
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" + escapeHtml(x.leaderboard_key || "") + "</td>" +
        "<td>" + escapeHtml(x.component_name || x.component_id || "") + "</td>" +
        "<td>" + String(x.points || 0) + "</td>" +
        "<td>" + escapeHtml(x.created_at || "") + "</td>";
      pointsBody.appendChild(tr);
    }
  }

  function loadTeamDetail(teamId){
    var sid = seasonSelect.value;
    if (!teamId){
      hintEl.textContent = "请选择队伍";
      rosterEl.innerHTML = "";
      pointsBody.innerHTML = "";
      return;
    }
    Api.setStatus(statusEl, true, "Loading…");
    Api.fetchJson("/api/public/team", { team_id: teamId, season_id: sid }).then(function(data){
      Api.setStatus(statusEl, true, "OK");
      hintEl.textContent = "team_id = " + teamId + " · season_id = " + sid;

      renderRoster(data.roster || []);
      renderPoints(data.points || []);
    }).catch(function(err){
      console.error(err);
      Api.setStatus(statusEl, false, "ERROR");
      hintEl.textContent = String(err.message || err);
      rosterEl.innerHTML = "<div class='muted'>加载失败</div>";
      pointsBody.innerHTML = "<tr><td colspan='4' class='muted'>加载失败</td></tr>";
    });
  }

  function loadTeams(){
    var sid = seasonSelect.value;
    Api.setStatus(statusEl, true, "Loading teams…");
    Api.fetchJson("/api/public/teams", { season_id: sid }).then(function(data){
      var teams = data.teams || [];
      var pick = qs("team_id") || "";
      renderTeams(teams, pick);
      Api.setStatus(statusEl, true, "OK");
      if (pick) loadTeamDetail(pick);
    }).catch(function(err){
      console.error(err);
      Api.setStatus(statusEl, false, "ERROR");
      hintEl.textContent = String(err.message || err);
    });
  }

  function boot(){
    Api.setStatus(statusEl, true, "Loading…");
    Api.fetchJson("/api/public/seasons").then(function(data){
      var seasons = data.seasons || [];
      var sid = qs("season_id") || data.current_season_id || (seasons[0] ? seasons[0].season_id : "");
      renderSeasons(seasons, sid);
      loadTeams();
    }).catch(function(err){
      console.error(err);
      Api.setStatus(statusEl, false, "ERROR");
      hintEl.textContent = String(err.message || err);
    });
  }

  function init(){
    statusEl = el("statusBadge");
    seasonSelect = el("seasonSelect");
    teamSelect = el("teamSelect");
    hintEl = el("hint");
    rosterEl = el("roster");
    pointsBody = el("pointsBody");

    el("backBtn").addEventListener("click", function(){ location.href="/campaigns"; });
    el("refreshBtn").addEventListener("click", boot);

    seasonSelect.addEventListener("change", function(){
      history.replaceState({}, "", "/team?season_id=" + encodeURIComponent(seasonSelect.value));
      loadTeams();
    });
    teamSelect.addEventListener("change", function(){
      var tid = teamSelect.value;
      var sid = seasonSelect.value;
      history.replaceState({}, "", "/team?season_id=" + encodeURIComponent(sid) + "&team_id=" + encodeURIComponent(tid));
      loadTeamDetail(tid);
    });

    boot();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
