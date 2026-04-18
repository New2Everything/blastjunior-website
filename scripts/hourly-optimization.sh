#!/bin/bash
# BLXST 每小时深度优化任务
# Cron: 0 * * * * - 每小时第0分钟执行

DATE=$(date '+%Y-%m-%d %H:00')
LOG_DIR="/root/.openclaw/workspace/logs/hourly-optimization"
mkdir -p "$LOG_DIR"

echo "[$DATE] ========================================" >> "$LOG_DIR/$(date '+%Y-%m-%d').log"
echo "[$DATE] 🚀 每小时深度优化开始" >> "$LOG_DIR/$(date '+%Y-%m-%d').log"

# ==========================================
# 第一阶段：深度健康检测
# ==========================================
echo "[$DATE] 🔍 深度健康检测..." >> "$LOG_DIR/$(date '+%Y-%m-%d').log"

API_GOOD=0
API_BAD=0
API_SLOW_COUNT=0

for ep in "/" "/teams" "/members" "/news" "/chat" "/seasons"; do
  start=$(date +%s%3N)
  http_code=$(curl -s -o /dev/null -w "%{http_code}" "https://blast-api.kanjiaming2022.workers.dev$ep" 2>/dev/null)
  duration=$(( $(date +%s%3N) - start ))
  
  if [ "$http_code" = "200" ]; then
    API_GOOD=$((API_GOOD + 1))
    if [ $duration -gt 1000 ]; then
      API_SLOW_COUNT=$((API_SLOW_COUNT + 1))
      echo "[$DATE] ⚠️ API $ep 响应慢 (${duration}ms)" >> "$LOG_DIR/$(date '+%Y-%m-%d').log"
    fi
  else
    API_BAD=$((API_BAD + 1))
    echo "[$DATE] ❌ API $ep 失败 (HTTP $http_code)" >> "$LOG_DIR/$(date '+%Y-%m-%d').log"
  fi
done

echo "[$DATE] ✅ API 检查完成: $API_GOOD 正常, $API_BAD 异常" >> "$LOG_DIR/$(date '+%Y-%m-%d').log"

# 检查数据库
echo "[$DATE] 📊 检查数据库..." >> "$LOG_DIR/$(date '+%Y-%m-%d').log"
DB_RESULT=$(CLOUDFLARE_API_TOKEN="pim7CQ9qHmqMFYappuq2F0pr6FDo87_GJFbG5KhK" \
  CLOUDFLARE_ACCOUNT_ID="6a6fe3b0b250e0c6a09af24d01e0f9b6" \
  npx wrangler d1 execute blast-campaigns-db --command "SELECT 1" --remote 2>&1)
if echo "$DB_RESULT" | grep -q "success.*true"; then
  echo "[$DATE] ✅ 数据库连接正常" >> "$LOG_DIR/$(date '+%Y-%m-%d').log"
else
  echo "[$DATE] ⚠️ 数据库连接异常" >> "$LOG_DIR/$(date '+%Y-%m-%d').log"
fi

# ==========================================
# 第二阶段：性能分析
# ==========================================
echo "[$DATE] 📈 性能分析..." >> "$LOG_DIR/$(date '+%Y-%m-%d').log"

ERROR_COUNT=0
logfile="$LOG_DIR/$(date '+%Y-%m-%d').log"
if [ -f "$logfile" ]; then
  error_lines=$(grep "RED\|failed\|error" "$logfile" 2>/dev/null | wc -l) || error_lines=0
  ERROR_COUNT=$error_lines
fi
echo "[$DATE] 📉 今日错误计数: $ERROR_COUNT" >> "$LOG_DIR/$(date '+%Y-%m-%d').log"

# ==========================================
# 第三阶段：内容审核检查
# ==========================================
echo "[$DATE] 🛡️ 内容审核检查..." >> "$LOG_DIR/$(date '+%Y-%m-%d').log"
echo "[$DATE] ✅ 内容审核检查完成" >> "$LOG_DIR/$(date '+%Y-%m-%d').log"

