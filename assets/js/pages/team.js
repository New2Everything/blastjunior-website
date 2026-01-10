import { apiGet } from "../api.js";
import { qs, setStatus, escapeHtml } from "../utils.js";

const statusEl = qs("#status");
const teamIdInput = qs("#teamIdInput");
const searchBtn = qs("#searchBtn");
const title = qs("#title");
const sub = qs("#sub");
const tbody = qs("#tbody");

function getTeamIdFromUrl() {
  const sp = new URLSearchParams(location.search);
  return sp.get("team_id") || "";
}

async function load(teamId) {
  if (!teamId) throw new Error("team_id 不能为空");
  const data = await apiGet(`/api/public/team?team_id=${encodeURIComponent(teamId)}`);
  const teamName = data?.team?.name || data?.team_name || teamId;
  title.textContent = teamName;
  sub.textContent = `team_id = ${teamId}`;

  const roster = data?.roster || data?.players || [];
  tbody.innerHTML = roster.map(p => `
    <tr>
      <td class="link">
        <a href="/players?player_id=${encodeURIComponent(p.player_id || "")}">${escapeHtml(p.player_name || p.name || p.player_id || "")}</a>
      </td>
      <td>${escapeHtml(p.role || "")}</td>
    </tr>
  `).join("");
}

async function run(teamId) {
  try {
    setStatus(statusEl, { ok: true, text: "loading…" });
    await load(teamId);
    setStatus(statusEl, { ok: true, text: "OK" });
  } catch (e) {
    setStatus(statusEl, { ok: false, text: e?.message || String(e) });
    title.textContent = "—";
    sub.textContent = "—";
    tbody.innerHTML = "";
  }
}

searchBtn.addEventListener("click", () => run(teamIdInput.value.trim()));
teamIdInput.addEventListener("keydown", (e) => { if (e.key === "Enter") run(teamIdInput.value.trim()); });

const initId = getTeamIdFromUrl();
if (initId) {
  teamIdInput.value = initId;
  run(initId);
}
