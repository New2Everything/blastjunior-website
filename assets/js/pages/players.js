// assets/js/pages/players.js
(async () => {
  const $ = (id) => document.getElementById(id);

  const qInput = $("qInput");
  const btnSearch = $("btnSearch");
  const msg = $("msg");
  const statusPill = $("statusPill");
  const statusText = $("statusText");
  const tableBody = $("tableBody");

  function setStatus(kind, text) {
    statusPill.dataset.kind = kind;
    statusText.textContent = text;
  }
  function setMsg(t) { msg.textContent = t || ""; }

  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[c]));
  }

  async function search() {
    const q = qInput.value.trim();
    if (!q) {
      setMsg("请输入 player_id 或名字关键词");
      return;
    }

    setStatus("loading", "Loading...");
    setMsg("");
    tableBody.innerHTML = "";

    try {
      // 这里用你已有的 public search 接口（如果你现在是 /api/public/players?q=...）
      const data = await API.apiGet(`/api/public/players?q=${encodeURIComponent(q)}`, { timeoutMs: 12000, retry: 1 });
      const rows = data?.rows || [];

      for (const r of rows) {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td class="mono">${escapeHtml(r.player_id ?? "")}</td>
          <td class="strong">${escapeHtml(r.player_name ?? "")}</td>
          <td class="muted">${escapeHtml(r.team_name ?? "")}</td>
          <td class="muted mono">${escapeHtml(r.season_id ?? "")}</td>
        `;
        tableBody.appendChild(tr);
      }

      setStatus("ok", "OK");
      if (!rows.length) setMsg("没有匹配结果");
    } catch (e) {
      setStatus("error", "ERROR");
      setMsg(String(e?.message || e));
    }
  }

  btnSearch.addEventListener("click", search);
  qInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") search();
  });

  setStatus("ok", "OK");
})();
