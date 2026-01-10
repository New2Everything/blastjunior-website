// assets/js/pages/campaigns.js
(async () => {
  const $ = (id) => document.getElementById(id);

  const statusDot = $("statusDot");
  const statusText = $("statusText");
  const statusPill = $("statusPill");
  const seasonSelect = $("seasonSelect");
  const msg = $("msg");

  function setStatus(kind, text) {
    statusPill.dataset.kind = kind; // ok|loading|error
    statusText.textContent = text;
  }

  function setMsg(t) {
    msg.textContent = t || "";
  }

  function option(label, value) {
    const o = document.createElement("option");
    o.value = value;
    o.textContent = label;
    return o;
  }

  async function loadSeasons() {
    setStatus("loading", "Loading...");
    setMsg("");

    try {
      const data = await API.apiGet("/api/public/seasons", { timeoutMs: 12000, retry: 1 });

      seasonSelect.innerHTML = "";
      const seasons = data?.seasons || [];
      const current = data?.current_season_id || (seasons[0]?.season_id ?? "");

      for (const s of seasons) {
        const label = `${s.name || s.season_id} · ${s.start_date || ""}${s.status ? ` · ${s.status}` : ""}`.replace(/\s+/g, " ").trim();
        seasonSelect.appendChild(option(label, s.season_id));
      }
      seasonSelect.value = current || seasonSelect.value;

      setStatus("ok", "OK");
      return seasonSelect.value;
    } catch (e) {
      setStatus("error", "ERROR");
      setMsg(`Failed to fetch: ${String(e?.message || e)}`);
      throw e;
    }
  }

  $("btnHpl").addEventListener("click", () => {
    const season_id = seasonSelect.value;
    location.href = `/hpl?season_id=${encodeURIComponent(season_id)}`;
  });

  $("btnTeam").addEventListener("click", () => {
    const season_id = seasonSelect.value;
    location.href = `/team?season_id=${encodeURIComponent(season_id)}`;
  });

  $("btnPlayers").addEventListener("click", () => {
    location.href = `/players`;
  });

  $("btnRefresh").addEventListener("click", async () => {
    try { await loadSeasons(); } catch {}
  });

  // 初始加载
  try { await loadSeasons(); } catch {}
})();
