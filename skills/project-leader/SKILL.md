# Project Leader Skill

> AI项目管理制度化 - 让小虾成为合格的项目Leader

---

## 角色定义

| 角色 | 职责 |
|------|------|
| **Architect (小虾)** | 需求分析、设计方案、把控质量、项目管理 |
| **Coder** | 执行代码开发、部署 |
| **Tester** | 执行双SKILL检测、回归测试 |

---

## 项目管理流程

### 1. 需求处理

```
收到需求（老K）
      ↓
Architect分析需求
      ↓
需老K确认？→ 是 → 找老K确认 → 否 → 直接执行
      ↓
设计方案
      ↓
输出：功能规格文档
```

### 2. 开发执行

```
功能规格确定
      ↓
Coder开发 ← Parallel: Architect规划下一步
      ↓
Tester检测
      ↓
通过？→ 部署 → 完成
  ↓ 否
修复 → 重新检测
```

### 3. 交付标准

| 检查项 | 标准 |
|--------|------|
| 功能 | 符合规格文档 |
| 测试 | website-test + agent-browser 全部通过 |
| 数据 | 来自合法数据源（D1/R2/KV） |
| 性能 | 符合SLO基准 |

---

## 项目状态管理

### 状态文件

每个项目必须有 `projects/{项目名}-status.md`，包含：

```markdown
# {项目名} 状态

## 当前冲刺

| 任务 | 状态 | 负责人 |
|------|------|--------|
| 用户系统-API | 开发中 | Coder |
| 评论系统-数据库 | 已完成 | - |
| 聊天室-设计 | 待开始 | - |

## 待办

- [ ] 评论系统-前端
- [ ] 上传系统
- [ ] 聊天室

## 完成

- [x] 用户系统-数据库设计
- [x] 用户系统-API
```

### 状态更新规则

| 触发 | 操作 |
|------|------|
| 开始新任务 | 更新状态文件 + 会议纪要 |
| 完成功能 | 更新状态文件 + 标记完成 |
| 遇到问题 | 记录问题 + 会议纪要 |
| 交付完成 | 最终状态更新 + 项目报告 |

---

## 会议纪要规范

### 格式

```markdown
# 会议纪要 #{序号}

**日期**：YYYY-MM-DD HH:MM
**参与**：老K、小虾
**主题**：{主题}

### ✅ 决定

| 项目 | 决定 |
|------|------|
| xxx | xxx |

### 📌 待办

- [ ] xxx

### 📌 小虾决策（无需老K确认）

| 项目 | 决策 |
|------|------|
| xxx | xxx |
```

### 存档

- 路径：`memory/{YYYY-MM-DD}-meeting-{序号}.md`
- 每次会议后必须更新

---

## Coder管理

### 创建Coder

```bash
sessions_spawn \
  --runtime=subagent \
  --label=coder-{功能名} \
  --task="{任务描述}" \
  --model=minimax/MiniMax-M2.5
```

### 任务下达格式

```markdown
## 任务：{功能名}

### 目标
{具体目标}

### 规格
见 `projects/{项目名}-detailed-spec.md`

### 约束
1. 数据必须来自D1/R2/KV
2. 禁止硬编码
3. 必须包含加载状态

### 交付
1. Worker API代码
2. 前端页面
3. 数据库（如需）
```

### Coder状态跟踪

| 状态 | 含义 |
|------|------|
| 待开始 | 尚未分配 |
| 进行中 | 正在开发 |
| 待检测 | 开发完成，等待Tester |
| 已完成 | Tester通过 |

---

## Tester管理

### 创建Tester

```bash
sessions_spawn \
  --runtime=subagent \
  --label=tester-{功能名} \
  --task="测试{功能名}功能：..." \
  --model=minimax/MiniMax-M2.5
```

### 测试任务下达格式

```markdown
## 任务：测试{功能名}

### 测试范围
1. 功能测试
2. 数据来源验证
3. UI检测

### 站点
- 网站：https://blastjunior.com
- API：https://blast-homepage-api.kanjiaming2022.workers.dev

### 检测命令
```bash
# website-test
SITE_URL=https://blastjunior.com API_BASE=https://blast-homepage-api.kanjiaming2022.workers.dev \
bash skills/website-test/scripts/run_tests.sh

# agent-browser
agent-browser open "https://blastjunior.com"
agent-browser screenshot
agent-browser errors
```

### 通过标准
- website-test: 全部通过
- agent-browser: 无控制台错误
```

---

## 项目交付流程

### 交付检查清单

| # | 检查项 | 负责人 |
|---|--------|--------|
| 1 | 功能符合规格 | Coder → Architect |
| 2 | website-test通过 | Tester |
| 3 | agent-browser无错误 | Tester |
| 4 | 数据来自合法源 | Architect |
| 5 | 性能符合SLO | Tester |

### 交付报告

```markdown
# {功能名} 交付报告

## 状态：✅ 已交付

### 功能清单
- [x] 用户注册/登录
- [x] 评论系统

### 测试结果
| 测试项 | 结果 |
|--------|------|
| website-test | 10/10 通过 |
| agent-browser | 无错误 |

### 数据来源
| 模块 | 数据源 |
|------|--------|
| 评论 | blastjunior-content-db.comments |

### 部署
- API: 已部署
- 前端: 已部署
```

---

## 时间管理

### 每日必做

1. **晨间检查**（收到heartbeat时）
   - 查看Coder/Tester状态
   - 更新项目状态文件

2. **会议后**
   - 更新会议纪要
   - 更新项目状态

3. **功能完成后**
   - 更新项目状态
   - 记录交付报告

---

## 常用命令速查

```bash
# 查看当前项目状态
cat projects/{项目名}-status.md

# 查看会议纪要
ls memory/*meeting*

# 更新项目状态
edit projects/{项目名}-status.md
```

---

*持续更新中...*
