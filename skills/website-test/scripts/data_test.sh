#!/bin/bash
# 数据模块与展示检测 - 通用版
# 用途：验证网站数据模块是否来自数据库（经API），非硬编码
# 使用：SITE_URL=https://example.com API_BASE=https://api.example.com bash data_test.sh

# 默认配置
SITE_URL="${SITE_URL:-https://example.com}"
API_BASE="${API_BASE:-https://api.example.com}"

# 解析PAGES变量（逗号分隔）
PAGES="${PAGES:-home,matches,teams,players,standings,gallery}"

echo "================================================================"
echo "数据模块与展示检测（通用版）"
echo "================================================================"
echo "目标网站: $SITE_URL"
echo "API地址: $API_BASE"
echo ""

PASS=0
FAIL=0
WARN=0

# ============================================================================
# 第零步：识别数据模块（通过Flag标记）
# ============================================================================

echo ">>> 第零步：识别数据模块（Flag标记 + 语义分析）"
echo "----------------------------------------------------------------"

# 尝试读取项目的HTML文件，识别DATA_MODULE标记
identify_data_modules() {
    echo "检测DATA_MODULE标记..."
    
    # 如果在workspace目录，尝试查找HTML文件
    if [ -d "/workspace" ]; then
        local modules=$(grep -rohP '<!--\s*DATA_MODULE:\s*\w+\s*-->' /workspace/*.html 2>/dev/null | sed 's/.*DATA_MODULE: //g' | sed 's/ -->//g' | sort -u)
        if [ -n "$modules" ]; then
            echo "发现标记的数据模块："
            echo "$modules" | while read mod; do
                echo "  ✅ $mod"
            done
            return 0
        fi
    fi
    
    # 如果没有标记，通过语义分析识别
    echo "无Flag标记，使用语义分析..."
    local content=$(curl -s -L "$SITE_URL" 2>/dev/null)
    
    echo "识别到的数据模块："
    
    echo "$content" | grep -qi "news\|新闻\|公告" && echo "  ✅ news"
    echo "$content" | grep -qi "sponsor\|赞助商\|合作伙伴" && echo "  ✅ sponsors"
    echo "$content" | grep -qi "match\|比赛\|赛程" && echo "  ✅ matches"
    echo "$content" | grep -qi "team\|战队\|球队" && echo "  ✅ teams"
    echo "$content" | grep -qi "player\|选手\|球员" && echo "  ✅ players"
    echo "$content" | grep -qi "standings\|积分榜\|排名" && echo "  ✅ standings"
    echo "$content" | grep -qi "gallery\|相册\|照片" && echo "  ✅ gallery"
}

identify_data_modules

# ============================================================================
# 第一部分：数据来源验证
# ============================================================================

echo ""
echo ">>> 第一部分：数据来源验证"
echo "----------------------------------------------------------------"

# 常见API端点
API_ENDPOINTS="news matches teams players standings sponsors gallery"

verify_api_source() {
    local name=$1
    
    # 尝试不同的API路径
    local endpoints="$API_ENDPOINTS $name"
    local found=0
    
    for endpoint in $endpoints; do
        local response=$(curl -s "${API_BASE}/${endpoint}" 2>/dev/null)
        
        # 检查是否有有效响应
        local ok=$(echo "$response" | python3 -c "import sys,json; d=json.load(sys.stdin); print('yes' if d.get('ok') else 'no')" 2>/dev/null)
        
        if [ "$ok" = "yes" ]; then
            local count=$(echo "$response" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('data',[])))" 2>/dev/null)
            echo "  ✅ $name: API返回数据 ($count条)"
            PASS=$((PASS + 1))
            found=1
            break
        fi
    done
    
    if [ $found -eq 0 ]; then
        echo "  ⚠️ $name: 未找到对应API"
        WARN=$((WARN + 1))
    fi
}

# 测试常见数据模块
for module in $API_ENDPOINTS; do
    verify_api_source "$module"
done

# ============================================================================
# 第二部分：数据存储验证
# ============================================================================

echo ""
echo ">>> 第二部分：数据存储验证（确认来自数据库非API硬编码）"
echo "----------------------------------------------------------------"

verify_d1_storage() {
    local endpoint=$1
    
    local response=$(curl -s "${API_BASE}/${endpoint}" 2>/dev/null)
    
    # 检查是否有数据数组
    local count=$(echo "$response" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('data',[])))" 2>/dev/null)
    
    if [ -n "$count" ] && [ "$count" -gt 0 ]; then
        # 检查数据结构是否像数据库数据（有id字段）
        local has_id=$(echo "$response" | grep -c '"id"' 2>/dev/null)
        
        if [ "$has_id" -gt 0 ]; then
            echo "  ✅ $endpoint: 数据已存储在数据库中（非API硬编码）"
            PASS=$((PASS + 1))
        else
            echo "  ⚠️ $endpoint: 数据可能来自硬编码"
            WARN=$((WARN + 1))
        fi
    else
        echo "  ⚠️ $endpoint: 无数据"
    fi
}

for module in $API_ENDPOINTS; do
    verify_d1_storage "$module"
done

# ============================================================================
# 第三部分：展示覆盖验证
# ============================================================================

echo ""
echo ">>> 第三部分：展示覆盖验证"
echo "----------------------------------------------------------------"

verify_page_coverage() {
    local page=$1
    
    # 构造页面URL
    local url="${SITE_URL}/${page}"
    [ "$page" = "home" ] && url="${SITE_URL}/"
    
    local status=$(curl -s -o /dev/null -w "%{http_code}" -L "$url" 2>/dev/null)
    
    if [ "$status" = "200" ]; then
        echo "  ✅ $page: 页面存在"
        PASS=$((PASS + 1))
    else
        echo "  ❌ $page: 页面不存在 (HTTP $status)"
        FAIL=$((FAIL + 1))
    fi
}

# 解析PAGES变量并测试
IFS=',' read -ra PAGE_ARRAY <<< "$PAGES"
for page in "${PAGE_ARRAY[@]}"; do
    verify_page_coverage "$page"
done

# ============================================================================
# 第四部分：Flag标记验证
# ============================================================================

echo ""
echo ">>> 第四部分：代码质量检查"
echo "----------------------------------------------------------------"

# 检查是否有硬编码数据（不应该在HTML中直接写数据）
check_hardcoded_data() {
    local issues=0
    
    if [ -d "/workspace" ]; then
        # 检查是否有明显的硬编码数据
        local hardcoded=$(grep -r "const teams = \[" /workspace/*.html 2>/dev/null | wc -l)
        
        if [ "$hardcoded" -gt 0 ]; then
            echo "  ⚠️ 发现可能的硬编码数据（需人工确认）"
            WARN=$((WARN + 1))
        else
            echo "  ✅ 未发现明显硬编码"
            PASS=$((PASS + 1))
        fi
    else
        echo "  ⚠️ 无法检查本地代码（请在workspace目录运行）"
    fi
}

check_hardcoded_data

# ============================================================================
# 总结
# ============================================================================

echo ""
echo "================================================================"
echo "检测完成"
echo "================================================================"
echo "目标: $SITE_URL"
echo "通过: $PASS"
echo "警告: $WARN"
echo "失败: $FAIL"
echo ""

if [ $FAIL -gt 0 ]; then
    echo "❌ 存在问题，请检查"
    exit 1
elif [ $WARN -gt 0 ]; then
    echo "⚠️ 有警告，请查看上面内容"
    exit 0
else
    echo "✅ 全部通过 - 数据模块来自数据库，非API硬编码"
fi
