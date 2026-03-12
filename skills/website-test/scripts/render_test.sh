#!/bin/bash
# 渲染层测试 - 用agent-browser检查实际渲染
# 用途：检测页面是否正确渲染，数据是否正确显示
# 必须：agent-browser

set -e

SITE_URL="${SITE_URL:-}"
BROWSER_SESSION="render-test-$$"

if [ -z "$SITE_URL" ]; then
    echo "❌ 错误: SITE_URL 未设置"
    echo "用法: SITE_URL=https://example.com bash render_test.sh"
    exit 1
fi

echo "================================================================"
echo "渲染层测试 - agent-browser深度检测"
echo "================================================================"
echo "目标: $SITE_URL"
echo ""

# 检查agent-browser是否可用
if ! command -v agent-browser &> /dev/null; then
    echo "❌ agent-browser 未安装"
    exit 1
fi

PASS=0
FAIL=0

# 测试函数
test_page() {
    local page=$1
    local url="${SITE_URL}/${page}"
    [ "$page" = "home" ] && url="${SITE_URL}/"
    
    echo ">>> 测试页面: $page"
    
    # 打开页面
    if ! agent-browser open "$url" --session "$BROWSER_SESSION" 2>&1 | grep -q "✓"; then
        echo "  ❌ 无法打开页面"
        FAIL=$((FAIL + 1))
        return 1
    fi
    
    # 等待加载
    agent-browser wait 2000 --session "$BROWSER_SESSION" 2>/dev/null || true
    
    # 检查控制台错误
    local errors=$(agent-browser errors --session "$BROWSER_SESSION" 2>&1 || true)
    if echo "$errors" | grep -qi "error\|failed\|exception"; then
        echo "  ⚠️ 控制台有错误: $(echo "$errors" | head -1)"
    fi
    
    # 获取快照
    local snapshot=$(agent-browser snapshot -c --session "$BROWSER_SESSION" 2>&1)
    
    # 检查是否显示"加载失败"
    if echo "$snapshot" | grep -q "加载失败\|加载中\|error\|Error"; then
        echo "  ❌ 页面加载失败或显示错误"
        FAIL=$((FAIL + 1))
        return 1
    fi
    
    # 检查页面标题
    local title=$(agent-browser get title --session "$BROWSER_SESSION" 2>&1)
    echo "  ✅ 页面加载成功: $title"
    PASS=$((PASS + 1))
}

# 检测技术字段泄露
test_tech_fields() {
    local page=$1
    local url="${SITE_URL}/${page}"
    
    echo ">>> 检测技术字段泄露: $page"
    
    agent-browser open "$url" --session "$BROWSER_SESSION" 2>/dev/null
    agent-browser wait 2000 --session "$BROWSER_SESSION" 2>/dev/null || true
    
    local snapshot=$(agent-browser snapshot -c --session "$BROWSER_SESSION" 2>&1)
    
    # 检测常见技术字段泄露
    local issues=0
    
    # club ID / team_code 泄露
    if echo "$snapshot" | grep -qE "club ID \|team_code \|ID TEAM"; then
        echo "  ❌ 发现技术字段: club ID / team_code"
        issues=$((issues + 1))
    fi
    
    # 数据缺失显示 (-)
    if echo "$snapshot" | grep -qE "所属战队 -\|战队 -\|积分 -\|胜率 -"; then
        echo "  ❌ 发现数据缺失显示: -"
        issues=$((issues + 1))
    fi
    
    # 空白或无数据
    if echo "$snapshot" | grep -qE "暂无数据\|无数据\|加载失败"; then
        echo "  ❌ 发现无数据或加载失败"
        issues=$((issues + 1))
    fi
    
    if [ $issues -eq 0 ]; then
        echo "  ✅ 无技术字段泄露"
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + issues))
    fi
}

# 关闭浏览器
cleanup() {
    agent-browser close --session "$BROWSER_SESSION" 2>/dev/null || true
}
trap cleanup EXIT

# ============================================================================
# 基础渲染测试
# ============================================================================
echo ">>> 1. 基础渲染测试"
echo "--------------------------------------"

PAGES="home matches teams players standings gallery"

for page in $PAGES; do
    test_page "$page"
done

# ============================================================================
# 技术字段泄露检测
# ============================================================================
echo ""
echo ">>> 2. 技术字段泄露检测"
echo "--------------------------------------"

test_tech_fields "teams"
test_tech_fields "players"

# ============================================================================
# 动态组件检测
# ============================================================================
echo ""
echo ">>> 3. 动态组件状态检测"
echo "--------------------------------------"

# 检测在线用户/实时数据组件
agent-browser open "${SITE_URL}/" --session "$BROWSER_SESSION" 2>/dev/null
agent-browser wait 3000 --session "$BROWSER_SESSION" 2>/dev/null || true

snapshot=$(agent-browser snapshot -c --session "$BROWSER_SESSION" 2>&1)

# 检查动态组件状态
if echo "$snapshot" | grep -qE "在线用户\|实时\|loading\|Loading"; then
    # 如果有动态组件，检查是否加载完成
    if echo "$snapshot" | grep -qE "暂无\|---\|- "; then
        echo "  ⚠️ 动态组件可能未正确加载"
    else
        echo "  ✅ 动态组件正常"
        PASS=$((PASS + 1))
    fi
else
    echo "  ✅ 无动态组件或已加载"
    PASS=$((PASS + 1))
fi

# ============================================================================
# 总结
# ============================================================================
echo ""
echo "================================================================"
echo "渲染层测试完成"
echo "================================================================"
echo "通过: $PASS"
echo "失败: $FAIL"
echo ""

if [ $FAIL -gt 0 ]; then
    echo "❌ 存在问题"
    exit 1
else
    echo "✅ 全部通过"
fi
