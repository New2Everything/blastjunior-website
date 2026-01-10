// /assets/js/api.js
(function () {
  const DEFAULT_TIMEOUT_MS = 15000;

  function withQuery(url, params = {}) {
    const u = new URL(url, window.location.origin);
    Object.entries(params).forEach(([k, v]) => {
      if (v === undefined || v === null || v === "") return;
      u.searchParams.set(k, String(v));
    });
    return u.toString();
  }

  async function apiFetchJson(path, params = {}, { timeoutMs = DEFAULT_TIMEOUT_MS } = {}) {
    const url = withQuery(path, params);

    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), timeoutMs);

    try {
      const res = await fetch(url, {
        method: "GET",
        headers: { "Accept": "application/json" },
        signal: ctrl.signal,
        cache: "no-store",
      });

      const text = await res.text();
      let data = null;
      try { data = text ? JSON.parse(text) : null; } catch { data = { raw: text }; }

      if (!res.ok) {
        const msg = (data && (data.error || data.message)) ? (data.error || data.message) : `HTTP ${res.status}`;
        const err = new Error(msg);
        err.status = res.status;
        err.data = data;
        throw err;
      }

      // 兼容：有些接口返回 {ok:false,error:"..."}
      if (data && data.ok === false) {
        const err = new Error(data.error || "API returned ok:false");
        err.status = 200;
        err.data = data;
        throw err;
      }

      return data;
    } finally {
      clearTimeout(t);
    }
  }

  window.API = {
    apiGet: apiFetchJson,
  };
})();
