/**
 * Step 2 (Fixed): Unified Data Layer + Backward Compatibility
 *
 * Provides:
 *   API.getJSON(path, params?, opts?)
 *   API.apiGet(pathOrUrl, paramsOrOpts?, opts?)
 *
 * Features:
 * - Same-origin by default: /api/public/*
 * - Optional override via window.API_ORIGIN (see config.js)
 * - Timeout (default 10s)
 * - Retry (default 0)
 * - sessionStorage cache with TTL (default 5 min)
 * - Debug mode: add ?debug=1
 */
(() => {
  const DEBUG = new URLSearchParams(location.search).get('debug') === '1';

  const DEFAULTS = {
    ttl: 300,        // seconds
    timeoutMs: 10000,
    retry: 0,
  };

  // Determine API base.
  // If window.API_ORIGIN is set (e.g., workers.dev), use it; otherwise same-origin.
  const origin = (window.API_ORIGIN || '').replace(/\/+$/, '');
  const API_BASE = origin ? (origin + '/api/public') : '/api/public';

  function log(...args) { if (DEBUG) console.log('[API]', ...args); }

  function isAbsoluteUrl(s) { return /^https?:\/\//i.test(s); }

  function normalizePath(p) {
    if (!p) return '/';
    // If caller passed full /api/public/xxx, strip the base prefix
    if (p.startsWith('/api/public/')) return p.slice('/api/public'.length);
    // If caller passed '/api/public' exactly
    if (p === '/api/public') return '/';
    // Otherwise keep as-is (expects '/events', '/seasons', etc.)
    return p.startsWith('/') ? p : ('/' + p);
  }

  function buildUrl(pathOrUrl, params) {
    if (isAbsoluteUrl(pathOrUrl)) {
      const u = new URL(pathOrUrl);
      if (params) Object.entries(params).forEach(([k,v]) => {
        if (v !== undefined && v !== null && v !== '') u.searchParams.set(k, v);
      });
      return u;
    }
    const path = normalizePath(pathOrUrl);
    const u = new URL(API_BASE + path, location.origin);
    if (params) Object.entries(params).forEach(([k,v]) => {
      if (v !== undefined && v !== null && v !== '') u.searchParams.set(k, v);
    });
    return u;
  }

  function cacheKey(u) { return 'api:' + u.toString(); }

  function getCached(u, ttl) {
    try{
      const raw = sessionStorage.getItem(cacheKey(u));
      if (!raw) return null;
      const obj = JSON.parse(raw);
      if (!obj || typeof obj.t !== 'number') return null;
      if (Date.now() - obj.t > ttl * 1000) return null;
      return obj.d;
    } catch { return null; }
  }

  function setCached(u, data) {
    try{
      sessionStorage.setItem(cacheKey(u), JSON.stringify({ t: Date.now(), d: data }));
    } catch {}
  }

  async function fetchJson(u, { timeoutMs, retry }){
    const attempt = async () => {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeoutMs);
      try{
        const res = await fetch(u.toString(), { signal: controller.signal });
        if (!res.ok) {
          const txt = await res.text().catch(() => '');
          throw new Error(`${res.status} ${res.statusText}${txt ? ' — ' + txt.slice(0,200) : ''}`);
        }
        return await res.json();
      } finally {
        clearTimeout(timer);
      }
    };

    let lastErr;
    for (let i=0; i<=retry; i++){
      try { return await attempt(); }
      catch(e){ lastErr = e; log('attempt failed', i+1, e); }
    }
    throw lastErr;
  }

  async function getJSON(pathOrUrl, params = {}, opts = {}) {
    const o = { ...DEFAULTS, ...opts };
    const u = buildUrl(pathOrUrl, params);

    const cached = getCached(u, o.ttl);
    if (cached !== null) {
      log('cache hit', u.toString());
      return cached;
    }

    log('fetch', u.toString());
    const data = await fetchJson(u, o);
    setCached(u, data);
    return data;
  }

  /**
   * Compatibility wrapper:
   * - apiGet(path, params, opts)  (new style)
   * - apiGet(url, opts)          (old style in your team.js/players.js)
   */
  async function apiGet(pathOrUrl, a = {}, b = {}) {
    // If second arg looks like opts (has timeoutMs/retry/ttl) and third arg is empty:
    const looksLikeOpts = a && typeof a === 'object' && (
      'timeoutMs' in a || 'retry' in a || 'ttl' in a
    );
    if (looksLikeOpts && (!b || Object.keys(b).length === 0)) {
      return getJSON(pathOrUrl, {}, a);
    }
    return getJSON(pathOrUrl, a, b);
  }

  window.API = { getJSON, apiGet, API_BASE };
})();