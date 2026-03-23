# Website Builder 技能

> 网站建设完整工作流

---

## 触发方式

**手动触发：**
```
输入: /build-website 或 "建设网站"
```

---

## 核心原则

**数据分离原则：**
| 数据类型 | 来源 | 访问方式 |
|----------|------|----------|
| 可变化数据 | D1/R2/KV | 必须经Worker API |
| 品牌表达 | 静态 | 允许占位 |

**规则：**
1. 所有变化数据必须经Worker API，禁止前端直连数据库
2. 禁止伪造真实数据
3. **Gallery/图片：必须从 R2 读取，禁止硬编码 picsum 等占位图**
   - API 返回空 → 页面显示空状态，不显示假数据
   - 禁止 MOCK_PHOTOS 等 fallback 机制
4. **字段映射：开发前先调用 API 确认返回字段**
   - 禁止假设字段名（如 p.url, p.image）
   - 必须对照实际 API 返回字段写代码

---

## 工作流程

```
设计 → 开发 → 部署 → 测试
```

### 1. 设计
- 查 BLXST-design.md
- 规划页面结构

### 2. 开发
- Worker API (如需要)
- 前端页面 (public/)
- 用 wrangler 部署

### 3. 测试
```bash
# website-test
SITE_URL=https://blastjunior.com API_BASE=https://blast-homepage-api.kanjiaming2022.workers.dev \
bash skills/website-test/scripts/run_tests.sh

# agent-browser
agent-browser open "https://blastjunior.com"
```

---

## 禁止事项

- 禁止前端直连D1/R2/KV
- 禁止硬编码数据
- 禁止伪造真实数据
