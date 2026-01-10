// assets/js/api.js
(() => {
  // ✅ 默认同域：/api/...
  // 你也可以临时改成 "https://blast-campaigns-api.kanjiaming2022.workers.dev"
  // 但手机网络经常不稳定，建议用同域 route。
  const API_BASE = (window.API_BASE ?? "").replace(/\/$/, "");

  function withTimeout(ms) {
    const controller = new AbortController();
    const t = setTimeout(() => controller.abort(new Error("timeout")), ms);
    return { controller, cancel: () => clearTimeout(t) };
  }

  async function safeFetch(url, options = {}, { timeoutMs = 12000, retry = 1 } = {}) {
    let lastErr;
    for (let attempt = 0; attempt <= retry; attempt++) {
      const { controller, cancel } = withTimeout(timeoutMs);
      try {
        const res = await fetch(url, {
          ...options,
          signal: controller.signal,
          // 避免某些移动端怪异缓存
          cache: "no-store",
          mode: "cors",
        });
        cancel();

        if (!res.ok) {
          const text = await res.text().catch(() => "");
          const err = new Error(`HTTP ${res.status} ${res.statusText}${text ? `: ${text}` : ""}`);
          err.status = res.status;
          throw err;
        }

        const ct = (res.headers.get("content-type") || "").toLowerCase();
        if (ct.includes("application/json")) return await res.json();
        // 兜底：有时候 Worker 返回 text
        const raw = await res.text();
        try { return JSON.parse(raw); } catch { return raw; }
      } catch (e) {
        cancel();
        lastErr = e;

        // 只有网络类/超时才重试
        const msg = String(e?.message || "");
        const isNetworkish = msg.includes("Failed to fetch") || msg.includes("NetworkError") || msg.includes("timeout") || msg.includes("aborted");
        if (!isNetworkish || attempt === retry) break;

        // 简单退避
        await new Promise(r => setTimeout(r, 400 + attempt * 600));
      }
    }
    throw lastErr;
  }

  async function apiGet(path, opts) {
    const url = `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
    return safeFetch(url, { method: "GET" }, opts);
  }

  window.API = {
    API_BASE,
    apiGet,
    safeFetch,
  };
})();
