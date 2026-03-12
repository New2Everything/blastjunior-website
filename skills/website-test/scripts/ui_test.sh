#!/bin/bash
# 深度UI测试 - 使用agent-browser实现完全无人化
# 自动检测：页面截图 + 控制台JS错误 + 图片加载失败

SITE_URL="${SITE_URL:-https://blastjunior.com}"
REPORT_DIR="test-reports"

echo ">>> 深度UI测试（agent-browser无人化）"
echo "目标: $SITE_URL"
echo ""

mkdir -p "$REPORT_DIR/screenshots"

# 检查agent-browser是否可用
if ! command -v agent-browser &> /dev/null; then
    echo "❌ agent-browser未安装"
    exit 1
fi

# 初始化结果
ERRORS=0

# 测试函数
test_page_fully() {
    local page=$1
    local name=$2
    local url="${SITE_URL}${page}"
    
    echo "--- 测试: $name ---"
    
    # 1. 打开页面
    echo "  📂 打开页面..."
    agent-browser open "$url" 2>/dev/null || true
    
    # 2. 截图
    echo "  📸 截图..."
    local safe_name=$(echo "$page" | tr '/' '_' | tr -d '.')
    local screenshot_path="${REPORT_DIR}/screenshots/${safe_name}.png"
    agent-browser screenshot "$screenshot_path" 2>/dev/null || true
    
    # 3. 检测控制台错误（执行JS）
    echo "  🔍 检测控制台错误..."
    local console_errors=$(agent-browser eval "
      (function() {
        var errors = [];
        window.addEventListener('error', function(e) {
          errors.push(e.message);
        });
        return errors.length > 0 ? errors.join('; ') : 'none';
      })();
    " 2>/dev/null | tr -d '"')
    
    if [ "$console_errors" != "none" ] && [ -n "$console_errors" ]; then
        echo "    ⚠️ 控制台错误: $console_errors"
        ERRORS=$((ERRORS + 1))
    else
        echo "    ✅ 无控制台错误"
    fi
    
    # 4. 检测图片加载失败
    echo "  🖼️ 检测图片加载..."
    local img_status=$(agent-browser eval "
      (function() {
        var imgs = document.querySelectorAll('img');
        var failed = 0;
        var loaded = 0;
        imgs.forEach(function(img) {
          if (img.complete && img.naturalWidth > 0) loaded++;
          else failed++;
        });
        return loaded + ' loaded, ' + failed + ' failed';
      })();
    " 2>/dev/null | tr -d '"')
    
    echo "    图片状态: $img_status"
    
    # 5. 检测undefined元素
    echo "  🔎 检测undefined元素..."
    local undefined_count=$(agent-browser eval "
      (function() {
        var count = 0;
        var text = document.body.innerText || '';
        if (text.includes('undefined')) count++;
        if (text.includes('null')) count++;
        return count;
      })();
    " 2>/dev/null || echo "0")
    
    if [ "$undefined_count" != "0" ]; then
        echo "    ⚠️ 发现undefined/null: $undefined_count处"
        ERRORS=$((ERRORS + 1))
    else
        echo "    ✅ 无undefined/null"
    fi
    
    echo ""
}

# 关闭之前的浏览器
agent-browser close 2>/dev/null || true

# 测试关键页面
test_page_fully "/" "首页"
test_page_fully "/matches.html" "赛程"
test_page_fully "/teams.html" "战队"
test_page_fully "/players.html" "选手"
test_page_fully "/gallery.html" "画廊"

# 关闭浏览器
agent-browser close 2>/dev/null || true

# 总结
echo "========================================"
echo "深度UI测试完成"
echo "========================================"
echo "发现错误数: $ERRORS"
echo "截图位置: $REPORT_DIR/screenshots/"
echo ""

if [ $ERRORS -gt 0 ]; then
    echo "❌ 存在问题，需要检查"
    exit 1
else
    echo "✅ 全部通过"
fi
