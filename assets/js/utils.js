// /assets/js/utils.js
export function setStatus(el, { ok, text }) {
  if (!el) return;
  const dot = el.querySelector(".dot");
  const msg = el.querySelector(".msg");
  if (dot) {
    dot.classList.remove("ok", "bad");
    dot.classList.add(ok ? "ok" : "bad");
  }
  if (msg) msg.textContent = text || (ok ? "OK" : "ERROR");
}

export function qs(sel, root = document) { return root.querySelector(sel); }
export function qsa(sel, root = document) { return Array.from(root.querySelectorAll(sel)); }

export function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

export function fmtDate(s) {
  if (!s) return "—";
  return String(s);
}
