---
name: blxst-deploy
description: |
  BLXST项目部署技能。用于部署网站到blastjunior.com。
  触发条件：(1) 用户要求部署网站 (2) 修改了public/目录下的文件需要上传 (3) 部署到线上环境 (4) GitHub推送后的验证
---

# BLXST 部署

## 快速开始

### 1. 推送代码到 GitHub

```bash
cd /root/.openclaw/workspace
git add public/ <其他修改的文件>
git commit -m "fix: ..."
git push origin main
```

Cloudflare Pages 会自动检测 GitHub 推送并部署。

### 2. 验证部署

推送后等待约30秒，然后验证：

```bash
# 检查部署状态
curl -s "https://api.cloudflare.com/client/v4/accounts/<ACCOUNT_ID>/pages/projects/blastjunior-website/deployments" \
  -H "Authorization: Bearer <API_TOKEN>" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['result'][0]['url'], d['result'][0]['latest_stage']['status'])"

# 验证主站
curl -s https://blastjunior.com/teams | grep -q "战队列表" && echo "主站正常"
```

## 核心规则

### 单一API架构

所有前端必须调用同一个API：`https://blast-homepage-api.kanjiaming2022.workers.dev`

### CORS配置

**必须遵守：只允许 blastjunior.com 一个域名**

```
const allowedOrigins = ["https://blastjunior.com"];
```

不允许空格分隔的多域名，不允许通配符。

### API数据源原则

- 数据必须来自 D1/R2/KV，禁止硬编码
- 测试环境可以用 pages.dev 验证，但生产只用 blastjunior.com

## 部署流程

1. **修改代码** → public/ 目录下的HTML文件
2. **推送GitHub** → 自动触发Cloudflare Pages部署
3. **验证** → 检查blastjunior.com是否正常
4. **如需修改API** → 部署 blast-homepage-api.js

### API部署（如需修改后端）

```bash
cd /root/.openclaw/workspace
CLOUDFLARE_API_TOKEN="pim7CQ9qHmqMFYappuq2F0pr6FDo87_GJFbG5KhK" \
CLOUDFLARE_ACCOUNT_ID="6a6fe3b0b250e0c6a09af24d01e0f9b6" \
npx wrangler deploy blast-homepage-api.js --name blast-homepage-api
```

## 项目信息

- **仓库**: New2Everything/blastjunior-website
- **目录**: public/
- **分支**: main
- **主站**: https://blastjunior.com
- **备用**: https://blastjunior-website.pages.dev
- **API**: https://blast-homepage-api.kanjiaming2022.workers.dev

## 详细参考

- CORS配置详解: [references/cors-rules.md](references/cors-rules.md)
- 数据真实性原则: 见 MEMORY.md
