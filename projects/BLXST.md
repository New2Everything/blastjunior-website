# BLXST - 兰星少年俱乐部官网

> **Description**: 项目入口文件，记录项目基本信息、状态和常用命令
> **维护规则**: 不要增加骨架，保持简洁

## 🚧 当前状态：Learning V2 自主改进阶段

> 旧版仍可访问：https://blastjunior.com
> 当前重点是建设 OpenClaw / Learning V2 的自学习、自进化、自改动网站系统。

---

## 📚 必读文件（每次打开项目必读）

> ⚡ 立即执行：bash /root/.openclaw/workspace/projects/.blxst-bootstrap.sh

---

## 🎯 Learning V2 自主改进工作流

```
1. 系统读取项目上下文、rules、state、history、patterns
2. 系统自主发现网站优化机会
3. 系统形成学习目的并寻找外部学习资源
4. 系统提炼 BLXST 专属学习结论
5. 系统生成低风险改动方案
6. dry-run / gate / scoped write
7. 自动验证 / outcome record / integrity / drift / secret check
8. commit / push / deploy 按当前 phase policy 和 gate 结果决定
```

原则：老K负责最高层方向、运行节奏、风险边界和阶段升级授权；direct deploy 永远禁止。

---

## 🔧 开发工具

| 工具 | 用途 |
|------|------|
| `website-builder` | 网站开发完整流程 |
| `website-test` | 自动化测试 |
| `agent-browser` | 浏览器深度检测 |
| `ai-news` | AI新闻生成 |
| `wrangler` | Cloudflare (D1/Workers/R2) |

---

## ⚠️ 核心原则（任何时候不能违反）

1. **数据真实性** - 数据必须来自 D1/R2/KV，禁止硬编码
2. **双API架构**:
   - `blast-api` - 用户创建的数据（战队/选手/新闻/积分）
   - `blast-homepage-api` - 俱乐部预存资产（257照片/赞助商等）
3. **CORS规则** - 允许 blastjunior.com + www + pages.dev，禁止通配符
4. **Gallery/R2** - 照片必须从 R2 读取，禁止从 D1 伪造
5. **双Skill检测** - website-test + agent-browser 必须同时通过

---

## 🔄 同步机制

### /blxst-sync（或 /sync）

**按阶段或循环结束时执行**

```
1. 系统检查 md / state / reports / snapshots 状态
2. 系统识别需要同步的上下文变化
3. 系统区分：可自治记录 / 需要阶段授权 / 高风险阻断
4. 系统写入必要记录
5. 系统汇报 diff、gate、结果和下一步
```

**原则：变更未记录 = 变更未完成。低风险上下文记录不应永久依赖老K逐条确认；阶段升级、风险边界变化、deploy 能力开放、高风险源码改动仍需明确授权。**

---

## 📍 常用链接

| 链接 | 地址 |
|------|------|
| 网站 | https://blastjunior.com |
| API | https://blast-homepage-api.kanjiaming2022.workers.dev |
| 知识库 | /root/.openclaw/workspace/knowledge/ |

---

## 📝 更新日志

- 2026-03-10: 重写为简洁入口，进入重建准备阶段
- 2026-03-12: 必读文件改为脚本触发
- 2026-05-27: 升级项目规则为 Learning V2 自治系统规则

## BLXST Project Operating Laws (Learning V2)

This section supersedes any older human-build-era project iron laws that conflict with Learning V2.

### Permanent architecture laws

- Keep BLXST as a static website on Cloudflare Pages plus Cloudflare Workers, D1, R2, and KV.
- Do not migrate BLXST to Next.js, SvelteKit, or any heavy framework unless a separate architecture migration is explicitly approved.
- Preserve the dual API model:
  - `blast-api`: user-created data such as teams, players, news, registrations, and standings.
  - `blast-homepage-api`: club-managed or preloaded assets such as homepage content, gallery photos, sponsors, and media assets.
- Real production data must come from approved runtime sources such as D1, R2, KV, and Workers.
- Do not hardcode fake production data.
- Production CORS must use an allowlist. Wildcard CORS is not allowed for production routes.
- Do not treat old isolated `worker/` drafts, `.wrangler` caches, raw research, raw evidence logs, local runtime state, or token-like files as commit candidates.
- Do not print, copy, summarize, commit, or spread secrets.

### Learning V2 autonomy laws

- The long-term goal is an autonomous learning, autonomous website improvement, and controlled self-evolution system.
- The system should be able to discover learning opportunities, form learning goals, collect external learning resources, distill BLXST-specific conclusions, propose changes, apply safe changes, validate them, and record outcomes.
- Human approval for every commit or push is no longer a permanent project law. It is a phase policy.
- Autonomous commit and push may be allowed only when the current mode allows it and the full gate chain passes:
  - opportunity discovery
  - external learning or research
  - BLXST-specific conclusion
  - proposal
  - dry-run
  - scoped source write
  - validation
  - outcome record
  - integrity check
  - drift check
  - secret check
  - push/deploy safety gate
- OldK's role should move upward over time:
  - set strategic direction
  - set operating cadence
  - set risk appetite
  - approve phase changes
  - intervene on exceptions or high-risk actions
- OldK should not be required to approve every low-risk routine push once autonomous gates are mature and explicitly enabled.
- Direct deployment remains forbidden.
- Controlled deployment is a separate capability and requires deploy mode, deploy gate, observer, rollback plan, and explicit phase authorization.
- `Cloudflare Pages production automatic deployments are paused` is runtime status, not a timeless project law. The system must read current deployment status before acting.

### Current phase policy

- Current phase: Learning V2 seventh round autonomous website improvement loop.
- Prefer low-risk HTML, CSS, and content-structure improvements.
- Preferred targets include homepage hierarchy, parent trust, CTA clarity, mobile experience,赛事氛围表达, and non-core information structure.
- Do not touch login, registration, upload review, D1 schema, Worker API behavior, R2 writes, admin flows, or production deploy unless a later phase explicitly opens that scope.
- Default maximum action size is one small target per cycle.
