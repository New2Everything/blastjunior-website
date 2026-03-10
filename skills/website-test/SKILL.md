---
name: website-test
description: |
  网站自动化测试技能。用于开发和部署后自动检测bug、性能问题、用户体验问题、数据来源问题。
  使用场景：(1)每次部署后自动测试 (2)回归测试 (3)性能基准验证 (4)UI bug排查 (5)数据来源验证
  配套工具：agent-browser（必须结合使用！）
  前置条件：需要配置目标网站URL和API端点
---

# Website Test Skill

自动化测试网站，检测bug、性能问题、数据来源问题，实现无人值守测试。

## ⚠️ 重要：必须结合两个Skill使用！

| Skill | 用途 | 必须使用 |
|-------|------|----------|
| **website-test** | 自动化脚本测试（API/性能/数据） | ✅ |
| **agent-browser** | 浏览器深度检测（截图/控制台/UI） | ✅ |

**两者结合才能全面发现问题**，单一工具可能遗漏问题。

---

## 快速开始（完整测试流程）

```bash
# 第1步：自动化脚本测试
SITE_URL=https://blastjunior.com API_BASE=https://api.example.com bash skills/website-test/scripts/run_tests.sh

# 第2步：agent-browser深度检测（必须！）
agent-browser open "https://blastjunior.com"
agent-browser screenshot
agent-browser errors
```

## 测试维度

### 1. website-test（自动化脚本）
- 功能测试
- 性能测试
- 数据来源验证

### 2. agent-browser（浏览器检测）
- 页面截图
- 控制台错误检测
- UI元素验证（加载状态/undefined检测）

---

## 快速开始

```bash
# 运行完整测试套件（功能+性能+数据）
SITE_URL=https://example.com API_BASE=https://api.example.com bash skills/website-test/scripts/run_tests.sh

# 仅测试数据来源（核心！）
SITE_URL=https://example.com API_BASE=https://api.example.com bash skills/website-test/scripts/data_test.sh

# 仅测试性能
SITE_URL=https://example.com bash skills/website-test/scripts/perf_test.sh

# 仅测试功能+UI
SITE_URL=https://example.com bash skills/website-test/scripts/func_test.sh

# 深度UI测试（agent-browser）
SITE_URL=https://example.com bash skills/website-test/scripts/ui_test.sh
```

## 配置说明

测试前需要配置以下环境变量：

| 变量 | 说明 | 示例 |
|------|------|------|
| SITE_URL | 网站地址 | https://blastjunior.com |
| API_BASE | API基础URL | https://blast-homepage-api.kanjiaming2022.workers.dev |
| PAGES | 页面列表 | home,matches,teams,players,standings |

---

## 测试维度

### 1. 功能测试
- 导航跳转
- 表单提交（报名/登录）
- 筛选/搜索
- 详情页数据加载

### 2. UI/视觉测试（agent-browser）
- 元素显示（无undefined/空白）
- 控制台JS错误检测
- 图片加载失败检测
- 响应式布局

### 3. 性能测试
- 首屏加载时间
- API响应时间
- 与SLO对比

### 4. 数据来源测试（核心！）

**方法一：通过Flag标记识别**
- 读取前端代码，识别 `<!-- DATA_MODULE: xxx -->` 标记
- 验证标记区域的数据来自API

**方法二：通过语义分析识别**
- 自动识别页面中的动态数据区域
- 验证数据来自API

**验证规则**：
| 数据类型 | 定义 | 正确来源 |
|----------|------|----------|
| **可变化数据** | 赛果/积分/比赛记录 | D1/R2 → Worker API |
| **可统计数据** | 在线人数/浏览量 | R2/KV → Worker API |
| **可追溯数据** | 积分榜/排名 | D1 → Worker API |
| **品牌表达** | Slogan/介绍文字 | 静态HTML（允许占位） |

### 5. 回归测试
- 新功能不破坏旧功能
- 关键路径完整性

---

## 性能基准（SLO）

详见 references/slo.md：

| 场景 | 指标 | 目标 |
|------|------|------|
| 首页首屏 | 可交互时间 | ≤2.5s |
| 详情页 | 主要信息出现 | ≤2.0s |
| API-首页聚合 | 响应时间P95 | ≤300ms |
| API-搜索 | 响应时间P95 | ≤700ms |
| 图片加载 | 失败率 | ≤0.5% |

