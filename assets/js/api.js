(function(){
  function normalizeBase(base) {
    if (!base) return "";
    if (base.endsWith("/")) return base.slice(0, -1);
    return base;
  }

  function getBase() {
    // 你可以在每个页面用 window.API_BASE 覆盖（推荐）
    // 比如：window.API_BASE = "https://blast-campaigns-api.kanjiaming2022.workers.dev";
    var b = window.API_BASE || "";
    return normalizeBase(b);
  }

  function buildUrl(path, params) {
    var base = getBase();
    var url = base + path;
    if (params) {
      var q = [];
      for (var k in params) {
        if (!Object.prototype.hasOwnProperty.call(params, k)) continue;
        var v = params[k];
        if (v === undefined || v === null || v === "") continue;
        q.push(encodeURIComponent(k) + "=" + encodeURIComponent(String(v)));
      }
      if (q.length) url += "?" + q.join("&");
    }
    return url;
  }

  function fetchJson(path, params) {
    var url = buildUrl(path, params);
    return fetch(url, {
      method: "GET",
      headers: { "accept": "application/json" }
    }).then(function(res){
      if (!res.ok) {
        return res.text().then(function(t){
          throw new Error("HTTP " + res.status + " " + res.statusText + " @ " + url + " :: " + t);
        });
      }
      return res.json();
    });
  }

  function setStatus(el, ok, text){
    if (!el) return;
    el.className = "badge " + (ok ? "ok" : "err");
    var dot = el.querySelector(".badge-dot");
    var msg = el.querySelector(".badge-msg");
    if (dot) { /* class controls color */ }
    if (msg) msg.textContent = text || (ok ? "OK" : "ERROR");
  }

  window.Api = {
    buildUrl: buildUrl,
    fetchJson: fetchJson,
    setStatus: setStatus
  };
})();
