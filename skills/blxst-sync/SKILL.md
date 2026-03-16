# BLXST Sync Skill

> 用于同步项目文档，确保新session能了解过去的变更

## 触发方式

- 输入 `/blxst-sync` 或 `/sync`
- 每次新session开始时（确保信息同步）

---

## 执行流程

### 步骤1：扫描变更

**扫描以下目录：**

| 目录 | 扫描内容 |
|------|----------|
| projects/*.md | 项目文件变更 |
| knowledge/*.md | 知识文件变更 |
| skills/*/SKILL.md | 技能变更 |

**命令：**
```bash
# 扫描文件修改时间
find /root/.openclaw/workspace/projects -name "*.md" -mtime -1
find /root/.openclaw/workspace/knowledge -name "*.md" -mtime -1
find /root/.openclaw/workspace/skills -name "SKILL.md" -mtime -1
```

### 步骤2：从上下文了解变化

从当前对话上下文（已加载的文件、已执行的命令）了解今天发生的变化：
- 哪些文件被修改了
- 哪些技能有变化
- 哪些知识有更新

### 步骤3：对比 status.md

读取 status.md，对比：
- 哪些文件已更新但 status 没记录
- 哪些技能有变化但 status 没记录
- 哪些知识有更新但 status 没记录

### 步骤4：列出需要同步的内容

```
🔍 发现以下需要同步到 status 的变更：

1. [文件/Skill] - [变更描述]
2. [文件/Skill] - [变更描述]
...

请确认是否同步，回复格式：
- "1,2,3" = 同步 1,2,3
- "全部" = 全部同步
- "跳过" = 暂不同步
```

### 步骤4：执行同步

确认后，更新 status.md，追加变更记录。

### 步骤5：完成汇报

```
✅ Sync 完成！

已同步到 status：
- [变更1]
- [变更2]

未同步：
- [原因]
```

---

## 注意事项

1. **必须扫描所有 md 和 skill** - 不能硬编码文件名
2. **对比 status.md** - 只同步未记录的变更
3. **必须逐条确认** - 不可以直接静默同步
4. **更新而非重写** - 只追加变更，不重写整个文件
