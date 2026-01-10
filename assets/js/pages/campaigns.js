(function(){
  var statusEl, seasonSelect, seasonsHint;

  function el(id){ return document.getElementById(id); }

  function renderSeasons(seasons, currentId){
    seasonSelect.innerHTML = "";
    for (var i=0;i<seasons.length;i++){
      var s = seasons[i];
      var opt = document.createElement("option");
      opt.value = s.season_id;
      var d = [];
      if (s.name) d.push(s.name);
      if (s.start_date) d.push(s.start_date);
      if (s.status) d.push(s.status);
      opt.textContent = d.join(" · ") || s.season_id;
      if (s.season_id === currentId) opt.selected = true;
      seasonSelect.appendChild(opt);
    }
  }

  function getSelectedSeasonId(){
    return seasonSelect.value;
  }

  function wireNav(){
    el("goHpl").addEventListener("click", function(){
      var sid = getSelectedSeasonId();
      location.href = "/hpl?season_id=" + encodeURIComponent(sid);
    });
    el("goTeams").addEventListener("click", function(){
      var sid = getSelectedSeasonId();
      location.href = "/team?season_id=" + encodeURIComponent(sid);
    });
    el("goPlayers").addEventListener("click", function(){
      location.href = "/players";
    });
    el("refreshBtn").addEventListener("click", boot);
  }

  function boot(){
    Api.setStatus(statusEl, true, "Loading…");
    Api.fetchJson("/api/public/seasons").then(function(data){
      var seasons = data.seasons || [];
      var current = data.current_season_id || (seasons[0] ? seasons[0].season_id : "");
      renderSeasons(seasons, current);
      seasonsHint.textContent = "共 " + seasons.length + " 个赛季";
      Api.setStatus(statusEl, true, "OK");
    }).catch(function(err){
      console.error(err);
      Api.setStatus(statusEl, false, "ERROR");
      seasonsHint.textContent = String(err.message || err);
    });
  }

  function init(){
    statusEl = el("statusBadge");
    seasonSelect = el("seasonSelect");
    seasonsHint = el("seasonsHint");
    wireNav();
    boot();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
