export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    
    // 查询表列表
    if (url.pathname === "/tables") {
      const { results } = await env.DB.prepare("SELECT name FROM sqlite_master WHERE type='table'").all();
      return new Response(JSON.stringify(results, null, 2), { headers: { "Content-Type": "application/json" } });
    }
    
    // 查询表数据
    const tableName = url.searchParams.get("table");
    if (tableName) {
      try {
        const { results } = await env.DB.prepare(`SELECT * FROM ${tableName} LIMIT 20`).all();
        return new Response(JSON.stringify(results, null, 2), { headers: { "Content-Type": "application/json" } });
      } catch (e) {
        return new Response(JSON.stringify({ error: e.message }), { status: 400 });
      }
    }
    
    return new Response("Use /tables or ?table=name", { status: 400 });
  }
};
