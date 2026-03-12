#!/bin/bash
# =========================================
# 网站最佳实践检测脚本
# 检测网站是否符合开发最佳实践
# 10项核心检测
# =========================================

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SITE_URL="${SITE_URL:-https://blastjunior.com}"
API_BASE="${API_BASE:-https://blast-homepage-api.kanjiaming2022.workers.dev}"

echo "========================================="
echo "网站最佳实践检测 (10项)"
echo "目标: $SITE_URL"
echo "时间: $(date +%Y%m%d_%H%M%S)"
echo "========================================="

PASS=0
FAIL=0
WARN=0

# 检测函数
check_pass() {
    echo -e "  ${GREEN}✓${NC} $1"
    ((PASS++))
}

check_fail() {
    echo -e "  ${RED}✗${NC} $1"
    ((FAIL++))
}

check_warn() {
    echo -e "  ${YELLOW}!${NC} $1"
    ((WARN++))
}

# ==========================================
# 路由架构检测 (2项)
# ==========================================
echo ""
echo -e "${BLUE}>>> 1. 路由架构 (2项)${NC}"
echo "--------------------------------------"

# 1.1 检测.html后缀详情页
# 注意：Cloudflare可能有旧文件缓存，只要SPA fallback工作正常即可
HTML_PAGES=$(curl -s -o /dev/null -w "%{http_code}" "$SITE_URL/team-detail.html" 2>/dev/null || echo "000")
if [ "$HTML_PAGES" = "200" ]; then
    # 检查是否是真正的详情页还是fallback首页
    CHECK_TITLE=$(curl -s "$SITE_URL/team-detail.html" | grep -oP '(?<=<title>)[^<]+' | head -1)
    if [[ "$CHECK_TITLE" == *"战队详情"* ]]; then
        check_fail "检测到独立的 .html 详情页文件（应使用SPA路由）"
    else
        check_pass "无.html后缀详情页（SPA fallback工作正常）"
    fi
else
    check_pass "无.html后缀详情页"
fi

# 1.2 SPA fallback检测 - 访问不存在的路由应返回index.html
SPACheck=$(curl -s "$SITE_URL/this-page-does-not-exist-12345" | grep -oP '(?<=<title>)[^<]+' | head -1 || echo "")
if [[ "$SPACheck" == *"兰星少年"* ]]; then
    check_pass "SPA fallback正确 (返回index.html)"
else
    check_fail "SPA fallback未配置或配置错误"
fi

# ==========================================
# 数据加载检测 (3项)
# ==========================================
echo ""
echo -e "${BLUE}>>> 2. 数据加载 (3项)${NC}"
echo "--------------------------------------"

# 2.1 硬编码检测
INDEX_HTML=$(curl -s "$SITE_URL/" 2>/dev/null | head -1000 || echo "")
if echo "$INDEX_HTML" | grep -qE "const (teams|players|matches) = \["; then
    check_fail "检测到硬编码数据 (const teams/players/matches)"
else
    check_pass "无硬编码数据"
fi

# 2.2 API获取检测
if echo "$INDEX_HTML" | grep -qE "fetch\("; then
    check_pass "使用fetch()获取数据"
else
    check_fail "未检测到fetch()数据获取"
fi

# 2.3 加载状态检测
if echo "$INDEX_HTML" | grep -qE "加载中|暂无|loading|暂无数据"; then
    check_pass "有加载状态/空状态提示"
else
    check_warn "未检测到明显加载状态"
fi

# ==========================================
# SEO检测 (2项)
# ==========================================
echo ""
echo -e "${BLUE}>>> 3. SEO检测 (2项)${NC}"
echo "--------------------------------------"

# 3.1 首页title
HOME_TITLE=$(curl -s "$SITE_URL/" | grep -oP '(?<=<title>)[^<]+' | head -1 || echo "")
if [[ "$HOME_TITLE" == *"兰星少年"* ]]; then
    check_pass "首页title正确: $HOME_TITLE"
