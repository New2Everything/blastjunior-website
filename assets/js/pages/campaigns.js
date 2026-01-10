import { apiGet } from "../api.js";
import { qs, setStatus } from "../utils.js";

const statusEl = qs("#status");
const rowsTbody = qs("#rows");

function setRow(i, ok, text) {
  const tr = rowsTbody.children[i];
  if (!tr) return;
  tr.children[2].textContent = ok ? "OK" : `ERROR: ${text || ""}`;
}

async function run() {
  try {
    setStatus(statusEl, { ok: true, text: "loading…" });

    const seasons = await apiGet("/api/public/seasons");
    setRow(0, true, "OK");

    const seasonId = seasons?.current_season_id || seasons?.seasons?.[0]?.season_id;
    if (!seasonId) throw new Error("No season_id from /seasons");

    const lbs = await apiGet(`/api/public/leaderboards?season_id=${encodeURIComponent(seasonId)}`);
    setRow(1, true, "OK");

    const leaderboardKey = lbs?.leaderboards?.[0]?.leaderboard_key;
    if (!leaderboardKey) throw new Error("No leaderboard_key from /leaderboards");

    await apiGet(`/api/public/leaderboard?season_id=${encodeURIComponent(seasonId)}&leaderboard_key=${encodeURIComponent(leaderboardKey)}`);
    setRow(2, true, "OK");

    setStatus(statusEl, { ok: true, text: "OK" });
  } catch (e) {
    setStatus(statusEl, { ok: false, text: e?.message || String(e) });
    setRow(0, false, "");
    setRow(1, false, "");
    setRow(2, false, "");
  }
}

run();
