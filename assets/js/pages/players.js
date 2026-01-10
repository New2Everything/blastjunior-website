import { apiGet } from "../api.js";
import { qs, setStatus, escapeHtml } from "../utils.js";

const statusEl = qs("#status");
const playerIdInput = qs("#playerIdInput");
const searchBtn = qs("#searchBtn");
const title = qs("#title");
const sub = qs("#sub");
const tbody = qs("#tbody");

function getPlayerIdFromUrl() {
  const sp = new URLSearchParams(location.search);
  return sp.get("player_id") || "";
}

async function load(playerId) {
  if (!playerId) throw new Error("player_id 不能为空");
  // 你定义的接口：GET /api/public/player?player_id=...
  const data = await apiGet(`/api/public/player?player_id=${encodeURIComponent(playerId)}`);

  title.textContent = data?.player?.name || data?.player_name || playerId;
  sub.textContent = `player_id = ${playerId}`;

  const rows = data?.rosters || data?.rows || [];
  tbody.innerHTML = rows.map(r => `
    <tr>
      <td>${escapeHtml(r.season_id || "")}</td>
      <td class="link"><a href="/team?team_id=${encodeURIComponent(r.team_id || "")}">${escapeHtml(r.team_name || r.team_id || "")}</a></td>
      <td>${escapeHtml(r.role || "")}</td>
    </tr>
  `).join("");
}

async function run(playerId) {
  try {
    setStatus(statusEl, { ok: true, text: "loading…" });
    await load(playerId);
    setStatus(statusEl, { ok: true, text: "OK" });
  } catch (e) {
    setStatus(statusEl, { ok: false, text: e?.message || String(e) });
    title.textContent = "—";
    sub.textContent = "—";
    tbody.innerHTML = "";
  }
}

searchBtn.addEventListener("click", () => run(playerIdInput.value.trim()));
playerIdInput.addEventListener("keydown", (e) => { if (e.key === "Enter") run(playerIdInput.value.trim()); });

const initId = getPlayerIdFromUrl();
if (initId) {
  playerIdInput.value = initId;
  run(initId);
}
