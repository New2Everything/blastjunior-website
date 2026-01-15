/**
 * Optional API base override.
 * If you want to call the Worker directly (cross-domain), set this and include
 * <script src="/assets/js/config.js?v=20260113"></script>
 * BEFORE api.js in each page.
 *
 * Leave this file as-is if you use same-origin routes: /api/public/...
 */
window.API_ORIGIN = "https://blast-campaigns-api.kanjiaming2022.workers.dev";