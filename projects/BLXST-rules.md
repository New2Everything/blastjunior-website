# BLXST 建站规则

> **Description**: 记录网站的制度性规则，禁止随意修改
> **维护规则**: 不要增加骨架，任何修改需经老K确认

> 本文件记录网站的**制度性规则**，禁止随意修改
> 现状类内容请查看 `BLXST-knowledge-graph.md`

---

## 🏛️ 智能体架构

### 角色层级

```
老K
  ↓
主智能体 (BLXST Controller) ← 触发: /blxst-controller
  ↓
子智能体 (Architect / Coder / Tester)
```

### 主智能体职责

| 做 | 不做 |
|----|------|
| 读取文档 | 实际写代码 |
| 拆分任务 | 实际测试 |
| spawn子智能体 | 实际设计 |
| 写回memory | - |

### 子智能体 Spawn 五要素

每次 spawn 子智能体时必须明确：

| 要素 | 说明 |
|------|------|
| 输入 | 信息源（读取哪些文件） |
| 运行 | 执行什么任务 |
| 输出 | 交付什么结果 |
| 技能 | 应该使用的技能 |
| 内容 | 应该掌握的知识 |

### 禁止事项

1. 严禁自己动手干活（只调度）
2. 严禁不spawn而直接写代码
3. 严禁不写回memory就结束

### Skills归属

| 角色 | Skill |
|------|-------|
| 主智能体 | blxst-controller, blxst-sync |
| Architect | (设计规划) |
| Coder | website-builder |
| Tester | website-test |

---

## 🔴 核心原则

### 数据真实性原则
- 所有数据模块必须来自 **D1/R2/KV 真实数据库**
- 禁止硬编码数据、禁止猜测数据
- 宁缺毋滥，不展示假数据
- **AI生成内容 ≠ 虚构数据**（见"禁止事项"第3条）

---

## 🏗️ 架构原则

### 单API架构
- 所有后端端点走 **blast-homepage-api**
- 禁止拆分多个独立API（除非功能完全不同）

### 数据库绑定规则
| 数据类型 | 数据源 | 说明 |
|----------|--------|------|
| 战队/选手/赛季/比赛 | D1 (blast-campaigns-db) | |
| 新闻内容 | D1 (news-database) | |
| 照片/媒体 | R2 (blastjunior-media) | 禁止从D1伪造 |
| 配置/缓存 | KV | 临时配置 |

### 3. 字段映射
```
✅ 正确做法:
  - 开发前先调用 API 确认返回字段
  - 写代码时对照实际 API 返回字段

❌ 禁止:
  - 假设字段名（如 p.url, p.image）
  - 不查 API 就写代码
  - 在代码里改字段映射，必须改 API 返回值
```

---

## 🚫 禁止事项

### 1. CORS 配置
```
✅ 正确（多域名数组）:
  allowedOrigins = [
    "https://blastjunior.com",           # 主站
    "https://www.blastjunior.com",       # 别名
    "https://blastjunior-website.pages.dev"  # 预览环境
  ]
  
❌ 错误:
  - 空格分隔多域名: "https://blastjunior.com https://www.blastjunior.com"
  - 通配符: "*"
```

### 2. KV 使用规则（2026-03-23 新增）
```
✅ 正确使用:
  - KV.get("已知key") - 用完整key查询
  - KV.put("known_key", value) - 写入
  - KV.delete("known_key") - 删除已知key

❌ 禁止在公开接口中使用:
  - KV.list() / KV.list({ prefix: "xxx" })
  - 原因：KV.list() 消耗大量 read operations，free tier 限额极低
  - 前端轮询会快速触发超额（30秒轮询 = 单标签页每天 2880 次操作）

✅ 正确替代方案:
  - 使用 D1 数据库存储需要遍历的数据
  - 示例：在线用户列表 → D1 表 + last_seen 时间戳 + 前端心跳更新
```

### 3. 获取照片的正确 API
```
✅ 正确（必须使用）:
  GET /gallery - 从 D1 (photo_metadata) 读取元数据 + R2 读取图片
  - category: 分类（如"未分类"）
  - cover: 缩略图 URL (R2)
  - full_url: 完整图片 URL (R2)
  
✅ D1 表结构 (blast-photo-db.photo_metadata):
  - id: 自增主键
  - r2_key: R2文件名
  - title: 标题
  - category: 分类（默认"未分类"）
  - description: 描述
  - season: 赛季
  - team_id, team_name: 关联战队
  
❌ 错误:
  - 直接从 R2 遍历文件名生成元数据（已废弃）
  - 使用 blastjunior-media 域名（已废弃）
```

