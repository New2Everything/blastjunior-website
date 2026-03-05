# MEMORY.md - 重要经验总结

## Cloudflare D1 权限问题

**问题**: API Token有D1权限，但直接调用API返回 "Route not found"

**原因**: D1的API路径格式与Workers/KV不同，官方文档中的路径可能不正确

**解决方案**: 使用 `wrangler` CLI操作D1，功能完全正常

```bash
CLOUDFLARE_API_TOKEN="xxx" CLOUDFLARE_ACCOUNT_ID="xxx" wrangler d1 list
```

## agent-browser 使用技巧

- 非常适合自动化测试网站
- 可以模拟用户登录、点击、填表等操作
- 截图功能强大，支持全页截图
- 适合排查UI bug

## Workers + R2 公开访问

- R2默认不能直接公开访问
- 需要创建Worker绑定R2 bucket
- Worker处理/public/*路径，返回R2文件内容
- 适用于网站静态资源托管
