#!/bin/bash
# API数据层测试 - 验证API数据正确性和完整性
# 用途：检测API返回的数据是否正确、完整

set -e

API_BASE="${API_BASE:-}"

if [ -z "$API_BASE" ]; then
    echo "❌ 错误: API_BASE 未设置"
    echo "用法: API_BASE=https://api.example.com bash api_test.sh"
    exit 1
fi

echo "================================================================"
echo "API数据层测试"
echo "================================================================"
echo "API: $API_BASE"
echo ""

PASS=0
FAIL=0
WARN=0

# ============================================================================
# 1. API可用性测试
# ============================================================================
echo ">>> 1. API可用性测试"
echo "--------------------------------------"

ENDPOINTS="home news matches teams players standings sponsors gallery seasons divisions"

for endpoint in $ENDPOINTS; do
    response=$(curl -s "${API_BASE}/${endpoint}" 2>/dev/null || echo '{"ok":false}')
    
    ok=$(echo "$response" | python3 -c "import sys,json; d=json.load(sys.stdin); print('yes' if d.get('ok') else 'no')" 2>/dev/null || echo "no")
    
    if [ "$ok" = "yes" ]; then
        count=$(echo "$response" | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('data',[])))" 2>/dev/null || echo "0")
        
        # 检查数据条数是否合理
        if [ "$count" = "0" ]; then
            echo "  ⚠️ /${endpoint}: 无数据 (0条)"
            WARN=$((WARN + 1))
        else
            echo "  ✅ /${endpoint}: $count条数据"
            PASS=$((PASS + 1))
        fi
    else
        echo "  ❌ /${endpoint}: 请求失败"
        FAIL=$((FAIL + 1))
    fi
done

# ============================================================================
# 2. 数据结构验证
# ============================================================================
echo ""
echo ">>> 2. 数据结构验证"
echo "--------------------------------------"

# 验证teams数据结构
response=$(curl -s "${API_BASE}/teams" 2>/dev/null)
if echo "$response" | python3 -c "import sys,json; d=json.load(sys.stdin); t=d.get('data',[])[0] if d.get('data') else {}; print('name' in t and 'id' in t)" 2>/dev/null | grep -q "True"; then
    echo "  ✅ teams: 包含必要字段 (id, name)"
    PASS=$((PASS + 1))
else
    echo "  ❌ teams: 缺少必要字段"
    FAIL=$((FAIL + 1))
fi

# 验证players数据结构
response=$(curl -s "${API_BASE}/players" 2>/dev/null)
if echo "$response" | python3 -c "import sys,json; d=json.load(sys.stdin); t=d.get('data',[])[0] if d.get('data') else {}; print('name' in t and 'id' in t)" 2>/dev/null | grep -q "True"; then
    echo "  ✅ players: 包含必要字段 (id, name)"
    PASS=$((PASS + 1))
else
    echo "  ❌ players: 缺少必要字段"
    FAIL=$((FAIL + 1))
fi

# 验证matches数据结构
response=$(curl -s "${API_BASE}/matches" 2>/dev/null)
if echo "$response" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('ok', False))" 2>/dev/null | grep -q "True"; then
    echo "  ✅ matches: API正常"
    PASS=$((PASS + 1))
else
    echo "  ⚠️ matches: 可能无数据"
    WARN=$((WARN + 1))
fi

# ============================================================================
# 3. 数据完整性检查
# ============================================================================
echo ""
echo ">>> 3. 数据完整性检查"
echo "--------------------------------------"

# 检查teams数量
count=$(curl -s "${API_BASE}/teams" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('data',[])))" 2>/dev/null || echo "0")
if [ "$count" -gt 50 ]; then
    echo "  ✅ teams: 数据充足 ($count条)"
    PASS=$((PASS + 1))
else
    echo "  ⚠️ teams: 数据较少 ($count条)"
    WARN=$((WARN + 1))
fi

# 检查players数量
count=$(curl -s "${API_BASE}/players" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('data',[])))" 2>/dev/null || echo "0")
if [ "$count" -gt 20 ]; then
    echo "  ✅ players: 数据充足 ($count条)"
    PASS=$((PASS + 1))
else
    echo "  ⚠️ players: 数据较少 ($count条)"
    WARN=$((WARN + 1))
fi

# 检查gallery数量
count=$(curl -s "${API_BASE}/gallery" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d.get('data',[])))" 2>/dev/null || echo "0")
if [ "$count" -gt 50 ]; then
    echo "  ✅ gallery: 数据充足 ($count条)"
    PASS=$((PASS + 1))
else
    echo "  ⚠️ gallery: 数据较少 ($count条)"
    WARN=$((WARN + 1))
fi

# ============================================================================
# 4. 响应时间测试
# ============================================================================
echo ""
echo ">>> 4. 响应时间测试"
echo "--------------------------------------"

for endpoint in home teams players; do
    start=$(date +%s%3N)
    curl -s -o /dev/null "${API_BASE}/${endpoint}" 2>/dev/null
    end=$(date +%s%3N)
    duration=$((end - start))
    
    if [ $duration -lt 1000 ]; then
        echo "  ✅ /${endpoint}: ${duration}ms (优秀)"
        PASS=$((PASS + 1))
    elif [ $duration -lt 2000 ]; then
        echo "  ⚠️ /${endpoint}: ${duration}ms (一般)"
        WARN=$((WARN + 1))
    else
        echo "  ❌ /${endpoint}: ${duration}ms (较慢)"
        FAIL=$((FAIL + 1))
    fi
done

# ============================================================================
# 总结
# ============================================================================
echo ""
echo "================================================================"
echo "API测试完成"
echo "================================================================"
echo "通过: $PASS"
echo "警告: $WARN"
echo "失败: $FAIL"
echo ""

if [ $FAIL -gt 0 ]; then
    echo "❌ 存在问题"
    exit 1
elif [ $WARN -gt 0 ]; then
    echo "⚠️ 有警告"
    exit 0
else
    echo "✅ 全部通过"
fi