---

## 测试脚本

- `run_tests.sh` - 完整测试套件
- `data_test.sh` - 数据来源验证（核心！）
- `func_test.sh` - 功能测试
- `perf_test.sh` - 性能测试
- `ui_test.sh` - UI深度测试（agent-browser）

---

## 数据验证规则

### 必须来自API的数据（禁止硬编码）
- 战队名称、选手名称、比赛比分
- 积分榜数据、射手榜数据
- 新闻标题、赛事报道
- 相册列表、照片
- 在线人数、统计数据

### 允许占位的数据
- Slogan
- 介绍文字
- 固定导航文案
- 版权声明

---

## 定时自动测试

配置cron实现部署后自动测试：

```bash
# 每天下午6点自动测试
0 18 * * * cd /workspace && \
  SITE_URL=https://example.com API_BASE=https://api.example.com \
  bash skills/website-test/scripts/run_tests.sh >> test-reports/cron.log 2>&1
```

---

## 报告输出

测试结果生成在 `test-reports/` 目录：
- `test-results.json` - 详细测试数据
- `test-summary-YYYYMMDD.txt` - 简洁摘要
- `screenshots/` - 失败截图

---

## 无人化检查清单

部署后自动执行：
1. ✅ 页面访问测试
2. ✅ API响应测试
3. ✅ 性能SLO对比
4. ✅ 数据来源验证（Flag标记 + 语义分析）
5. ✅ 控制台JS错误检测（agent-browser）
6. ✅ UI视觉检测（agent-browser截图）

---

## 9. 最佳实践检测（P0！）

**每次测试必须检测是否符合最佳实践**，详见 `references/best-practices.md`

### 9.1 路由架构

| 检测项 | 要求 | 检测方法 |
|--------|------|----------|
| URL无.html后缀 | 详情页应为 `/team/xxx` 而非 `/team.html?id=xxx` | URL正则 |
| SPA路由正确 | fallback指向index.html | 配置检查 |

### 9.2 数据加载

| 检测项 | 要求 | 检测方法 |
|--------|------|----------|
| 无硬编码数据 | 禁止 `const teams = [...]` 硬编码 | 源码扫描 |
| 加载状态正常 | 有loading/骨架屏 | agent-browser |

### 9.3 页面Title

| 检测项 | 要求 | 检测方法 |
|--------|------|----------|
| title唯一 | 每个页面title应包含关键信息 | 源码检测 |
| 动态title | 详情页title应包含对象名 | agent-browser |

### 9.4 检测命令

```bash
# 最佳实践专项检测
SITE_URL=https://blastjunior.com bash skills/website-test/scripts/best_practice_test.sh
```

### 9.5 最佳实践完整清单

| 类别 | # | 检测项 | 要求 | 检测方法 |
|------|---|--------|------|----------|
| **路由** | 1 | 无.html后缀 | 详情页URL不含.html | 访问404检测 |
| **路由** | 2 | SPA fallback | 所有路由 fallback 到 index.html | 配置检测 |
| **数据** | 3 | 无硬编码 | 禁止 const teams = [...] | 源码扫描 |
| **数据** | 4 | API获取 | 使用 fetch() 获取数据 | 源码扫描 |
| **数据** | 5 | 加载状态 | 有loading/空状态提示 | agent-browser |
| **SEO** | 6 | title正确 | 首页title包含品牌名 | 源码检测 |
| **SEO** | 7 | 动态title | 详情页title包含对象名 | 源码检测 |
| **UX** | 8 | 无JS错误 | 控制台无错误 | agent-browser |
| **UX** | 9 | 无undefined | 页面无undefined文本 | agent-browser |
| **安全** | 10 | HTTPS | 全站HTTPS | 跳转检测 |

### 9.6 违反示例

**❌ 错误**：
- `/team-detail.html?id=TEAM002`（多HTML文件）
- `const teams = [{name: "A"}]`（硬编码数据）
- `title="战队详情"`（无关键信息）
- 页面显示 "undefined"

**✅ 正确**：
- `/team/TEAM002`（SPA路由）
- `fetch(API_BASE + '/teams')`（API获取）
- `title="AKA - 兰星少年"`（动态title）
- 有loading状态，无undefined
