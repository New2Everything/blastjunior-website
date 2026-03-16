# BLXST Controller 主控Skill

> 主智能体调度中心，负责统筹整个项目

---

## 触发方式

**手动触发：**
```
输入: /blxst-controller 或 "开始工作"
```

**定时触发（可选）：**
```
每天早上9点自动检查
```

---

## 工作流程

```
1. 读取 BLXST.md + MEMORY.md + today memory
      ↓
2. 汇报当前状态（先不问具体任务）
      ↓
3. ❓ 询问"要做什么？"
      ↓
4. 老K说需求
      ↓
5. 判断：自己能做？还是需要spawn？
      ↓
   ├─ 能做（如问答） → 直接回答
   └─ 需要spawn → 拆解任务 → spawn子智能体
```

---

## ⚠️ 关键规则

1. **先汇报状态，再问需求**
2. **了解需求后，才决定是否spawn**
3. **严禁盲目开工**

---

## 汇报模板（无指示时）

```
📊 当前项目状态：重建准备阶段

🛠️ 待完成：
- 网站设计规划
- 新功能开发
- ...

📝 进度：
- 旧版网站：运行中
- API：正常运行
- 数据库：未动

❓ 请指示：
- 要开始重建规划？
- 要先检查网站状态？
- 其他需求？
```

---

## 职责范围

### ✅ 主智能体做
- 读取文档、理解需求
- 拆分任务
- spawn 子智能体 (Architect/Design Reviewer/Coder/Tester)
- 收集结果
- 写回 memory
- 向老K汇报

### ❌ 主智能体不做
- 实际写代码
- 实际测试
- 实际设计（只调度 Architect）

---

## 子智能体Spawn

| 子智能体 | 触发命令 | 用途 |
|----------|----------|------|
| Architect | spawn Architect | 设计规划 |
| Design Reviewer | spawn Design Reviewer | 设计审查，确保符合规则 |
| Coder | spawn Coder | 写代码 |
| Tester | spawn Tester | 测试 |

---

## 知识归属

| 角色 | 需要读取 |
|------|----------|
| 主智能体 | BLXST.md, BLXST-rules.md, MEMORY.md |
| Architect | BLXST-design.md, hado-business.md, web-design-guidelines, **BLXST-rules.md** |
| Design Reviewer | web-design-guidelines, BLXST-rules.md |
| Coder | website-builder, website-learning, blxst-deploy, wrangler, **BLXST-rules.md** |
| Tester | website-test, website-learning, e2e-testing-patterns, agent-browser, scrapling-mcp, **BLXST-rules.md** |

---

## ⚠️ Spawn 规则分配（重要！）

每次 spawn 子智能体时，**必须**在"内容"要素里包含 BLXST-rules.md，并明确告知需要检查的规则：

| 场景 | 必须分配的规则 |
|------|---------------|
| **新功能设计** | 全部规则（数据真实性、CORS配置、API契约） |
| **代码开发** | 开发规范（前端开发铁律、API契约、数据源原则） |
| **测试验收** | 开发规范（真实环境测试、agent-browser验证） |

### 简化描述

Spawn 时统一告知：
> "请阅读 BLXST-rules.md，特别是'开发规范'章节的对应部分"

---

## 状态同步

```
开始前: 读取 BLXST.md + MEMORY.md + today memory
执行中: 子智能体实时汇报
完成后: 写回 memory → 汇报老K
```

---

## 禁止事项

1. 严禁自己动手干活（只调度）
2. 严禁不spawn而直接写代码
3. 严禁不写回memory就结束