else
    check_fail "首页title不正确: $HOME_TITLE"
fi

# 3.2 详情页动态title
# 注意：curl无法获取动态title（JS渲染），需要用agent-browser
# 先检查query参数格式的详情页
DETAIL_TITLE=$(curl -s "$SITE_URL/team?id=TEAM002" | grep -oP '(?<=<title>)[^<]+' | head -1 || echo "")
if [[ "$DETAIL_TITLE" == *"AKA"* ]] && [[ "$DETAIL_TITLE" != *"官网"* ]]; then
    check_pass "详情页title动态(curl): $DETAIL_TITLE"
else
    # 使用agent-browser检测JS渲染后的title
    agent-browser open "$SITE_URL/team?id=TEAM002" --wait 3000 2>&1 > /dev/null
    AGENT_TITLE=$(agent-browser eval "document.title" 2>&1 | grep -v "^$" | head -1)
    if [[ "$AGENT_TITLE" == *"AKA"* ]]; then
        check_pass "详情页title动态(agent): $AGENT_TITLE"
    else
        check_fail "详情页title不正确: $AGENT_TITLE (应为: AKA - 兰星少年)"
    fi
fi

# ==========================================
# UX检测 (2项) - 需要agent-browser
# ==========================================
echo ""
echo -e "${BLUE}>>> 4. UX检测 (2项) - 需agent-browser${NC}"
echo "--------------------------------------"

# 4.1 控制台错误检测
agent-browser open "$SITE_URL/" --wait 2000 2>&1 > /dev/null
ERRORS=$(agent-browser errors 2>&1 || echo "")
# 过滤掉空输出
ERRORS=$(echo "$ERRORS" | grep -v "^$" | head -5)
if [ -z "$ERRORS" ]; then
    check_pass "无JS控制台错误"
else
    check_fail "检测到JS错误: $ERRORS"
fi

# 4.2 undefined检测
SNAPSHOT=$(agent-browser snapshot 2>&1 || echo "")
if echo "$SNAPSHOT" | grep -q "undefined"; then
    check_fail "页面包含undefined值"
else
    check_pass "无undefined值"
fi

# ==========================================
# 安全检测 (1项)
# ==========================================
echo ""
echo -e "${BLUE}>>> 5. 安全检测 (1项)${NC}"
echo "--------------------------------------"

# 5.1 HTTPS检测
HTTPS_CHECK=$(curl -sI "$SITE_URL" | grep -i "location" | grep "https" || echo "")
if [ -n "$HTTPS_CHECK" ]; then
    check_pass "支持HTTPS"
else
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -L "$SITE_URL" | head -1)
    if [[ "$HTTP_CODE" == "200" ]]; then
        check_pass "网站可访问"
    else
        check_fail "网站访问异常: $HTTP_CODE"
    fi
fi

# ==========================================
# 总结
# ==========================================
echo ""
echo "========================================="
echo "检测结果"
echo "========================================="
echo -e "${GREEN}通过: $PASS${NC}"
echo -e "${RED}失败: $FAIL${NC}"
echo -e "${YELLOW}警告: $WARN${NC}"

if [ $FAIL -gt 0 ]; then
    echo ""
    echo -e "${RED}❌ 检测到 $FAIL 项不符合最佳实践${NC}"
    echo ""
    echo "修复建议:"
    [ $FAIL -ge 1 ] && echo "  1. 路由: 使用SPA路由，去掉.html后缀"
    [ $FAIL -ge 2 ] && echo "  2. SPA: 配置fallback到index.html"
    [ $FAIL -ge 3 ] && echo "  3. 数据: 使用API获取，禁止硬编码"
    [ $FAIL -ge 6 ] && echo "  4. SEO: 详情页title应动态包含对象名"
    exit 1
else
    echo ""
    echo -e "${GREEN}✓ 所有最佳实践检测通过！${NC}"
    exit 0
fi
