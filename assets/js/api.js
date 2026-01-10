(() => {
  async function getJSON(path, params = {}) {
    const url = new URL(path, location.origin);
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== null && String(v).length) url.searchParams.set(k, v);
    });

    const res = await fetch(url.toString(), {
      method: "GET",
      headers: { "Accept": "application/json" },
      cache: "no-store",
    });

    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`HTTP ${res.status}: ${text.slice(0, 200)}`);
    }
    return res.json();
  }

  window.API = { getJSON };
})();
