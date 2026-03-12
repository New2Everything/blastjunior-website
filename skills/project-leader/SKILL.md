# Project Leader 技能

> AI项目管理制度

---

## 触发方式

**手动触发：**
```
输入: /project-leader 或 "创建项目"
```

---

## 角色分工

| 角色 | 职责 |
|------|------|
| **Architect (小虾)** | 需求分析、设计方案、把控质量 |
| **Coder (subagent)** | 执行代码开发 |
| **Tester (subagent)** | 执行测试 |

---

## 项目管理

### 创建项目
```
1. 创建 projects/{项目名}.md
2. 创建 projects/{项目名}-status.md
3. 规划功能优先级
```

### 状态管理
每个项目必须有 `projects/{项目名}-status.md`

---

## Coder 任务下达

```bash
sessions_spawn \
  --runtime=subagent \
  --label=coder-{功能名} \
  --task="{任务描述}"
```

---

## Tester 任务下达

```bash
sessions_spawn \
  --runtime=subagent \
  --label=tester-{功能名} \
  --task="测试{功能名}功能"
```

---

## 交付标准

- 功能符合规格
- website-test 通过
- agent-browser 无错误
- 数据来自 D1/R2/KV
