// blast-subscribe-api - 关注订阅API
// 使用KV存储用户订阅状态

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const action = url.searchParams.get("action");
    const userId = url.searchParams.get("userId") || "anonymous";
    const targetType = url.searchParams.get("type"); // team/player
    const targetId = url.searchParams.get("id");

    const cors = { 
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, OPTIONS" 
    };

    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: cors });
    }

    try {
      // 获取订阅列表
      if (action === "list") {
        const key = `subs:${userId}`;
        const value = await env.KV.get(key);
        const subscriptions = value ? JSON.parse(value) : { teams: [], players: [] };
        
        // 获取订阅对象的详细信息
        let result = { teams: [], players: [] };
        
        if (subscriptions.teams.length > 0) {
          try {
            const obj = await env.BUCKET.get("data/teams.json");
            if (obj) {
              const teams = JSON.parse(await obj.text());
              result.teams = teams.filter(t => subscriptions.teams.includes(t.id));
            }
          } catch(e) {}
        }
        
        if (subscriptions.players.length > 0) {
          try {
            const obj = await env.BUCKET.get("data/players.json");
            if (obj) {
              const players = JSON.parse(await obj.text());
              result.players = players.filter(p => subscriptions.players.includes(p.id));
            }
          } catch(e) {}
        }
        
        return new Response(JSON.stringify({ ok: true, data: result, counts: subscriptions }), {
          headers: { "Content-Type": "application/json", ...cors }
        });
      }
      
      // 订阅
      if (action === "subscribe") {
        if (!targetType || !targetId) {
          return new Response(JSON.stringify({ error: "缺少type或id参数" }), { status: 400, headers: { "Content-Type": "application/json", ...cors } });
        }
        
        const key = `subs:${userId}`;
        const value = await env.KV.get(key);
        const subscriptions = value ? JSON.parse(value) : { teams: [], players: [] };
        
        if (targetType === "team" && !subscriptions.teams.includes(targetId)) {
          subscriptions.teams.push(targetId);
        } else if (targetType === "player" && !subscriptions.players.includes(targetId)) {
          subscriptions.players.push(targetId);
        }
        
        await env.KV.put(key, JSON.stringify(subscriptions));
        
        return new Response(JSON.stringify({ ok: true, action: "subscribed", type: targetType, id: targetId }), {
          headers: { "Content-Type": "application/json", ...cors }
        });
      }
      
      // 取消订阅
      if (action === "unsubscribe") {
        if (!targetType || !targetId) {
          return new Response(JSON.stringify({ error: "缺少type或id参数" }), { status: 400, headers: { "Content-Type": "application/json", ...cors } });
        }
        
        const key = `subs:${userId}`;
        const value = await env.KV.get(key);
        const subscriptions = value ? JSON.parse(value) : { teams: [], players: [] };
        
        if (targetType === "team") {
          subscriptions.teams = subscriptions.teams.filter(id => id !== targetId);
        } else if (targetType === "player") {
          subscriptions.players = subscriptions.players.filter(id => id !== targetId);
        }
        
        await env.KV.put(key, JSON.stringify(subscriptions));
        
        return new Response(JSON.stringify({ ok: true, action: "unsubscribed", type: targetType, id: targetId }), {
          headers: { "Content-Type": "application/json", ...cors }
        });
      }
      
      // 检查是否已订阅
      if (action === "check" && targetType && targetId) {
        const key = `subs:${userId}`;
        const value = await env.KV.get(key);
        const subscriptions = value ? JSON.parse(value) : { teams: [], players: [] };
        
        const isSubscribed = targetType === "team" 
          ? subscriptions.teams.includes(targetId)
          : subscriptions.players.includes(targetId);
        
        return new Response(JSON.stringify({ ok: true, subscribed: isSubscribed }), {
          headers: { "Content-Type": "application/json", ...cors }
        });
      }
      
      return new Response(JSON.stringify({ 
        usage: [
          "?action=list&userId=xxx - 获取订阅列表",
          "?action=subscribe&type=team&id=xxx - 订阅",
          "?action=unsubscribe&type=player&id=xxx - 取消订阅",
          "?action=check&type=team&id=xxx - 检查订阅状态"
        ]
      }), { headers: { "Content-Type": "application/json", ...cors } });

    } catch (err) {
      return new Response(JSON.stringify({ error: err.message }), { status: 500, headers: { "Content-Type": "application/json", ...cors } });
    }
  }
};
