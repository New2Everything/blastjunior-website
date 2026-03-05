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

## 完整工作流程

### 1. 需求分析（需求定义）

在开始写代码前，必须明确：

- **网站类型**：俱乐部/社区/电商/媒体/企业官网/个人博客
- **目标用户**：青少年/商务人士/运动爱好者/游戏玩家
- **核心功能**：信息展示/用户交互/内容发布/电商交易
- **品牌调性**：热血/专业/简约/潮流/高端

> **产出**：一句话描述网站核心价值

---

### 2. 竞品调研（偷师学习）

**必须先看业界标杆，再谈创新。**

#### 2.1 搜索同类型知名网站

使用 Tavily 或 Google 搜索：
```
[网站类型] 官网 examples
例如：青少年体育俱乐部官网 examples
```

#### 2.2 分析维度

| 维度 | 看什么 |
|------|--------|
| **配色** | 主色调、辅色、渐变、对比度 |
| **布局** | 栅格系统、留白、层级 |
| **字体** | 标题字体、正文字体、字号层级 |
| **动效** | 加载动画、hover效果、滚动动画 |
| **交互** | 按钮样式、表单设计、导航逻辑 |
| **图片** | banner图风格、人物/产品图处理 |

#### 2.3 记录借鉴点

```
# 调研笔记
- 网站: xxx.com
- 配色: 深蓝 + 橙色渐变
- 亮点: 顶部大banner + 动态粒子背景
- 可借鉴: 导航栏吸顶 + 搜索框动画
```

---

### 3. 设计决策

基于调研结果，确定：

#### 3.1 视觉规范

```
主色调: #00d4ff (科技蓝)
辅色调: #ff6b35 (活力橙)
背景色: #0a0e17 (深空黑)
文字色: #ffffff / #8b9dc3
```

#### 3.2 字体选择

```
标题: Orbitron (科技感)
正文: Noto Sans SC (中文兼容)
```

#### 3.3 组件清单

列出需要的所有组件：
- [ ] 导航栏
- [ ] Hero区域
- [ ] 内容卡片
- [ ] 聊天窗口
- [ ] 登录注册
- [ ] 页脚

---

### 4. 开发流程

#### 4.1 项目结构

```
/workspace
  /index.html      # 首页
  /styles.css      # 样式
  /app.js         # 逻辑
  /assets/        # 图片资源
```

#### 4.2 HTML结构原则

```html
<!-- 语义化标签 -->
<header>导航</header>
<main>主要内容</main>
<footer>页脚</footer>

<!-- 命名规范 -->
<div class="hero-section">
  <h1 class="hero-title">标题</h1>
</div>
```

#### 4.3 CSS规范

```css
/* 使用CSS变量 */
:root {
  --primary: #00d4ff;
  --bg-dark: #0a0e17;
}

/* 组件化 */
.card { ... }
.card:hover { ... }

/* 响应式 */
@media (max-width: 768px) { ... }
```

#### 4.4 JavaScript规范

```javascript
// 模块化
const App = {
  init() { ... },
  loadData() { ... }
};

// 事件委托
document.addEventListener('click', (e) => { ... });
```

---

### 5. 部署流程

#### 5.1 提交代码

```bash
git add .
git commit -m "feat: 添加首页"
git push origin main
```

#### 5.2 Cloudflare Pages 部署

触发部署：
```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -d '{"branch": "main"}' \
  "https://api.cloudflare.com/.../pages/projects/{name}/deployments"
```

#### 5.3 验证

访问网站，确认：
- [ ] 页面加载正常
- [ ] 功能可点击
- [ ] 无控制台错误

---

### 6. 测试与迭代

**每改必测，测试驱动开发。**

#### 6.1 自动化测试

使用 agent-browser：

```bash
# 打开页面
agent-browser open https://example.com

# 截图检查
agent-browser screenshot

# 检查错误
agent-browser errors

# 点击测试
agent-browser click @e1

# 填表测试
agent-browser fill @e2 "text"
```

#### 6.2 测试清单

| 测试项 | 方法 |
|--------|------|
| 页面加载 | 截图确认 |
| 按钮点击 | agent-browser click |
| 表单提交 | 填写并提交 |
| 响应式 | 调整浏览器宽度 |
| 控制台错误 | agent-browser errors |

#### 6.3 迭代循环

```
开发 → 部署 → 测试 → 发现问题 → 回到开发 → 重新部署 → 再次测试
```

---

### 7. 升级机制

**三次原则**

> 同一个Bug尝试3次无法解决 → 必须汇报给老K

汇报格式：
```
问题: [描述]
尝试: [已尝试的解决方案]
现状: [当前状态]
需要帮助: [具体需要什么]
```

---

## 常用技术栈

### 前端

- **纯HTML/CSS/JS** - 简单快速，适合静态站
- **React/Vue** - 适合复杂交互
- **Tailwind CSS** - 快速样式开发

### 后端（Cloudflare）

- **Workers** - API服务
- **KV** - 键值存储（用户、会话）
- **D1** - SQL数据库
- **R2** - 文件存储
- **Pages** - 静态托管

---

## 常用命令速查

```bash
# 部署到Cloudflare Pages
wrangler pages deploy ./dist

# 部署Worker
wrangler deploy

# 测试D1
wrangler d1 execute database --local --command="SELECT * FROM users"

# 列出KV
wrangler kv:namespace list
```

---

## 常见问题

### Q: 不知道做什么风格？

A: 先搜索同类型知名网站，模仿学习后再创新。

### Q: 遇到技术难题怎么办？

A: 
1. 尝试3次解决
2. 记录尝试过程
3. 汇报给老K

### Q: 如何提升设计感？

A: 
1. 参考知名品牌官网
2. 使用渐变和动效
3. 注意留白和层级
4. 图片质量要过关

---

## 检查清单

开始新项目时，确认：

- [ ] 明确网站类型和目标用户
- [ ] 调研了至少3个同类型网站
- [ ] 确定了配色和字体
- [ ] 规划了需要的组件
- [ ] 建立了开发环境
- [ ] 设置了测试流程

