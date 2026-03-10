---
name: website-builder
description: 网站建设完整工作流 - 从需求分析到部署上线
read_when:
  - 需要建设新网站
  - 需要改进现有网站
  - 需要设计网站UI
metadata: {"openclaw":{"emoji":"🏗️","requires":{}}}
---

# Website Builder - 网站建设全流程

## 核心原则

**网站建设的本质是解决问题。始终围绕用户需求来设计。**

---

## ⚠️ 数据分离原则（必须遵守）

在开发任何数据展示功能时，必须严格区分：

| 数据类型 | 定义 | 数据来源 | 访问方式 |
|----------|------|----------|----------|
| **可变化数据** | 赛果/积分/比赛记录/用户生成内容 | D1/R2/KV | 必须经由Worker API |
| **可统计数据** | 在线人数/浏览量/计数 | D1/KV | 必须经由Worker API |
| **可追溯数据** | 积分榜/排名/历史记录 | D1/R2 | 必须经由Worker API |
| **品牌表达** | Slogan/介绍文字/口号/导航标签 | 静态 | 允许占位，直接渲染 |

**规则**：
1. 所有变化数据必须经由Worker API，禁止前端直连D1/R2/KV
2. 品牌表达文字允许占位，与数据模块严格隔离
3. **真实数据禁止伪造** - D1/R2/KV中的数据是真实事件

---

## 完整工作流程

### 流程图

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│    设计     │ ──▶ │    开发     │ ──▶ │    部署     │ ──▶ │    测试     │
│  查白皮书   │     │  写代码     │     │ Pages/Worker│     │ 自动+人工   │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │                   │
       ▼                   ▼                   ▼                   ▼
  查数据库设计          用wrangler           验证部署            用website-test
  请求老K提供           工具/agent           是否成功             + agent-browser
