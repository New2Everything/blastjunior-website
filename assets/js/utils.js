export function qs(sel, root = document) {
  return root.querySelector(sel);
}
export function qsa(sel, root = document) {
  return Array.from(root.querySelectorAll(sel));
}

export function getParam(name, fallback = null) {
  const url = new URL(location.href);
  return url.searchParams.get(name) ?? fallback;
}

export function setParam(name, value) {
  const url = new URL(location.href);
  if (value === null || value === undefined) url.searchParams.delete(name);
  else url.searchParams.set(name, value);
  history.replaceState({}, "", url.toString());
}

export function fmtDate(s) {
  if (!s) return "";
  return s;
}

export function escapeHtml(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
