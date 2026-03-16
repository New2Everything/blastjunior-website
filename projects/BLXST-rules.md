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

### 前端字段映射
- 前端必须严格匹配 API 返回的字段名
- 禁止在代码里改字段映射，必须改 API 返回值

---

## 🚫 禁止事项

### 1. CORS 配置
```
✅ 正确:
  Access-Control-Allow-Origin: https://blastjunior.com
  
❌ 错误:
  - 空格分隔多域名: "https://blastjunior.com https://www.blastjunior.com"
  - 通配符: "*"
```

### 2. 数据展示
```
❌ 禁止:
  - 伪造占位数据填充空内容
  - 硬编码战队/选手列表
  - Gallery 数据从 D1 伪造（必须从 R2 读取）
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

### 4. API 改动
```
❌ 禁止:
  - 修改 API_BASE 地址
  - 移除已有的端点
  - 改变数据源绑定
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

# 2. 验证 API 数据
curl -s https://blast-homepage-api.kanjiaming2022.workers.dev/ | jq '.data.news | length'

# 3. 验证 Gallery (必须从 R2)
curl -s https://blast-homepage-api.kanjiaming2022.workers.dev/gallery | jq '.data | length'

# 4. 验证网站状态
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
