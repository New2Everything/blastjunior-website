// blast-safe-api - 安全内容审核系统
// 自动过滤色情、暴力、政治敏感等违规内容

// 敏感词库（持续更新）
const SENSITIVE_WORDS = {
  // 政治敏感
  political: [
    "胡锦涛", "温家宝", "江泽民", "朱镕基", "李克强", "温家宝", 
    "习近", "彭丽媛", "薄熙来", "周永康", "郭伯雄", "徐才厚", "令计划",
    "天安门事件", "六四", "法轮功", "全能神", "藏独", "疆独", "台独",
    "共匪", "卖国", "汉奸", "美分", "五毛", "狗腿子"
  ],
  // 色情相关
  porn: [
    "色情", "黄片", "成人", "AV", "苍井空", "波多野结衣", "av网站",
    "黄色", "裸聊", "援交", "约炮", "一夜情", "买春", "卖淫",
    "脱衣", "裸露", "三级片", "毛片", "黄书", "淫秽", "妓女",
    "人肉", "性交易", "嫩妹", "少妇", "学生妹", "操", "干",
    "逼", "肏", "屌", "妓", "婊", "奶子", "大奶", "骚",
    "浪", "淫", "奸", "爽", "做爱", "性交", "口交", "肛交"
  ],
  // 暴力相关
  violence: [
    "杀人", "杀", "砍死", "剁碎", "碎尸", "分尸", "自杀",
    "kill", "death", "die", "murder", "torture", "拷打",
    "炸弹", "爆炸", "炸死", "枪毙", "处决", "凌迟"
  ],
  // 赌博/诈骗
  gambling: [
    "赌博", "博彩", "时时彩", "pk10", "赛车", "澳门赌场",
    "网络赌博", "庄家", "出千", "抽水", "赢钱", "必赢"
  ],
  // 毒品
  drug: [
    "毒品", "大麻", "海洛因", "冰毒", "K粉", "摇头丸", "可卡因",
    "贩毒", "吸毒", "制毒", "罂粟", "鸦片"
  ],
  // 诈骗相关
  scam: [
    "诈骗", "骗子", "传销", "非法集资", "跑路", "爆雷",
    "庞氏", "割韭菜", "血本无归"
  ],
  // 其它违规
  other: [
    "枪支", "武器", "军火", "AK47", "手枪", "子弹",
    "黑市", "黑客", "木马", "病毒", "钓鱼网站",
    "伪造", "假证", "办证", "代孕", "器官"
  ]
};

// 合并所有敏感词
const ALL_SENSITIVE_WORDS = Object.values(SENSITIVE_WORDS).flat();

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = normalizePath(url.pathname, ["/safe"]);

    // CORS
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: corsHeaders() });
    }

    try {
      // 审核内容
      if (request.method === "POST" && (path === "/check" || path === "/")) {
        return withCors(await handleCheck(request, env));
      }

      // 批量审核
      if (request.method === "POST" && path === "/check-batch") {
        return withCors(await handleBatchCheck(request, env));
      }

      // 获取词库统计
      if (request.method === "GET" && path === "/stats") {
        return withCors(handleStats());
      }

      return withCors(jsonResponse({ ok: false, error: "Not found" }, 404));
    } catch (err) {
      return withCors(jsonResponse({ ok: false, error: "Server error", detail: String(err) }, 500));
    }
  },
};

async function handleCheck(request, env) {
  const { content, nickname } = await request.json();

  if (!content) {
    return jsonResponse({ ok: false, error: "内容不能为空" }, 400);
  }

  const result = await checkContent(content, nickname || "");
  
  // 记录审核日志
  await logCheck(env, { content, nickname, result });

  return jsonResponse(result);
}

async function handleBatchCheck(request, env) {
  const { items } = await request.json();

  if (!Array.isArray(items)) {
    return jsonResponse({ ok: false, error: "需要数组" }, 400);
  }

  const results = await Promise.all(
    items.map(async (item) => ({
      ...item,
      ...(await checkContent(item.content, item.nickname || ""))
    }))
  );

  // 统计
  const stats = {
    total: results.length,
    passed: results.filter(r => r.approved).length,
    blocked: results.filter(r => !r.approved).length
  };

  return jsonResponse({ ok: true, results, stats });
}

async function checkContent(content, nickname = "") {
  const text = (content + " " + nickname).toLowerCase();
  const findings = [];

  // 1. 敏感词检查
  for (const word of ALL_SENSITIVE_WORDS) {
    if (text.includes(word.toLowerCase())) {
      findings.push({
        type: "sensitive_word",
        word,
        category: getCategory(word)
      });
    }
  }

  // 2. 重复字符检测（刷屏特征）
  if (/(.)\1{5,}/.test(text)) {
    findings.push({ type: "spam", reason: "重复字符过多" });
  }

  // 3. 纯数字/纯符号检测
  if (/^[0-9\s]*$/.test(text) || /^[\s\d\W]*$/.test(text.replace(/[a-zA-Z]/g, ''))) {
    if (text.length > 10) {
      findings.push({ type: "suspicious", reason: "疑似乱码或机器人生成" });
    }
  }

  // 4. 敏感URL检测
  if (/[(http|https):\/\/]*(xvideos|pornhub|redtube|91porn|草榴|福利社|成人网站)/i.test(text)) {
    findings.push({ type: "porn_link", reason: "包含成人网站链接" });
  }

  if (/(duobao|赌博|彩金|庄家)/i.test(text) && /(\.com|\.net|\.cn)/i.test(text)) {
    findings.push({ type: "gambling_link", reason: "包含赌博链接" });
  }

  // 判定结果
  const hasPolitical = findings.some(f => f.category === "political");
  const hasPorn = findings.some(f => f.category === "porn");
  const hasViolence = findings.some(f => f.category === "violence");
  const hasGambling = findings.some(f => f.category === "gambling");
  const hasDrug = findings.some(f => f.category === "drug");
  const hasScam = findings.some(f => f.category === "scam");

  // 严格级别：政治敏感一律拒绝
  if (hasPolitical) {
    return {
      approved: false,
      reason: "内容包含敏感信息",
      category: "political",
      findings
    };
  }

  // 高危：色情/暴力/赌博/毒品/诈骗
  if (hasPorn || hasViolence || hasGambling || hasDrug || hasScam) {
    return {
      approved: false,
      reason: "内容不符合社区规范",
      category: hasPorn ? "porn" : hasViolence ? "violence" : hasGambling ? "gambling" : hasDrug ? "drug" : "scam",
      findings
    };
  }

  // 中危：标记但允许
  if (findings.length > 0) {
    return {
      approved: true,
      flagged: true,
      reason: "内容已标记待复查",
      findings
    };
  }

  return {
    approved: true,
    reason: "审核通过"
  };
}

function getCategory(word) {
  for (const [category, words] of Object.entries(SENSITIVE_WORDS)) {
    if (words.includes(word)) return category;
  }
  return "other";
}

async function logCheck(env, data) {
  try {
    const log = {
      timestamp: new Date().toISOString(),
      ...data
    };
    const key = `safelog_${Date.now()}_${Math.random().toString(36).slice(2)}`;
    await env.SAFE_LOGS?.put(key, JSON.stringify(log));
  } catch (e) {
    // 静默失败
  }
}

function handleStats() {
  const stats = {};
  for (const [category, words] of Object.entries(SENSITIVE_WORDS)) {
    stats[category] = words.length;
  }
  stats.total = ALL_SENSITIVE_WORDS.length;
  return jsonResponse({ ok: true, stats });
}

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
    "Access-Control-Allow-Headers": "Content-Type, X-Admin-Token",
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
