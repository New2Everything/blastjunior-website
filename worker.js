// blast-auth-api - 用户注册登录系统
// KV: blastjunior-registrations

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = normalizePath(url.pathname, ["/auth"]);

    // CORS
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders() });
    }

    try {
      // 注册
      if (request.method === "POST" && path === "/register") {
        return withCors(await handleRegister(request, env));
      }

      // 登录
      if (request.method === "POST" && path === "/login") {
        return withCors(await handleLogin(request, env));
      }

      // 验证token
      if (request.method === "GET" && path === "/verify") {
        return withCors(await handleVerify(request, env, url.searchParams));
      }

      // 获取用户信息
      if (request.method === "GET" && path === "/user") {
        return withCors(await handleGetUser(request, env, url.searchParams));
      }

      return withCors(jsonResponse({ ok: false, error: "Not found" }, 404));
    } catch (err) {
      return withCors(jsonResponse({ ok: false, error: "Server error", detail: String(err) }, 500));
    }
  },
};

// ========== 核心逻辑 ==========

async function handleRegister(request, env) {
  const { email, password, nickname } = await request.json();

  // 验证必填
  if (!email || !password) {
    return jsonResponse({ ok: false, error: "邮箱和密码必填" }, 400);
  }

  // 检查邮箱格式
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return jsonResponse({ ok: false, error: "邮箱格式不正确" }, 400);
  }

  // 密码强度
  if (password.length < 6) {
    return jsonResponse({ ok: false, error: "密码至少6位" }, 400);
  }

  // 检查是否已注册
  const existing = await env.USERS.get(email.toLowerCase());
  if (existing) {
    return jsonResponse({ ok: false, error: "该邮箱已注册" }, 400);
  }

  // 生成用户ID和Token
  const userId = crypto.randomUUID();
  const passwordHash = await hashPassword(password);
  const now = Date.now();

  const user = {
    id: userId,
    email: email.toLowerCase(),
    nickname: nickname || email.split("@")[0],
    password: passwordHash,
    createdAt: now,
    role: "user",
  };

  // 存到KV
  await env.USERS.put(email.toLowerCase(), JSON.stringify(user));
  await env.USER_IDS.put(userId, JSON.stringify(user));

  // 生成会话token
  const sessionToken = generateToken();
  await env.SESSIONS.put(sessionToken, userId, { expirationTtl: 7 * 24 * 60 * 60 }); // 7天

  return jsonResponse({
    ok: true,
    user: { id: userId, email, nickname: user.nickname, role: user.role },
    token: sessionToken,
  });
}

async function handleLogin(request, env) {
  const { email, password } = await request.json();

  if (!email || !password) {
    return jsonResponse({ ok: false, error: "邮箱和密码必填" }, 400);
  }

  const userData = await env.USERS.get(email.toLowerCase());
  if (!userData) {
    return jsonResponse({ ok: false, error: "邮箱或密码错误" }, 401);
  }

  const user = JSON.parse(userData);
  const valid = await verifyPassword(password, user.password);
  if (!valid) {
    return jsonResponse({ ok: false, error: "邮箱或密码错误" }, 401);
  }

  // 生成会话token
  const sessionToken = generateToken();
  await env.SESSIONS.put(sessionToken, user.id, { expirationTtl: 7 * 24 * 60 * 60 });

  return jsonResponse({
    ok: true,
    user: { id: user.id, email: user.email, nickname: user.nickname, role: user.role },
    token: sessionToken,
  });
}

async function handleVerify(request, env, params) {
  const token = params.get("token") || request.headers.get("Authorization")?.replace("Bearer ", "");
  if (!token) {
    return jsonResponse({ ok: false, error: "缺少token" }, 401);
  }

  const userId = await env.SESSIONS.get(token);
  if (!userId) {
    return jsonResponse({ ok: false, error: "token无效或已过期" }, 401);
  }

  const userData = await env.USER_IDS.get(userId);
  if (!userData) {
    return jsonResponse({ ok: false, error: "用户不存在" }, 401);
  }

  const user = JSON.parse(userData);
  return jsonResponse({
    ok: true,
    user: { id: user.id, email: user.email, nickname: user.nickname, role: user.role },
  });
}

async function handleGetUser(request, env, params) {
  const token = params.get("token") || request.headers.get("Authorization")?.replace("Bearer ", "");
  if (!token) {
    return jsonResponse({ ok: false, error: "缺少token" }, 401);
  }

  const userId = await env.SESSIONS.get(token);
  if (!userId) {
    return jsonResponse({ ok: false, error: "未登录" }, 401);
  }

  const userData = await env.USER_IDS.get(userId);
  if (!userData) {
    return jsonResponse({ ok: false, error: "用户不存在" }, 401);
  }

  const user = JSON.parse(userData);
  return jsonResponse({
    ok: true,
    user: { id: user.id, email: user.email, nickname: user.nickname, role: user.role },
  });
}

// ========== 密码工具 ==========

async function hashPassword(password) {
  const encoder = new TextEncoder();
  const data = encoder.encode(password);
  const hashBuffer = await crypto.subtle.digest("SHA-256", data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map(b => b.toString(16).padStart(2, "0")).join("");
}

async function verifyPassword(password, hash) {
  return (await hashPassword(password)) === hash;
}

function generateToken() {
  const array = new Uint8Array(32);
  crypto.getRandomValues(array);
  return Array.from(array, b => b.toString(16).padStart(2, "0")).join("");
}

// ========== 辅助函数 ==========

function normalizePath(pathname, prefixes = []) {
  for (const p of prefixes) {
    if (pathname === p) return "/";
    if (pathname.startsWith(p + "/")) return pathname.slice(p.length);
  }
  return pathname;
}

function corsHeaders() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
  };
}

function withCors(resp) {
  const h = new Headers(resp.headers);
  const ch = corsHeaders();
  for (const [k, v] of Object.entries(ch)) h.set(k, v);
  return new Response(resp.body, { status: resp.status, headers: h });
}

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data, null, 2), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}
