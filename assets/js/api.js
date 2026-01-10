import { API_BASE } from "./config.js";

async function getJson(path) {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  const data = await res.json();
  if (!res.ok) throw new Error(data?.error || data?.message || `HTTP ${res.status}`);
  return data;
}

export const api = {
  health: () => getJson("/api/public/health"),

  seasons: () => getJson("/api/public/seasons"),

  leaderboards: (seasonId) =>
    getJson(`/api/public/leaderboards?season_id=${encodeURIComponent(seasonId)}`),

  leaderboard: (seasonId, leaderboardKey) =>
    getJson(`/api/public/leaderboard?season_id=${encodeURIComponent(seasonId)}&leaderboard_key=${encodeURIComponent(leaderboardKey)}`),

  teams: (seasonId) =>
    getJson(`/api/public/teams?season_id=${encodeURIComponent(seasonId)}`),

  team: (teamId, seasonId) => {
    const s = seasonId ? `&season_id=${encodeURIComponent(seasonId)}` : "";
    return getJson(`/api/public/team?team_id=${encodeURIComponent(teamId)}${s}`);
  },

  rounds: (seasonId, leaderboardKey) => {
    const k = leaderboardKey ? `&leaderboard_key=${encodeURIComponent(leaderboardKey)}` : "";
    return getJson(`/api/public/rounds?season_id=${encodeURIComponent(seasonId)}${k}`);
  },

  round: (componentId) =>
    getJson(`/api/public/round?component_id=${encodeURIComponent(componentId)}`),

  players: () => getJson(`/api/public/players`),

  player: (playerId) =>
    getJson(`/api/public/player?player_id=${encodeURIComponent(playerId)}`),
};
