# CORS 规则详解

## 核心原则

**只允许 blastjunior.com 一个域名**

## 错误示例（禁止）

```javascript
// ❌ 错误：空格分隔多域名
const allowedOrigins = ["https://blastjunior.com https://www.blastjunior.com"];

// ❌ 错误：通配符
const allowedOrigins = ["*"];

// ❌ 错误：多个独立域名
const allowedOrigins = ["https://blastjunior.com", "https://example.com"];
```

## 正确示例

```javascript
// ✅ 正确：只允许主域名
const allowedOrigins = ["https://blastjunior.com"];
```

## 实现

### Worker API 中的 CORS

```javascript
function corsHeaders(origin) {
  const allowedOrigins = ["https://blastjunior.com"];
  const allowOrigin = allowedOrigins.includes(origin) ? origin : "";
  
  return {
    "Access-Control-Allow-Origin": allowOrigin,
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
  };
}
```

### Preflight 请求

对于 OPTIONS 预检请求，返回 204：

```javascript
if (request.method === "OPTIONS") {
  return new Response(null, { status: 204, headers: corsHeaders(origin) });
}
```

## 测试

```bash
# 验证 CORS
curl -I https://blast-homepage-api.kanjiaming2022.workers.dev/ \
  -H "Origin: https://blastjunior.com" -X OPTIONS | grep access-control

# 应该返回：
# access-control-allow-origin: https://blastjunior.com
```
