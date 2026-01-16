import { CONFIG } from "./config.js";

function url(path, params){
  const u = new URL(CONFIG.API_BASE + path);
  if (params){
    for (const [k,v] of Object.entries(params)){
      if (v === undefined || v === null || v === "") continue;
      u.searchParams.set(k, String(v));
    }
  }
  return u.toString();
}

async function getJSON(path, params){
  const res = await fetch(url(path, params), { headers: { "accept":"application/json" }});
  if (!res.ok){
    const text = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status} ${res.statusText}: ${text}`);
  }
  return res.json();
}

export const API = {
  getJSON,

  events(){
    return getJSON("/events");
  },

  seasons(event_id){
    return getJSON("/seasons", { event_id });
  },

  divisions(season_id){
    return getJSON("/divisions", { season_id });
  },

  roundsBundle(season_id, leaderboard_key){
    return getJSON("/rounds_bundle", { season_id, leaderboard_key });
  },

  leaderboardBundle(leaderboard_key, { limit=20 } = {}){
    return getJSON("/leaderboard_bundle", { leaderboard_key, limit });
  },

  teamProfile(team_id){
    return getJSON("/team_profile", { team_id });
  },

  playerLookup(q){
    return getJSON("/player_lookup", { q });
  },

  playerDetail(player_id){
    return getJSON("/player_detail", { player_id });
  }
};

export const fmt = {
  num(v){
    const n = Number(v);
    if (!Number.isFinite(n)) return "-";
    return String(n);
  }
};
