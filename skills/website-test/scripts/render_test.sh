#!/bin/bash
# 渲染层测试 - 从设计文档读取测试标准
# 参考: projects/BLXST-test-standards.md

set -e

SITE_URL="${SITE_URL:-}"
PAGES_CONFIG="${PAGES:-}"
DESIGN_DOC="${DESIGN_DOC:-/root/.openclaw/workspace/projects/BLXST-design.md}"
BROWSER_SESSION="render-test-$$"

# ============================================================================
# 1. 验证环境
# ============================================================================

if [ -z "$SITE_URL" ]; then
    echo "❌ 错误: SITE_URL 未设置"
    echo "用法: SITE_URL=https://example.com bash render_test.sh"
    exit 1
fi

if [ ! -f "$DESIGN_DOC" ]; then
    echo "❌ 错误: 设计文档不存在: $DESIGN_DOC"
    echo "请确保设计文档存在，或设置 DESIGN_DOC 环境变量"
    exit 1
fi

echo "================================================================"
echo "渲染层测试 - 从设计文档读取标准"
echo "================================================================"
echo "目标: $SITE_URL"
echo "设计文档: $DESIGN_DOC"
echo ""

# 检查agent-browser
if ! command -v agent-browser &> /dev/null; then
    echo "❌ agent-browser 未安装"
    exit 1
fi

# ============================================================================
# 2. 从设计文档读取配置
# ============================================================================

echo ">>> 读取设计文档..."

# 读取页面列表（如果没有配置）
if [ -z "$PAGES_CONFIG" ]; then
    # 从设计文档解析页面列表
    PAGES_CONFIG=$(grep -E "^\|" "$DESIGN_DOC" | grep "页面" | awk -F'|' '{print $3}' | grep -v "^$" | head -10 | tr '\n' ',' | sed 's/,$//')
fi

if [ -z "$PAGES_CONFIG" ]; then
    echo "⚠️ 无法从设计文档读取页面列表，使用默认"
    PAGES_CONFIG="home,matches,teams,players,standings,gallery"
fi

echo "测试页面: $PAGES_CONFIG"
echo ""

# 解析页面数组
IFS=',' read -ra PAGE_ARRAY <<< "$PAGES_CONFIG"

PASS=0
FAIL=0
WARN=0

# ============================================================================
# 3. 定义测试函数（从设计文档读取规则）
# ============================================================================

# 技术字段泄露模式（来自设计文档3.1）
TECH_FIELD_PATTERNS="club ID |team_code |ID TEAM|internal_"

# 数据完整性模式（来自设计文档3.2）
# 注意：只检测真正的数据缺失（如加载失败），不把"-"当作错误（可能是真实无数据）
DATA_MISSING_PATTERNS="暂无数据|加载失败|加载错误"

# JS错误模式（来自设计文档3.3）
JS_ERROR_PATTERNS="error|failed|exception"

test_page_load() {
    local page=$1
    local url="${SITE_URL}/${page}"
    [ "$page" = "home" ] && url="${SITE_URL}/"
    
    echo ">>> 测试页面: $page"
    
    if ! agent-browser open "$url" --session "$BROWSER_SESSION" 2>&1 | grep -q "✓"; then
        echo "  ❌ 无法打开页面"
        FAIL=$((FAIL + 1))
        return 1
    fi
    
    # 智能等待（来自设计文档5.2）
    agent-browser wait 2000 --session "$BROWSER_SESSION" 2>/dev/null || true
    
    # 检查JS错误（来自设计文档3.3）
    local errors=$(agent-browser errors --session "$BROWSER_SESSION" 2>&1 || true)
    if echo "$errors" | grep -qiE "$JS_ERROR_PATTERNS"; then
        echo "  ⚠️ 控制台有JS错误"
        WARN=$((WARN + 1))
    fi
    
    local snapshot=$(agent-browser snapshot -c --session "$BROWSER_SESSION" 2>&1)
    
    # 检查加载失败
    if echo "$snapshot" | grep -qE "加载失败|error|Error"; then
        echo "  ❌ 页面显示错误"
        FAIL=$((FAIL + 1))
        return 1
    fi
    
    local title=$(agent-browser get title --session "$BROWSER_SESSION" 2>&1)
    [ -n "$title" ] && echo "  ✅ 加载成功: $title"
    PASS=$((PASS + 1))
}

test_data_display() {
    local page=$1
    local url="${SITE_URL}/${page}"
    
    echo ">>> 数据完整性: $page"
    
    agent-browser open "$url" --session "$BROWSER_SESSION" 2>/dev/null
    agent-browser wait 2000 --session "$BROWSER_SESSION" 2>/dev/null || true
    
    local snapshot=$(agent-browser snapshot -c --session "$BROWSER_SESSION" 2>&1)
    local issues=0
    
    # 检测技术字段泄露（来自设计文档3.1）
    if echo "$snapshot" | grep -qE "$TECH_FIELD_PATTERNS"; then
        echo "  ❌ 技术字段泄露"
        issues=$((issues + 1))
    fi
    
    # 检测数据缺失（来自设计文档3.2）
    if echo "$snapshot" | grep -qE "$DATA_MISSING_PATTERNS"; then
        echo "  ❌ 数据缺失"
        issues=$((issues + 1))
    fi
    
    [ $issues -eq 0 ] && echo "  ✅ 数据完整" || FAIL=$((FAIL + issues))
    PASS=$((PASS + 1))
}

test_page_independence() {
    local page=$1
    local url="${SITE_URL}/${page}"
    
    echo ">>> 页面独立性: $page"
    
    agent-browser open "$url" --session "$BROWSER_SESSION" 2>/dev/null
    agent-browser wait 2000 --session "$BROWSER_SESSION" 2>/dev/null || true
    
    local snapshot=$(agent-browser snapshot -c --session "$BROWSER_SESSION" 2>&1)
    
    # 检测未定义数据（来自设计文档3.3）
    if echo "$snapshot" | grep -qE "undefined|null|NaN"; then
        echo "  ⚠️ 未定义数据"
        WARN=$((WARN + 1))
    else
        echo "  ✅ 正常"
        PASS=$((PASS + 1))
    fi
}

# ============================================================================
# 4. 执行测试
# ============================================================================

cleanup() { agent-browser close --session "$BROWSER_SESSION" 2>/dev/null || true; }
trap cleanup EXIT

echo ">>> 1. 页面加载测试"
echo "--------------------------------------"
for page in "${PAGE_ARRAY[@]}"; do
    test_page_load "$page"
done

echo ""
echo ">>> 2. 数据完整性测试"
echo "--------------------------------------"
# 对数据相关页面进行测试
for page in teams players matches standings; do
    if [[ " ${PAGE_ARRAY[*]} " =~ " $page " ]]; then
        test_data_display "$page"
    fi
done

echo ""
echo ">>> 3. 页面独立性测试"
echo "--------------------------------------"
[ ${#PAGE_ARRAY[@]} -gt 0 ] && test_page_independence "${PAGE_ARRAY[0]}"

# ============================================================================
# 5. 总结
# ============================================================================
echo ""
echo "================================================================"
echo "测试完成 - 标准来源: $DESIGN_DOC"
echo "================================================================"
echo "测试页面: ${PAGE_ARRAY[*]}"
echo "通过: $PASS | 警告: $WARN | 失败: $FAIL"
echo ""

[ $FAIL -gt 0 ] && exit 1 || exit 0
