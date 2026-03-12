#!/bin/bash
# 完整测试 - 三层检测体系
# HTTP层 + API层 + 渲染层

set -e

# 必须配置的环境变量
SITE_URL="${SITE_URL:-}"
API_BASE="${API_BASE:-}"

# 验证必填参数
if [ -z "$SITE_URL" ]; then
    echo "❌ 错误: SITE_URL 未设置"
    echo "用法: SITE_URL=https://example.com API_BASE=https://api.example.com bash full_test.sh"
    exit 1
fi

echo "========================================"
echo "网站完整测试"
echo "目标: $SITE_URL"
echo "API: ${API_BASE:-未配置}"
echo "========================================"
echo ""

TOTAL_PASS=0
TOTAL_FAIL=0

# ============================================================================
# 第1层: HTTP可用性测试
# ============================================================================
echo ">>> 第1层: HTTP可用性测试"
echo "--------------------------------------"

HTTP_PASS=0
HTTP_FAIL=0

# 测试首页
if curl -s -L -o /dev/null -w "%{http_code}" "$SITE_URL/" | grep -q "200"; then
    echo "✅ 首页: 200"
    HTTP_PASS=$((HTTP_PASS + 1))
else
    echo "❌ 首页: 失败"
    HTTP_FAIL=$((HTTP_FAIL + 1))
fi

# 测试各页面
for page in matches teams players standings gallery; do
    status=$(curl -s -o /dev/null -w "%{http_code}" "${SITE_URL}/${page}" 2>/dev/null || echo "000")
    if [ "$status" = "200" ]; then
        echo "✅ ${page}: 200"
        HTTP_PASS=$((HTTP_PASS + 1))
    else
        echo "❌ ${page}: $status"
        HTTP_FAIL=$((HTTP_FAIL + 1))
    fi
done

echo "HTTP层: $HTTP_PASS 通过, $HTTP_FAIL 失败"
[ $HTTP_FAIL -eq 0 ] && TOTAL_PASS=$((TOTAL_PASS + 1)) || TOTAL_FAIL=$((TOTAL_FAIL + 1))
echo ""

# ============================================================================
# 第2层: API数据测试
# ============================================================================
echo ">>> 第2层: API数据测试"
echo "--------------------------------------"

API_PASS=0
API_FAIL=0

for endpoint in home news matches teams players standings sponsors gallery; do
    response=$(curl -s "${API_BASE}/${endpoint}" 2>/dev/null || echo '{"ok":false}')
    
    ok=$(echo "$response" | python3 -c "import sys,json; d=json.load(sys.stdin); print('yes' if d.get('ok') else 'no')" 2>/dev/null || echo "no")
    
    if [ "$ok" = "yes" ]; then
        count=$(echo "$response" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('data',[])))" 2>/dev/null || echo "0")
        echo "✅ /${endpoint}: $count条数据"
        API_PASS=$((API_PASS + 1))
    else
        echo "❌ /${endpoint}: 无数据"
        API_FAIL=$((API_FAIL + 1))
    fi
done

echo "API层: $API_PASS 通过, $API_FAIL 失败"
[ $API_FAIL -eq 0 ] && TOTAL_PASS=$((TOTAL_PASS + 1)) || TOTAL_FAIL=$((TOTAL_FAIL + 1))
echo ""

# ============================================================================
# 第3层: 渲染测试（关键！）
# ============================================================================
echo ">>> 第3层: 渲染测试"
echo "--------------------------------------"

if command -v agent-browser &> /dev/null; then
    RENDER_PASS=0
    RENDER_FAIL=0
    
    SESSION="blxst-test-$$"
    
    # 清理函数
    cleanup() { agent-browser close --session "$SESSION" 2>/dev/null || true; }
    trap cleanup EXIT
    
    # 测试战队列表
    echo "检测: 战队列表渲染..."
    agent-browser open "${SITE_URL}/teams" --session "$SESSION" 2>/dev/null
    agent-browser wait 2000 --session "$SESSION" 2>/dev/null || true
    
    snapshot=$(agent-browser snapshot -c --session "$SESSION" 2>&1)
    
    # 检查是否有技术字段泄露
    if echo "$snapshot" | grep -qE "club ID TEAM|team_code"; then
        echo "  ❌ 发现技术字段泄露 (club ID / team_code)"
        RENDER_FAIL=$((RENDER_FAIL + 1))
    else
        echo "  ✅ 无技术字段泄露"
        RENDER_PASS=$((RENDER_PASS + 1))
    fi
    
    # 检查是否显示加载失败
    if echo "$snapshot" | grep -q "加载失败"; then
        echo "  ❌ 显示加载失败"
        RENDER_FAIL=$((RENDER_FAIL + 1))
    else
        echo "  ✅ 正常显示"
        RENDER_PASS=$((RENDER_PASS + 1))
    fi
    
    # 测试选手列表
    echo "检测: 选手列表渲染..."
    agent-browser open "${SITE_URL}/players" --session "$SESSION" 2>/dev/null
    agent-browser wait 2000 --session "$SESSION" 2>/dev/null || true
    
    snapshot=$(agent-browser snapshot -c --session "$SESSION" 2>&1)
    
    # 检查所属战队是否显示
    if echo "$snapshot" | grep -qE "所属战队 -\|所属战队$"; then
        echo "  ❌ 所属战队未正确显示"
        RENDER_FAIL=$((RENDER_FAIL + 1))
    else
        echo "  ✅ 所属战队正确显示"
        RENDER_PASS=$((RENDER_PASS + 1))
    fi
    
    # 检查JS错误
    errors=$(agent-browser errors --session "$SESSION" 2>&1 || true)
    if echo "$errors" | grep -qi "error\|failed"; then
        echo "  ⚠️ 控制台有错误"
        RENDER_FAIL=$((RENDER_FAIL + 1))
    else
        echo "  ✅ 无JS错误"
        RENDER_PASS=$((RENDER_PASS + 1))
    fi
    
    echo "渲染层: $RENDER_PASS 通过, $RENDER_FAIL 失败"
    [ $RENDER_FAIL -eq 0 ] && TOTAL_PASS=$((TOTAL_PASS + 1)) || TOTAL_FAIL=$((TOTAL_FAIL + 1))
else
    echo "⚠️ agent-browser 未安装，跳过渲染层测试"
    echo "建议安装: npm install -g agent-browser"
fi

echo ""

# ============================================================================
# 总结
# ============================================================================
echo "========================================"
echo "测试完成"
echo "========================================"
echo "第1层(HTTP): $HTTP_PASS 通过, $HTTP_FAIL 失败"
echo "第2层(API):  $API_PASS 通过, $API_FAIL 失败"
echo "第3层(渲染): $RENDER_PASS 通过, $RENDER_FAIL 失败"
echo ""
echo "总计: $TOTAL_PASS/3 层通过, $TOTAL_FAIL 层失败"
echo ""

if [ $TOTAL_FAIL -gt 0 ]; then
    echo "❌ 测试未通过"
    exit 1
else
    echo "✅ 全部通过"
fi
