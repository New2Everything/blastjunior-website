#!/bin/bash
# 功能+UI测试脚本
# 用法: bash skills/website-test/scripts/func_test.sh

SITE_URL="${SITE_URL:-https://blastjunior.com}"

echo ">>> 功能+UI测试"

# 测试列表
PAGES=(
    "/"
    "/matches.html"
    "/standings.html"
    "/teams.html"
    "/players.html"
    "/gallery.html"
    "/join.html"
    "/honor.html"
    "/team-detail.html?id=1"
    "/player-detail.html?id=1"
    "/match-detail.html?id=1"
)

PASS=0
FAIL=0

for page in "${PAGES[@]}"; do
    # -L 跟随重定向（Cloudflare Pages会重定向无斜杠路径）
    status=$(curl -s -L -o /dev/null -w "%{http_code}" "$SITE_URL$page" 2>/dev/null || echo "000")
    if [ "$status" = "200" ]; then
        echo "✅ $page"
        PASS=$((PASS + 1))
    else
        echo "❌ $page (HTTP $status)"
        FAIL=$((FAIL + 1))
    fi
done

echo ""
echo "结果: $PASS 通过, $FAIL 失败"
