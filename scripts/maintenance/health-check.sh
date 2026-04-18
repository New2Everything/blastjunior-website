#!/bin/bash
# BLXST 健康检测模块

LOG_DIR="/root/.openclaw/workspace/logs/maintenance"
mkdir -p "$LOG_DIR"

# 健康状态
export STATUS_API="UNKNOWN"
export STATUS_DB="UNKNOWN"
export STATUS_WEB="UNKNOWN"
export STATUS_MEMBERS="UNKNOWN"
export API_RESPONSE_TIME=0
export DB_ERRORS=0

# 检测函数
check_api() {
  local start=$(date +%s%3N)
  local response=$(curl -s -w "%{http_code}" -o /dev/null "https://blast-api.kanjiaming2022.workers.dev/" 2>/dev/null)
  local end=$(date +%s%3N)
  API_RESPONSE_TIME=$((end - start))
  
  if [ "$response" = "200" ]; then
    STATUS_API="GREEN"
    return 0
  else
    STATUS_API="RED"
    return 1
  fi
}

check_database() {
  local result=$(CLOUDFLARE_API_TOKEN="pim7CQ9qHmqMFYappuq2F0pr6FDo87_GJFbG5KhK" \
    CLOUDFLARE_ACCOUNT_ID="6a6fe3b0b250e0c6a09af24d01e0f9b6" \
    npx wrangler d1 execute blast-campaigns-db --command "SELECT COUNT(*) as cnt FROM blxst_users" --remote 2>&1)
  
  if echo "$result" | grep -q "\"success\": true"; then
    STATUS_DB="GREEN"
    return 0
  else
    STATUS_DB="RED"
    DB_ERRORS=$((DB_ERRORS + 1))
    return 1
  fi
}

check_website() {
  local response=$(curl -s -o /dev/null -w "%{http_code}" "https://blastjunior.com/" 2>/dev/null)
  if [ "$response" = "200" ]; then
    STATUS_WEB="GREEN"
    return 0
  else
    STATUS_WEB="RED"
    return 1
  fi
}

check_members() {
  local count=$(curl -s "https://blast-api.kanjiaming2022.workers.dev/members" 2>/dev/null | grep -o '"id"' | wc -l)
  if [ $count -ge 0 ]; then
    STATUS_MEMBERS="GREEN"
    export MEMBER_COUNT=$count
    return 0
  else
    STATUS_MEMBERS="YELLOW"
    return 1
  fi
}

# 执行所有检测
run_health_check() {
  echo "[$(date '+%Y-%m-%d %H:%M')] 🔍 健康检测开始" >> "$LOG_DIR/$(date '+%Y-%m-%d').log"
  
  check_api
  check_database
  check_website
  check_members
  
  # 汇总健康状态
  if [ "$STATUS_API" = "GREEN" ] && [ "$STATUS_DB" = "GREEN" ] && [ "$STATUS_WEB" = "GREEN" ]; then
    export OVERALL_STATUS="GREEN"
  elif [ "$STATUS_API" = "RED" ] || [ "$STATUS_DB" = "RED" ]; then
    export OVERALL_STATUS="RED"
  else
    export OVERALL_STATUS="YELLOW"
  fi
  
  # 记录结果
  cat >> "$LOG_DIR/$(date '+%Y-%m-%d').log" << EOF
[$(date '+%Y-%m-%d %H:%M')] 📊 健康检测结果:
  - API: $STATUS_API (响应 ${API_RESPONSE_TIME}ms)
  - 数据库: $STATUS_DB
  - 网站: $STATUS_WEB
  - 成员: $STATUS_MEMBERS ($MEMBER_COUNT 人)
  - 总体: $OVERALL_STATUS
EOF
}

# 执行检测
run_health_check
