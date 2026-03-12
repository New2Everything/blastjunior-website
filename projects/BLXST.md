# BLXST - 兰星少年俱乐部官网

## 🚧 当前状态：重建准备阶段

> 旧版仍可访问：https://blastjunior.com

---

## 📚 必读文件（每次打开项目必读）

| 优先级 | 文件 | 用途 |
|--------|------|------|
| ⭐⭐⭐ | `BLXST-knowledge-graph.md` | 现状图谱 - 现在有什么 |
| ⭐⭐⭐ | `BLXST-rules.md` | 建站铁律 - 禁止事项+架构原则 |
| ⭐⭐⭐ | `BLXST-status.md` | 项目进度 - 当前状态 |
| ⭐⭐⭐ | `BLXST-controller-handbook.md` | 主控工作手册 - 必须遵守 |
| ⭐⭐ | `knowledge/hado-business.md` | HADO业务规则 |
| ⭐⭐ | `knowledge/hado-resources.md` | HADO资源链接 |

---

## 🎯 重建工作流

```
1. 读取 knowledge-graph → 了解现状
2. 读取 rules → 明白铁律
3. 读取 status → 知道进度
4. 规划新功能 → 写 design.md
5. 开发 → 测试 → 部署
```

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
2. **单API架构** - 所有端点走 blast-homepage-api
3. **CORS规则** - 只允许 blastjunior.com，禁止通配符
4. **双Skill检测** - website-test + agent-browser 必须同时通过

---

## 🔄 同步机制

### /blxst-sync（或 /sync）

**每天必须执行一次**（睡前/下线前）

```
1. 检查所有 md 文件状态
2. 列出需要同步的内容
3. 等待老K逐条确认
4. 执行同步
5. 汇报完成
```

**原则：变更未记录 = 变更未完成**

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