### 2. 数据展示
```
✅ 允许:
  - 页面无数据时显示空状态 ("暂无内容")

❌ 禁止:
  - 伪造占位数据填充空内容
  - 硬编码战队/选手列表
  - Gallery 数据从 D1 伪造（必须从 R2 读取）
  - 使用 picsum/placeholder 等外部图床作为 fallback
  - 代码中保留 MOCK_PHOTOS 等模拟数据变量
```

### 3. 数据库内容（核心铁律）

```
✅ 允许进入数据库的内容：
  - AI生成的新闻/资讯（必须标注 "AI生成" 或 "AI创作"）
  - 基于真实信源生成的报道
  - AI的独立观点/评论

❌ 禁止进入数据库的内容：
  - 完全虚构的赛事（不存在的杯赛/联赛）
  - 完全虚构的俱乐部/战队
  - 完全虚构的选手/队员
  - 完全虚构的比赛结果
  - 任何"看起来像真但其实是假"的数据
```

**简单区分：**
- AI写的新闻 → ✅ 可以进，但要标注
- 虚构的队伍/选手/比赛 → ❌ 绝对不行

### 4. 用户认证系统
```
✅ blast-auth-api 端点:
  - POST /register - 注册（email + password + nickname）
  - POST /login - 登录（email + password）
  - GET /verify?token=xxx - 验证token
  - GET /user?token=xxx - 获取用户信息
  - PUT /username - 修改昵称（需认证，限1次）
  - POST /logout - 退出登录
  - GET /online - 获取在线用户列表
  
✅ 数据存储:
  - 用户信息: D1 (blast-user-db.users)
  - Session/在线状态: KV (sess:xxx, online:xxx)
  
✅ 密码: SHA256 哈希存储，6位数字
```

### 5. API 改动
```
❌ 禁止:
  - 修改 API_BASE 地址
  - 移除已有的端点
  - 改变数据源绑定
```

### 5. 邮件发送（验证码/通知）
```
✅ 正确方式:
  - 使用 Resend API 发送邮件
  - API Key 存为 Cloudflare Secret（wrangler secret put）
  - 验证码必须存 KV（10分钟有效期）
  
❌ 错误方式:
  - 把 API Key 硬编码在代码里
  - 不存储验证码直接比较
  - 使用不安全的邮件服务

示例（Resend）:
  npx wrangler secret put RESEND_API_KEY  # 部署时执行
  
  # 代码中通过 env.RESEND_API_KEY 访问
  fetch('https://api.resend.com/emails', {
    headers: { 'Authorization': `Bearer ${env.RESEND_API_KEY}` }
  })
```

### 6. 网站性能优化（2026-03-24）
```
✅ 正确做法:
  - 首页首屏只加载必要数据，控制在3秒内
  - 大量数据用按需加载（如Poster页面tags）
  - 并行请求用 Promise.all，串行用 for await...of
  - 资源404要用前端兜底（onerror隐藏）
  - 同一个函数不要调用两次

❌ 错误做法:
  - 一次性串行请求所有数据（如 for循环 await fetch）
  - 页面加载时预加载不需要的数据
  - 重复调用同一个初始化函数
  - 资源404时不处理，让它报错
```

---

## 🟡 修改前必须确认

1. **修改任何 Worker API** → 必须验证 CORS 配置正确
2. **修改任何前端页面** → 必须验证字段映射正确
3. **新增数据展示** → 必须确认来源是 D1/R2/KV，禁止硬编码

---

## ✅ 验证命令

每次部署后必须执行：

```bash
# 1. 验证 CORS
curl -I https://blast-homepage-api.kanjiaming2022.workers.dev/ \
  -H "Origin: https://blastjunior.com" -X OPTIONS | grep access-control
curl -I https://blast-auth-api.kanjiaming2022.workers.dev/ \
  -H "Origin: https://blastjunior.com" -X OPTIONS | grep access-control

# 2. 验证 API 数据
curl -s https://blast-homepage-api.kanjiaming2022.workers.dev/ | jq '.data.news | length'

# 3. 验证 Gallery (从D1)
curl -s https://blast-homepage-api.kanjiaming2022.workers.dev/gallery | jq '.categories'

# 4. 验证用户系统
curl -s -X POST https://blast-auth-api.kanjiaming2022.workers.dev/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"123456"}' | jq '.ok'

# 5. 验证在线用户
curl -s https://blast-auth-api.kanjiaming2022.workers.dev/online | jq '.ok'

# 6. 验证网站状态
curl -s -o /dev/null -w "%{http_code}" https://blastjunior.com
```

