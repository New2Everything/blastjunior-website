/* globals API */
// Step 6: Players page (search + detail + URL state)
(() => {
  const $ = (id) => document.getElementById(id);
  const qs = () => new URLSearchParams(location.search);

  const el = {
    qInput: $("qInput"),
    btnSearch: $("btnSearch"),
    msg: $("msg"),
    statusPill: $("statusPill"),
    statusText: $("statusText"),
    tableBody: $("tableBody"),
  };

  function setStatus(kind, text){
    if (el.statusPill) el.statusPill.dataset.kind = kind;
    if (el.statusText) el.statusText.textContent = text || "";
  }
  function setMsg(t){ if (el.msg) el.msg.textContent = t || ""; }
  function esc(s){
    return String(s ?? "").replace(/[&<>"']/g, (c) => ({
      "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
    }[c]));
  }
  function getQS(name){ return qs().get(name); }
  function setQS(params){
    const u = new URL(location.href);
    Object.entries(params).forEach(([k,v]) => {
      if (v === null || v === undefined || v === "") u.searchParams.delete(k);
      else u.searchParams.set(k, v);
    });
    history.replaceState({}, "", u.toString());
  }
  function displayName(p){
    return p.nickname || p.display_name || p.real_name || p.player_id || "";
  }

  async function renderDetail(player_id){
    setStatus("loading", "Loading...");
    setMsg("");
    el.tableBody.innerHTML = '<tr><td class="muted" colspan="4">Loading…</td></tr>';

    try{
      const d = await API.getJSON("/player", { player_id }, { ttl: 60 });
      const p = d?.player;
      const rosters = d?.rosters || [];

      if (!p){
        el.tableBody.innerHTML = '<tr><td class="muted" colspan="4">player not found</td></tr>';
        setStatus("ok", "OK");
        return;
      }

      const header = [
        ["PLAYER", displayName(p)],
        ["PLAYER_ID", p.player_id],
        p.club_name ? ["CLUB", p.club_name] : null,
      ].filter(Boolean);

      el.tableBody.innerHTML = header.map(([k,v]) => `
        <tr><td class="muted mono">${esc(k)}</td><td class="strong" colspan="3">${esc(v)}</td></tr>
      `).join("");

      el.tableBody.innerHTML += '<tr><td class="muted mono">ROSTERS</td><td class="muted" colspan="3">该player出现在哪些team/赛季</td></tr>';

      if (!rosters.length){
        el.tableBody.innerHTML += '<tr><td class="muted" colspan="4">暂无 roster</td></tr>';
        setStatus("ok", "OK");
        return;
      }

      const frag = document.createDocumentFragment();
      for (const r of rosters){
        const tr = document.createElement("tr");
        tr.classList.add("row-clickable");
        tr.dataset.teamId = r.team_id;
        tr.dataset.seasonId = r.season_id;
        tr.innerHTML = `
          <td class="muted mono">${esc(r.season_id || "")}</td>
          <td class="strong">${esc(r.team_name || r.team_id || "")}</td>
          <td class="muted">${esc(r.role || "")}</td>
          <td class="muted mono">${esc(r.team_id || "")}</td>
        `;
        tr.addEventListener("click", () => {
          location.href = `/team/?team_id=${encodeURIComponent(tr.dataset.teamId)}&season_id=${encodeURIComponent(tr.dataset.seasonId)}`;
        });
        frag.appendChild(tr);
      }
      el.tableBody.appendChild(frag);

      setStatus("ok", "OK");
    }catch(e){
      console.error(e);
      setStatus("error", "ERROR");
      setMsg(String(e?.message || e));
      el.tableBody.innerHTML = '<tr><td class="muted" colspan="4">加载失败</td></tr>';
    }
  }

  async function search(){
    const q = (el.qInput?.value || "").trim();
    if (!q){
      setMsg("请输入 player_id 或名字关键词");
      return;
    }

    if (/^\d+$/.test(q)){
      setQS({ player_id: q });
      return renderDetail(q);
    }

    setStatus("loading", "Loading...");
    setMsg("");
    el.tableBody.innerHTML = "";

    try{
      const data = await API.getJSON("/players", {}, { ttl: 300 });
      const all = data?.players || (Array.isArray(data) ? data : []);
      const qq = q.toLowerCase();
      const matches = all.filter(p => {
        const a = (p.nickname || "").toLowerCase();
        const b = (p.display_name || "").toLowerCase();
        const c = (p.real_name || "").toLowerCase();
        return a.includes(qq) || b.includes(qq) || c.includes(qq);
      }).slice(0, 30);

      if (!matches.length){
        setStatus("ok", "OK");
        setMsg("没有匹配结果");
        return;
      }

      el.tableBody.innerHTML = matches.map(p => `
        <tr class="row-clickable" data-player="${esc(p.player_id)}">
          <td class="mono">${esc(p.player_id)}</td>
          <td class="strong">${esc(displayName(p))}</td>
          <td class="muted">${esc(p.club_name || "")}</td>
          <td class="muted">${esc(p.is_active ?? "")}</td>
        </tr>
      `).join("");

      el.tableBody.querySelectorAll("tr[data-player]").forEach(tr => {
        tr.addEventListener("click", () => {
          const pid = tr.getAttribute("data-player");
          if (el.qInput) el.qInput.value = pid;
          setQS({ player_id: pid });
          renderDetail(pid);
        });
      });

      setStatus("ok", "OK");
    }catch(e){
      console.error(e);
      setStatus("error", "ERROR");
      setMsg(String(e?.message || e));
    }
  }

  const pid = getQS("player_id");
  if (pid){
    if (el.qInput) el.qInput.value = pid;
    renderDetail(pid);
  } else {
    setStatus("ok", "OK");
  }

  el.btnSearch?.addEventListener("click", search);
  el.qInput?.addEventListener("keydown", (e) => { if (e.key === "Enter") search(); });
})();