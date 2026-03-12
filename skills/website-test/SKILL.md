---
name: website-test
description: |
  通用网站自动化测试技能。支持任何网站的测试。
  触发条件：(1) 用户要求测试网站 (2) 部署后验证 (3) /test-website
  包含：HTTP可用性、API数据正确性、浏览器渲染检测、JS错误检测
  
  依赖技能：agent-browser (浏览器自动化)
---

# Website Test 技能

> 通用网站自动化测试 - 三层检测体系

## 快速开始

```bash
# 完整测试（需要配置环境变量）
SITE_URL=https://your-site.com API_BASE=https://api.your-site.com \
bash skills/website-test/scripts/full_test.sh
```

## 环境变量配置

| 变量 | 必填 | 说明 |
|------|------|------|
| `SITE_URL` | 是 | 网站URL (如 https://example.com) |
| `API_BASE` | 否 | API地址，如无需可不填 |
| `PAGES` | 否 | 测试页面列表，逗号分隔 |
| `BROWSER_SESSION` | 否 | 浏览器会话名 |

## 三层检测体系

### 第1层：HTTP可用性
- 服务是否响应
- 页面是否可访问

### 第2层：API数据正确性
- API返回数据格式
- 数据完整性（条数、字段）
- 响应时间

### 第3层：渲染正确性（关键！）
- **用agent-browser真正检查DOM**
- 检查数据是否正确显示
- 检测JS运行时错误
- 检测动态组件状态
- **检测技术字段泄露**

## 核心原则

**API返回200 ≠ 网站正常！**

必须用agent-browser检查实际渲染内容。

## 通用检测项目

所有网站都应检测：

| 检测项 | 说明 |
|--------|------|
| 页面可访问 | HTTP 200 |
| 无JS错误 | 控制台无错误 |
| 无技术泄露 | 无暴露内部ID/字段 |
| 数据完整 | 无 "暂无数据"/"-" |

### 可选检测（根据网站类型）

| 类型 | 额外检测 |
|------|----------|
| 电商 | 购物车、支付流程 |
| 社交 | 登录、评论、发布 |
| 仪表盘 | 实时数据加载 |
| 画廊 | 图片懒加载 |

## 脚本说明

| 脚本 | 用途 |
|------|------|
| `full_test.sh` | 完整三层测试 |
| `http_test.sh` | HTTP可用性 |
| `api_test.sh` | API数据正确性 |
| `render_test.sh` | 渲染正确性 |

## 自定义测试

如需自定义测试，参考：
- [references/custom-tests.md](references/custom-tests.md)
- [references/patterns.md](references/patterns.md)

## 依赖

- **agent-browser**: 浏览器自动化测试
  - 安装: `npm install -g agent-browser`
  - 用于: 渲染层检测
