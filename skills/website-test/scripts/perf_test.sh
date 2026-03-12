#!/bin/bash
# 性能测试脚本
# 用法: bash skills/website-test/scripts/perf_test.sh

SITE_URL="${SITE_URL:-https://blastjunior.com}"

echo ">>> 性能基准测试"
echo ""

# SLO基准（来自白皮书）
declare -A SLO=(
    ["首页"]=2500
    ["详情页"]=2000
    ["画廊"]=2500
    ["API-首页"]=300
    ["API-列表"]=500
    ["API-详情"]=400
    ["API-搜索"]=700
)

test_page() {
    local name=$1
    local url=$2
    local slo=$3
    
    start=$(date +%s%3N)
    curl -s -o /dev/null "$url"
    end=$(date +%s%3N)
    duration=$((end - start))
    
    if [ $duration -lt $slo ]; then
        echo "✅ $name: ${duration}ms (SLO: ${slo}ms)"
    else
        echo "❌ $name: ${duration}ms (SLO: ${slo}ms) - 未达标!"
    fi
}

# 页面性能测试
echo "--- 页面加载 ---"
test_page "首页" "$SITE_URL/" ${SLO["首页"]}
test_page "赛程" "$SITE_URL/matches.html" ${SLO["首页"]}
test_page "积分榜" "$SITE_URL/standings.html" ${SLO["首页"]}
test_page "战队" "$SITE_URL/teams.html" ${SLO["首页"]}
test_page "选手" "$SITE_URL/players.html" ${SLO["首页"]}
test_page "画廊" "$SITE_URL/gallery.html" ${SLO["画廊"]}

echo ""
echo "--- API响应 ---"

# API性能测试
test_api() {
    local name=$1
    local url=$2
    local slo=$3
    
    start=$(date +%s%3N)
    status=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
    end=$(date +%s%3N)
    duration=$((end - start))
    
    if [ "$status" = "200" ]; then
        if [ $duration -lt $slo ]; then
            echo "✅ $name: ${duration}ms (SLO: ${slo}ms)"
        else
            echo "❌ $name: ${duration}ms (SLO: ${slo}ms) - 未达标!"
        fi
    else
        echo "❌ $name: HTTP $status"
    fi
}

test_api "首页聚合API" "https://blast-homepage-api.kanjiaming2022.workers.dev/" ${SLO["API-首页"]}
test_api "搜索API" "https://blast-search-api.kanjiaming2022.workers.dev/search?q=test" ${SLO["API-搜索"]}

echo ""
echo "性能测试完成"