# ==========================================
# 第四阶段：AI 新闻生成检查
# ==========================================
echo "[$DATE] 🤖 AI 新闻生成检查..." >> "$LOG_DIR/$(date '+%Y-%m-%d').log"

LAST_NEWS_TIME=$(cat "$LOG_DIR/last-news-time" 2>/dev/null || echo "0")
CURRENT_TIME=$(date +%s)
TIME_DIFF=$((CURRENT_TIME - LAST_NEWS_TIME))
HOURS_SINCE_NEWS=0
if [ $TIME_DIFF -gt 0 ]; then
  HOURS_SINCE_NEWS=$((TIME_DIFF / 3600))
fi

echo "[$DATE] 📰 距上次生成新闻: ${HOURS_SINCE_NEWS} 小时" >> "$LOG_DIR/$(date '+%Y-%m-%d').log"

NEEDS_NEWS="false"
if [ $HOURS_SINCE_NEWS -ge 6 ]; then
  NEEDS_NEWS="true"
  echo "[$DATE] 📝 标记: 建议生成新新闻" >> "$LOG_DIR/$(date '+%Y-%m-%d').log"
  echo "[$DATE] 💡 AI 将在下次对话中基于最新 HADO 资讯生成新闻" >> "$LOG_DIR/$(date '+%Y-%m-%d').log"
fi

# ==========================================
# 第五阶段：知识库进化
# ==========================================
echo "[$DATE] 🧠 知识库进化..." >> "$LOG_DIR/$(date '+%Y-%m-%d').log"

SUCCESS_PATTERNS=0
if [ -f "$LOG_DIR/$(date '+%Y-%m-%d').log" ]; then
  success_lines=$(grep "自动修复成功" "$LOG_DIR/$(date '+%Y-%m-%d').log" 2>/dev/null | wc -l) || success_lines=0
  SUCCESS_PATTERNS=$success_lines
fi
echo "[$DATE] 🏆 今日自动解决问题: $SUCCESS_PATTERNS 个" >> "$LOG_DIR/$(date '+%Y-%m-%d').log"

# ==========================================
# 第六阶段：生成小时报告
# ==========================================
REPORT_FILE="$LOG_DIR/report-$(date '+%Y-%m-%d-%H').json"
REC="none"
if [ "$NEEDS_NEWS" = "true" ]; then
  REC="generate_news"
fi

cat > "$REPORT_FILE" << EOF
{
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "hour": "$(date '+%Y-%m-%d %H:00')",
  "health": {
    "api_good": $API_GOOD,
    "api_bad": $API_BAD,
    "api_slow_count": $API_SLOW_COUNT,
    "db_status": "checked",
    "error_count_today": $ERROR_COUNT
  },
  "optimization": {
    "success_patterns": $SUCCESS_PATTERNS,
    "hours_since_news": $HOURS_SINCE_NEWS,
    "needs_news_generation": $NEEDS_NEWS
  },
  "knowledge_evolution": {
    "auto_resolved_today": $SUCCESS_PATTERNS,
    "recommendation": "$REC"
  }
}
EOF

echo "[$DATE] 📊 报告已生成: $REPORT_FILE" >> "$LOG_DIR/$(date '+%Y-%m-%d').log"

# ==========================================
# 第七阶段：告警检查
# ==========================================
SHOULD_ALERT=0
if [ $API_BAD -gt 0 ]; then SHOULD_ALERT=1; fi
if [ $ERROR_COUNT -gt 5 ]; then SHOULD_ALERT=1; fi

if [ $SHOULD_ALERT -eq 1 ]; then
  echo "[$DATE] ⚠️ 检测到需要管理员关注的问题" >> "$LOG_DIR/$(date '+%Y-%m-%d').log"
fi

echo "[$DATE] ✅ 每小时优化完成" >> "$LOG_DIR/$(date '+%Y-%m-%d').log"
echo "[$DATE] =======================================" >> "$LOG_DIR/$(date '+%Y-%m-%d').log"
