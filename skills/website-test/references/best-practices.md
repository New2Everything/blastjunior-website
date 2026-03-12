# 网站开发最佳实践

> 本文档定义网站开发应遵循的最佳实践，用于指导开发并作为测试依据。

---

## 1. 路由架构

### 1.1 SPA路由（推荐）

**原则**：使用单一HTML文件，通过前端路由动态加载内容

| 实践 | 示例 | 检测方法 |
|------|------|----------|
| 干净URL（无.html后缀） | `/teams` 而非 `/teams.html` | URL正则检测 |
| 统一入口 | 所有路由指向 index.html | fallback配置 |
| 历史模式 | 使用 History API | `window.history.pushState` |

**检测项**：
```bash
# URL不应包含.html后缀
if [[ "$url" =~ \.html$ ]]; then
    echo "FAIL: URL包含.html后缀，应使用SPA路由"
fi
```

### 1.2 文件组织

**推荐结构**：
```
public/
├── index.html          # SPA入口
├── _routes.json       # 路由配置
└── assets/            # 静态资源
```

**检测项**：
- 不应有多个独立的HTML页面
- 详情页应通过路由参数实现（`?id=xxx` 或 `/xxx`）

---

## 2. 数据加载

### 2.1 数据来源

**原则**：所有动态数据必须来自API，禁止硬编码

| 数据类型 | 正确来源 | 禁止 |
|----------|----------|------|
| 战队列表 | D1 → Worker API | 硬编码JSON |
| 选手数据 | D1 → Worker API | 静态数组 |
| 积分排名 | D1 → Worker API | 固定排名 |
| 新闻内容 | D1/R2 → Worker API | 固定文本 |

**检测项**：
```bash
# 读取页面源码，检测是否有硬编码数据
if grep -q "const teams = \[" index.html; then
    echo "FAIL: 检测到硬编码的teams数据"
fi
```

### 2.2 加载状态

**原则**：数据加载中应有loading状态，加载失败应有错误提示

| 状态 | 要求 |
|------|------|
| 加载中 | 显示"加载中..."或骨架屏 |
| 加载成功 | 正常渲染数据 |
| 加载失败 | 显示友好错误提示，不白屏 |

**检测项**：
- 初始加载时页面不应为空白
- 应有loading指示器

---

## 3. 性能

### 3.1 SLO基准

| 指标 | 目标 | 超时告警 |
|------|------|----------|
| 首页API响应 | ≤300ms | >500ms |
| 详情页API响应 | ≤500ms | >800ms |
| 首屏加载 | ≤2.5s | >4s |
| 图片失败率 | ≤0.5% | >1% |

### 3.2 缓存策略

| 资源类型 | 缓存策略 |
|----------|----------|
| API数据 | KV缓存5分钟 |
| 静态资源 | 长期缓存 |
| 图片 | CDN优化 |

---

## 4. SEO与可访问性

### 4.1 页面Title

**原则**：每个页面应有独特的title，准确描述页面内容

| 页面 | 正确title | 错误title |
|------|-----------|-----------|
| 首页 | 兰星少年 HADO 俱乐部 - 官网 | 官网 |
| 战队详情 | AKA - 兰星少年 HADO 俱乐部 | 战队详情 |
| 选手详情 | 羽 - 兰星少年 HADO 俱乐部 | 选手 |

**检测项**：
```bash
# 检测title是否包含页面关键信息
title=$(curl -s "$url" | grep -oP '(?<=<title>)[^<]+')
if [[ ! "$title" =~ "兰星少年" ]]; then
    echo "FAIL: title可能不正确"
fi
```

### 4.2 Meta标签

**必含**：
```html
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>页面标题</title>
```

---

## 5. 用户体验

### 5.1 导航

- 导航链接应正确指向路由
- 当前页面应有高亮状态
- 面包屑导航（如适用）

### 5.2 响应式

- 移动端正常显示
- 触摸友好

### 5.3 错误处理

- 404页面友好
- API错误不白屏
- 表单验证友好提示

---

## 6. 代码质量

### 6.1 无控制台错误

**原则**：生产环境不应有JS错误

**检测项**：
```bash
# 使用agent-browser检测控制台错误
agent-browser open "$url"
agent-browser errors  # 应返回空
```

### 6.2 无undefined/NaN

**原则**：页面不应显示"undefined"、"NaN"等原始值

**检测项**：
```bash
# 页面snapshot检测
if snapshot | grep -q "undefined"; then
    echo "FAIL: 检测到undefined值"
fi
```

---

## 7. 安全

### 7.1 HTTPS

- 全站HTTPS
- 混合内容警告

### 7.2 输入安全

- 表单输入 sanitization
- XSS防护

---

## 8. 检测流程

### 8.1 自动化测试

```bash
# 完整最佳实践检测
SITE_URL=https://example.com API_BASE=https://api.example.com \
bash skills/website-test/scripts/best_practice_test.sh
```

### 8.2 检测清单

| 类别 | 检测项 | 优先级 |
|------|--------|--------|
| 路由 | URL无.html后缀 | P0 |
| 路由 | SPA fallback正确 | P0 |
| 数据 | 无硬编码数据 | P0 |
| 数据 | 加载状态正常 | P1 |
| 性能 | API响应时间SLO | P1 |
| SEO | title正确 | P1 |
| UX | 无控制台错误 | P1 |
| UX | 无undefined值 | P1 |
| 安全 | HTTPS | P2 |

---

## 9. 违反示例

### ❌ 错误：多HTML文件
```
/index.html
/teams.html
/team-detail.html
/players.html
/player-detail.html
```
问题：每个详情页都需要独立文件，难以维护

### ✅ 正确：SPA路由
```
/                   → index.html → 加载首页数据
/teams              → index.html → 加载战队列表
/teams/TEAM002      → index.html → 加载战队详情
/players/lx_001     → index.html → 加载选手详情
```

### ❌ 错误：硬编码数据
```javascript
const teams = [
    { id: 1, name: "战队A" },
    { id: 2, name: "战队B" }
];
```

### ✅ 正确：API获取
```javascript
const resp = await fetch(API_BASE + '/teams');
const teams = await resp.json();
```

---

*持续更新中...*