```

---

## 1. 设计阶段

### 1.1 查询设计白皮书

首先检查项目目录下是否有设计白皮书：

```bash
# 查看项目设计文档
ls projects/*design*.md
```

**如果白皮书存在**，读取并遵循其中的：
- 数据结构设计
- 页面规划
- 功能定义
- SLO性能指标

**如果需要数据库信息**：
1. 先查现有D1数据库设计（见下方数据库部分）
2. 如无对应设计，**必须询问老K提供**

### 1.2 需求确认

明确以下内容：
- **网站类型**：俱乐部/社区/电商/媒体/企业官网
- **目标用户**：青少年/商务人士/运动爱好者
- **核心功能**：信息展示/用户交互/内容发布
- **品牌调性**：热血/专业/简约/潮流

> **产出**：一句话描述网站核心价值

---

## 2. 开发阶段

### 2.1 技术栈

| 类型 | 技术 | 用途 | 访问方式 |
|------|------|------|----------|
| **后端** | Workers | API服务 | 直接部署 |
| **后端** | D1 | SQL数据库 | 通过wrangler CLI |
| **后端** | KV | 键值存储 | Workers绑定 |
| **后端** | R2 | 文件存储 | Workers绑定 |
| **前端** | Pages | 静态托管 | wrangler pages deploy |
| **开发工具** | cursor-cli | 代码编辑/AI编程 | cursor-agent |
| **开发工具** | agent-browser | 浏览器自动化 | agent-browser |

### 2.2 开发工具使用

**cursor-cli** - AI编程助手：
```bash
# 让Cursor AI帮你写代码
cursor-agent -p "帮我写一个登录表单" --mode=ask

# 用Cursor打开文件
cursor --goto file.py:10
```

**agent-browser** - 浏览器自动化：
```bash
# 打开页面测试
agent-browser open https://example.com

# 截图
agent-browser screenshot
```

### 2.3 D1数据库操作

**必须使用wrangler CLI操作D1**：

```bash
# 列出D1数据库
wrangler d1 list

# 执行SQL查询
wrangler d1 execute <database-name> --command="SELECT * FROM users" --remote

# 查看表结构
wrangler d1 execute <database-name> --command="PRAGMA table_info(table_name)" --remote
```

### 2.3 项目结构

```
/workspace
  /index.html      # 首页
  /matches.html    # 比赛页
  /teams.html     # 战队页
  /players.html   # 选手页
  /wrangler.toml  # Worker配置
```

### 2.4 开发规范

#### 数据模块Flag标记（重要！）

在前端代码中，**必须**对数据模块展示区域进行flag标记，方便后续测试识别：

```html
<!-- DATA_MODULE: teams_list -->
<div class="teams-grid" id="teamsGrid">
  <!-- 战队数据将在这里渲染 -->
</div>

<!-- DATA_MODULE: players_list -->
<div class="players-grid" id="playersGrid">
  <!-- 选手数据将在这里渲染 -->
</div>

<!-- DATA_MODULE: matches_list -->
<div class="matches-list" id="matchesList">
  <!-- 比赛数据将在这里渲染 -->
</div>

<!-- DATA_MODULE: news_feed -->
<div class="news-feed" id="newsFeed">
  <!-- 新闻数据将在这里渲染 -->
</div>
```

**规则**：
1. 每个动态数据渲染区域，都要用 `<!-- DATA_MODULE: 模块名 -->` 标记
2. 模块名要语义化：`news_list`, `teams`, `players`, `standings`, `gallery` 等
3. 禁止在DATA_MODULE区域硬编码数据（如 `<div>战队A</div>`）
4. 品牌表达区域不需要标记（如 `<h1>关于我们</h1>`）

#### 前端调用API

```javascript
// 前端调用API
const API_BASE = 'https://xxx.workers.dev';
const data = await fetch(API_BASE + '/data').then(r => r.json());
```

```javascript
// Worker API读取D1
const result = await env.DB.prepare("SELECT * FROM table").all();
```

---

## 3. 部署阶段

### 3.1 部署静态页面

```bash
# 部署到Cloudflare Pages
wrangler pages deploy . --project-name=your-project
```

### 3.2 部署Worker API

```bash
# 部署Worker
wrangler deploy
```

### 3.3 验证部署

```bash
# 验证网站可访问
curl -I https://your-domain.com

# 验证API可访问
curl https://your-worker.workers.dev/
```

---

## 4. 测试阶段

### 4.1 使用 website-test Skill

**自动测试脚本**（推荐）：

```bash
# 完整测试（功能+性能+数据）
bash skills/website-test/scripts/run_tests.sh

# 数据来源测试
bash skills/website-test/scripts/data_test.sh

# UI测试
bash skills/website-test/scripts/ui_test.sh

# 性能测试
bash skills/website-test/scripts/perf_test.sh
```

### 4.2 使用 agent-browser

**手动测试**：

```bash
# 打开页面
agent-browser open https://example.com

# 截图
agent-browser screenshot

# 检查控制台错误
agent-browser errors

# 点击测试
agent-browser click @element

# 填表测试
agent-browser fill @input "value"
```

### 4.3 三次原则

> 同一个Bug尝试3次无法解决 → 必须汇报给老K

汇报格式：
```
问题: [描述]
尝试: [已尝试的解决方案]
现状: [当前状态]
需要帮助: [具体需要什么]
```

---

## 数据库设计

### 查询现有D1

首先检查Cloudflare上的D1数据库：

```bash
# 列出所有D1
CLOUDFLARE_API_TOKEN="xxx" CLOUDFLARE_ACCOUNT_ID="xxx" wrangler d1 list

# 查看表
wrangler d1 execute <db-name> --command="SELECT name FROM sqlite_master WHERE type='table'" --remote
```

### 获取数据库信息

**如果设计白皮书中有数据库设计**，按其执行。

**如果没有**，必须询问老K：
- 需要哪些表？
- 表结构是什么？
- 数据从哪里来？

---

## 常用命令速查

```bash
# 部署
wrangler pages deploy . --project-name=xxx
wrangler deploy

# D1操作
wrangler d1 list
wrangler d1 execute <db> --command="SQL" --remote

# KV操作
wrangler kv namespace list
wrangler kv namespace create <name>

# R2操作
wrangler r2 bucket list
```

---

## 检查清单

开始新项目时，确认：

- [ ] 读取设计白皮书（如有）
- [ ] 明确数据库需求，如无则询问老K
- [ ] 确定技术栈
- [ ] 开发功能
- [ ] 部署测试
- [ ] 使用 website-test 进行自动化测试
- [ ] 验证通过后交付
