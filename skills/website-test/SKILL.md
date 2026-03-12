---
name: website-test
description: |
  通用网站自动化测试技能。遵循E2E最佳实践。
  触发条件：(1) 用户要求测试网站 (2) 部署后验证 (3) /test-website
  
  依赖技能：
  - agent-browser: 浏览器自动化
  - e2e-testing-patterns: E2E测试最佳实践
---

# Website Test 技能

> 通用网站自动化测试 - 三层检测 + E2E最佳实践

## 快速开始

```bash
# 完整测试（三层）
SITE_URL=https://your-site.com API_BASE=https://api.your-site.com \
bash skills/website-test/scripts/full_test.sh
```

## 环境变量配置

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `SITE_URL` | 是 | - | 网站URL |
| `API_BASE` | 否 | - | API地址 |
| `PAGES` | 否 | 见下方 | 测试页面列表(逗号分隔) |

### 默认测试页面

根据 BLXST-knowledge-graph.md 设计文档：

```
home,matches,teams,players,standings,gallery,heroes,login,register
```

## 三层检测体系

### 第1层：HTTP可用性
- 服务是否响应
- 页面是否可访问

### 第2层：API数据正确性
- API返回数据格式
- 数据完整性
- 响应时间

### 第3层：渲染正确性（E2E最佳实践）
- 智能等待（非固定timeout）
- 稳定选择器（无技术字段泄露）
- 测试独立性（每个页面独立）
- 测试行为（用户可见内容）

## E2E最佳实践

### 核心原则（来自 e2e-testing-patterns）

| 原则 | 应用 |
|------|------|
| **测试行为，不测实现** | 断言用户可见结果，不测DOM结构 |
| **智能等待** | 等待条件满足，不用固定timeout |
| **稳定选择器** | 检测无内部ID/技术字段泄露 |
| **测试独立** | 每个页面单独测试 |

### 检测项目

| 检测 | 说明 |
|------|------|
| 技术字段泄露 | 无 club_id、team_code、internal_xxx |
| 数据完整 | 无 "数据 -"、undefined、null |
| JS错误 | 控制台无错误 |
| 页面独立 | 无状态污染 |

## 用法示例

```bash
# 测试所有默认页面
SITE_URL=https://blastjunior.com API_BASE=https://api.example.com \
bash skills/website-test/scripts/full_test.sh

# 仅测试指定页面
SITE_URL=https://blastjunior.com PAGES="home,teams,players" \
bash skills/website-test/scripts/render_test.sh

# 仅渲染测试
SITE_URL=https://blastjunior.com \
bash skills/website-test/scripts/render_test.sh
```

## 通过标准

| 层 | 检查项 | 标准 |
|----|--------|------|
| HTTP | 页面响应 | 全部200 |
| API | 数据返回 | 格式正确，有数据 |
| 渲染 | E2E检查 | 无JS错误，数据正确，无技术泄露 |

## 参考

- E2E最佳实践: `skills/e2e-testing-patterns/SKILL.md`
- 自定义测试: `references/custom-tests.md`
