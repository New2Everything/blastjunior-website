# 自定义测试指南

## 如何添加自定义检测

### 1. 修改 render_test.sh

在 `test_tech_fields()` 函数中添加：

```bash
# 检测你的特定问题
if echo "$snapshot" | grep -qE "你的问题模式"; then
    echo "  ❌ 发现你的特定问题"
    issues=$((issues + 1))
fi
```

### 2. 添加新的测试函数

```bash
my_custom_test() {
    local url="${SITE_URL}/your-page"
    
    agent-browser open "$url" --session "$BROWSER_SESSION"
    agent-browser wait 2000 --session "$BROWSER_SESSION"
    
    snapshot=$(agent-browser snapshot -c --session "$BROWSER_SESSION")
    
    # 你的检测逻辑
    if echo "$snapshot" | grep -qE "问题模式"; then
        echo "  ❌ 自定义检测失败"
        return 1
    fi
}
```

### 3. 在主函数中调用

```bash
echo ">>> 自定义测试"
my_custom_test
```

## 常用检测模式

### 检测加载状态
```bash
if echo "$snapshot" | grep -qE "加载中\|loading\|Loading"; then
    echo "  ⚠️ 页面仍在加载"
fi
```

### 检测错误信息
```bash
if echo "$snapshot" | grep -qE "error\|Error\|错误\|失败"; then
    echo "  ❌ 发现错误"
fi
```

### 检测空数据
```bash
if echo "$snapshot" | grep -qE "暂无\|无数据\|---\|- "; then
    echo "  ⚠️ 数据可能为空"
fi
```

### 检测特定文本
```bash
if echo "$snapshot" | grep -q "预期显示的文本"; then
    echo "  ✅ 正常"
else
    echo "  ❌ 文本不匹配"
fi
```

## BLXST 示例

```bash
# BLXST 特定检测
test_blxst_specific() {
    agent-browser open "${SITE_URL}/teams" --session "$BROWSER_SESSION"
    snapshot=$(agent-browser snapshot -c --session "$BROWSER_SESSION")
    
    # 检测技术字段泄露
    if echo "$snapshot" | grep -qE "club ID \|team_code"; then
        echo "  ❌ 技术字段泄露"
    fi
}
```