---

## 📝 历史教训

1. **禁止硬编码数据** - 数据必须来自D1/R2/KV
2. **CORS格式** - 必须单域名，禁止空格分隔
3. **字段映射** - 前端必须匹配API返回字段
4. **占位数据** - 宁缺毋滥，不展示假数据
5. **Gallery数据源** - 从R2读取，不从D1伪造
6. **单API原则** - 所有端点走blast-homepage-api

---

## 📝 文档同步原则（最高优先级）

> 任何代码/配置变更后，必须立即更新对应文档

### 变更即记录

| 变更类型 | 必须更新的文档 |
|----------|---------------|
| API 新增/删除/修改 | BLXST-knowledge-graph.md |
| 规则新增/修改 | BLXST-rules.md |
| 功能完成/进度变化 | BLXST-status.md |
| HADO 新知识 | knowledge/hado-business.md |

### 同步时机

1. **实时同步** - 每次变更后立即记录
2. **手动同步** - 使用 `/blxst-sync` 命令查漏补缺
3. **定期同步** - 每天启动/下线前执行

### /blxst-sync 命令

```
触发: /blxst-sync 或 /sync

流程:
1. 检查所有 md 文件状态
2. 列出需要同步的内容
3. 等待老K逐条确认
4. 执行同步
5. 汇报完成
```

### 铁律

**变更未记录 = 变更未完成**

---

## 📝 更新日志

- 2026-03-10: 从 BLXST-config-protection.md 拆分独立成本文件
- 2026-03-10: 新增文档同步原则
- 2026-03-10: 新增数据库内容铁律（AI生成新闻 vs 虚构数据）

---

## ⚙️ 项目执行规范

### 1. 精简原则
- 只记录关键信息，不放完整代码或长文本
- 项目文件保持简洁

### 2. 同步原则
- 每次 `/sync` 检查文件是否有更新
- **新增Skill → 必须更新 BLXST-knowledge-graph.md**
- 关键决策必须写下来

### 3. 浏览器操作原则
- 先明确目标，带着问题去操作
- 一次性获取足够信息再分析

### 4. 迭代原则
- 每次只设定一个小目标
- 不追求一次做完，先快速迭代

### 5. 存档原则
- 每次会话结束前，更新项目进度
- 使用 `/sync` 命令确保文档同步

---

## 🔧 开发规范（Spawn时必须分配）

### 子智能体 Spawn 规则分配

| 场景 | Architect | Design Reviewer | Coder | Tester |
|------|-----------|-----------------|-------|--------|
| **新功能设计** | ✅ 全部规则 | ✅ 全部规则 | - | - |
| **代码开发** | - | - | ✅ 全部规则 | - |
| **测试验收** | - | - | - | ✅ 全部规则 |

### 开发时必检清单（Coder & Tester）

每次开发/测试完成后必须验证：

- [ ] API 调用能正常工作吗？（CORS配置正确）
- [ ] CORS 配置正确了吗？（只允许 blastjunior.com）
- [ ] 数据来自 D1/R2/KV 吗？（禁止硬编码）
- [ ] 字段映射正确吗？（前端匹配API返回字段）
- [ ] 真实浏览器打开看过了吗？（用 agent-browser）

### 前端开发铁律

1. **开发前端时，必须同步确认后端API配置完整**
   - 包括 CORS、认证、数据返回格式
   
2. **API 契约必须文档化**
   ```markdown
   ## API 要求
   - 需返回 Access-Control-Allow-Origin: https://blastjunior.com
   - Content-Type: application/json
   - 返回字段必须包含: id, name, ...
   ```

3. **禁止假设后端已配置**
   - 不能假定"API已经好了"
   - 必须验证实际可用

### 测试时必检（Tester）

1. **真实环境测试** - 不能只看代码
2. **用 agent-browser 验证** - 打开页面看控制台
3. **检查 CORS 错误** - 控制台不能有 CORS 报错

---

## 📝 更新日志

- 2026-03-10: 从 BLXST-config-protection.md 拆分独立成本文件
- 2026-03-10: 新增文档同步原则
- 2026-03-10: 新增数据库内容铁律（AI生成新闻 vs 虚构数据）
- 2026-03-16: 新增开发规范（Spawn规则分配 + 开发/测试必检清单）
- 2026-03-18: 更新照片API规则（D1元数据）、新增用户认证系统规则
