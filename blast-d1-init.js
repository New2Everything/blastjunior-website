export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const action = url.searchParams.get("action");
    const sql = url.searchParams.get("sql");
    
    const cors = { "Access-Control-Allow-Origin": "*", "Content-Type": "application/json" };
    
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors });
    }
    
    try {
      // 执行SQL (INSERT/UPDATE/DELETE)
      if (action === "exec" && sql) {
        const decodedSQL = decodeURIComponent(sql);
        // 使用 prepare + run
        const result = await env.DB.prepare(decodedSQL).run();
        return new Response(JSON.stringify({ ok: true, result }), { headers: cors });
      }
      
      // 查询表
      if (action === "tables") {
        const { results } = await env.DB.prepare("SELECT name FROM sqlite_master WHERE type='table'").all();
        return new Response(JSON.stringify(results), { headers: cors });
      }
      
      // 查询数据 (SELECT)
      if (action === "query") {
        const table = url.searchParams.get("table");
        if (!table) return new Response(JSON.stringify({ error: "need table param" }), { headers: cors });
        
        // 安全的查询
        const stmt = env.DB.prepare(`SELECT * FROM ${table} LIMIT 20`);
        const { results } = await stmt.all();
        return new Response(JSON.stringify(results), { headers: cors });
      }
      
      return new Response(JSON.stringify({ usage: "?action=exec&sql=... | ?action=query&table=xxx | ?action=tables" }), { headers: cors });
      
    } catch (err) {
      return new Response(JSON.stringify({ error: err.message, stack: err.stack }), { status: 500, headers: cors });
    }
  }
};
