export function qs(key) {
  return new URLSearchParams(location.search).get(key);
}

export function setSearch(params, replace = true) {
  const sp = new URLSearchParams(location.search);
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") sp.delete(k);
    else sp.set(k, String(v));
  }
  const newUrl = `${location.pathname}?${sp.toString()}`.replace(/\?$/, "");
  if (replace) history.replaceState({}, "", newUrl);
  else history.pushState({}, "", newUrl);
}

export function clearSearch(keys = []) {
  const sp = new URLSearchParams(location.search);
  for (const k of keys) sp.delete(k);
  const newUrl = `${location.pathname}?${sp.toString()}`.replace(/\?$/, "");
  history.pushState({}, "", newUrl);
}

export function el(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}

export function renderCrumb(container, items) {
  container.innerHTML = "";
  items.forEach((it, idx) => {
    if (idx > 0) container.appendChild(el(`<span class="sep">→</span>`));
    if (it.href) {
      const a = el(`<a href="${it.href}">${escapeHtml(it.label)}</a>`);
      a.addEventListener("click", (e) => {
        e.preventDefault();
        it.onClick?.();
      });
      container.appendChild(a);
    } else {
      container.appendChild(el(`<span>${escapeHtml(it.label)}</span>`));
    }
  });
}

export function escapeHtml(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function tile({ title, subtitle = "", badge = "" }) {
  return el(`
    <div class="tile" role="button" tabindex="0">
      <div class="t">${escapeHtml(title)}</div>
      ${subtitle ? `<div class="s">${escapeHtml(subtitle)}</div>` : ""}
      <div class="meta">
        ${badge ? `<span class="badge">${escapeHtml(badge)}</span>` : ""}
      </div>
    </div>
  `);
}

export function emptyBlock(text = "暂无数据") {
  return el(`<div class="empty">${escapeHtml(text)}</div>`);
}