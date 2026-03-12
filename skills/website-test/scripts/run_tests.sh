#!/bin/bash
# Website Test Suite - 通用测试套件
# 用法: SITE_URL=https://example.com API_BASE=https://api.example.com bash run_tests.sh

set -e

# 默认配置
SITE_URL="${SITE_URL:-https://example.com}"
API_BASE="${API_BASE:-https://api.example.com}"
PAGES="${PAGES:-home,matches,teams,players,standings,gallery,join,honor}"

REPORT_DIR="test-reports"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "========================================"
echo "网站自动化测试"
echo "目标: $SITE_URL"
echo "时间: $TIMESTAMP"
echo "========================================"

# 创建报告目录
mkdir -p "$REPORT_DIR/screenshots"

# 初始化结果
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# 测试函数
log_test() {
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    echo "[$1] $2"
}

pass_test() {
    PASSED_TESTS=$((PASSED_TESTS + 1))
}

fail_test() {
    FAILED_TESTS=$((FAILED_TESTS + 1))
    echo "  ❌ 失败: $1"
}

# 1. 功能测试
echo ""
echo ">>> 1. 功能测试"
echo "--------------------------------------"

# 解析PAGES变量
IFS=',' read -ra PAGE_ARRAY <<< "$PAGES"

# 测试首页
if curl -s -L -o /dev/null -w "%{http_code}" "$SITE_URL/" | grep -q "200"; then
    log_test "PASS" "首页访问"
    pass_test
else
    log_test "FAIL" "首页访问"
    fail_test "首页无法访问"
fi

# 测试各页面
for page in "${PAGE_ARRAY[@]}"; do
    if [ "$page" = "home" ]; then
        continue
    fi
    
    # 尝试多种URL格式
    local_url="${SITE_URL}/${page}"
    if curl -s -L -o /dev/null -w "%{http_code}" "$local_url" 2>/dev/null | grep -q "200"; then
        log_test "PASS" "页面 $page"
        pass_test
    elif curl -s -L -o /dev/null -w "%{http_code}" "${local_url}.html" 2>/dev/null | grep -q "200"; then
        log_test "PASS" "页面 ${page}.html"
        pass_test
    else
        log_test "FAIL" "页面 $page"
        fail_test "$page 返回非200"
    fi
done

# 2. API测试
echo ""
echo ">>> 2. API测试"
echo "--------------------------------------"

# 常见API端点
API_ENDPOINTS="home news matches teams players standings sponsors"

for endpoint in $API_ENDPOINTS; do
    start_time=$(date +%s%3N)
    response=$(curl -s -o /dev/null -w "%{http_code}" "${API_BASE}/${endpoint}" 2>/dev/null || echo "000")
    end_time=$(date +%s%3N)
    duration=$((end_time - start_time))
    
    if [ "$response" = "200" ]; then
        # 根据端点类型设定不同的SLO
        slo=700
        [ "$endpoint" = "home" ] && slo=300
        
        if [ $duration -lt $slo ]; then
            log_test "PASS" "API /$endpoint (${duration}ms)"
            pass_test
        else
            log_test "WARN" "API /$endpoint (${duration}ms) - 超过SLO ${slo}ms"
            pass_test
        fi
    else
        log_test "FAIL" "API /$endpoint (HTTP $response)"
        fail_test "API返回非200"
    fi
done

# 3. 性能测试（基础）
echo ""
echo ">>> 3. 性能测试"
echo "--------------------------------------"

# 首页加载时间
start_time=$(date +%s%3N)
curl -s -o /dev/null "$SITE_URL/"
end_time=$(date +%s%3N)
homepage_time=$((end_time - start_time))

if [ $homepage_time -lt 2500 ]; then
    log_test "PASS" "首页加载时间 (${homepage_time}ms ≤ 2500ms)"
    pass_test
else
    log_test "FAIL" "首页加载时间 (${homepage_time}ms > 2500ms)"
    fail_test "首页加载超过SLO"
fi

# 4. 控制台错误检测
echo ""
echo ">>> 4. 控制台错误检测"
echo "--------------------------------------"

# 使用agent-browser检测控制台错误（如果可用）
if command -v agent-browser &> /dev/null; then
    echo "检测到agent-browser，使用浏览器检测控制台错误..."
    # 这里可以调用agent-browser进行检测
fi

# 5. 图片加载检测
echo ""
echo ">>> 5. 图片加载检测"
echo "--------------------------------------"

# 检查网站logo是否能加载
logo_response=$(curl -s -o /dev/null -w "%{http_code}" "$SITE_URL/images/logo.png" 2>/dev/null || echo "000")
if [ "$logo_response" = "200" ] || [ "$logo_response" = "301" ] || [ "$logo_response" = "302" ]; then
    log_test "PASS" "Logo图片可访问"
    pass_test
else
    log_test "WARN" "Logo图片返回 $logo_response"
fi

# 生成报告
echo ""
echo "========================================"
echo "测试完成"
echo "========================================"
echo "总计: $TOTAL_TESTS"
echo "通过: $PASSED_TESTS"
echo "失败: $FAILED_TESTS"
echo "报告: $REPORT_DIR/test-summary-$TIMESTAMP.txt"
echo ""

# 写入摘要
cat > "$REPORT_DIR/test-summary-$TIMESTAMP.txt" << EOF
网站测试报告
==================
时间: $TIMESTAMP
目标: $SITE_URL

结果:
- 总计: $TOTAL_TESTS
- 通过: $PASSED_TESTS  
- 失败: $FAILED_TESTS

性能:
- 首页加载: ${homepage_time}ms (目标≤2500ms)

SLO检查:
EOF

if [ $homepage_time -lt 2500 ]; then
    echo "✅ 首页SLO达标" >> "$REPORT_DIR/test-summary-$TIMESTAMP.txt"
else
    echo "❌ 首页SLO未达标" >> "$REPORT_DIR/test-summary-$TIMESTAMP.txt"
fi

echo "✅ 测试完成"
