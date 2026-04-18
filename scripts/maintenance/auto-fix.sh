#!/bin/bash
# BLXST 自动修复模块

LOG_DIR="/root/.openclaw/workspace/logs/maintenance"
KB_FILE="/root/.openclaw/workspace/scripts/maintenance/knowledge-base.json"

# 引入健康状态
source /root/.openclaw/workspace/scripts/maintenance/health-check.sh 2>/dev/null

# 问题记录
PROBLEMS_FOUND=()
AUTO_FIXED=()
MANUAL_REQUIRED=()

# 日志
fix_log() {
  echo "[$(date '+%Y-%m-%d %H:%M')] 🔧 $1" >> "$LOG_DIR/$(date '+%Y-%m-%d').log"
}

# 自动修复: API 超时
fix_api_timeout() {
  fix_log "检测到 API 响应慢，尝试重试..."
  
  # 从知识库获取上次成功的等待时间
  local wait_time=$(cat "$KB_FILE" 2>/dev/null | grep -o '"optimal_wait_time":[0-9]*' | grep -o '[0-9]*' | head -1)
  wait_time=${wait_time:-3}
  
  sleep "$wait_time"
  
  local retry=$(curl -s -o /dev/null -w "%{http_code}" "https://blast-api.kanjiaming2022.workers.dev/" 2>/dev/null)
  if [ "$retry" = "200" ]; then
    fix_log "✅ API 重试成功 (等待 ${wait_time}s)"
    AUTO_FIXED+=("api_timeout_retry_success")
    update_knowledge "api_timeout" "success" "等待 ${wait_time}s 重试成功"
    return 0
  else
    fix_log "⚠️ API 重试失败，标记为需要人工处理"
    MANUAL_REQUIRED+=("api_timeout_persist")
    update_knowledge "api_timeout" "failed" "需要更长的等待时间"
    return 1
  fi
}

# 自动修复: 数据库连接
fix_db_connection() {
  fix_log "检测到数据库连接问题，执行重连..."
  
  # 测试简单查询
  local test=$(CLOUDFLARE_API_TOKEN="pim7CQ9qHmqMFYappuq2F0pr6FDo87_GJFbG5KhK" \
    CLOUDFLARE_ACCOUNT_ID="6a6fe3b0b250e0c6a09af24d01e0f9b6" \
    npx wrangler d1 execute blast-campaigns-db --command "SELECT 1" --remote 2>&1)
  
  if echo "$test" | grep -q "success"; then
    fix_log "✅ 数据库连接恢复"
    AUTO_FIXED+=("db_connection_restored")
    return 0
  else
    fix_log "⚠️ 数据库连接持续失败，通知管理员"
    MANUAL_REQUIRED+=("db_connection_failed")
    return 1
  fi
}

# 自动修复: 网站不可访问
fix_website_down() {
  fix_log "检测到网站不可访问，检查 CDN 状态..."
  
  # 等待 10 秒后重试
  sleep 10
  
  local retry=$(curl -s -o /dev/null -w "%{http_code}" "https://blastjunior.com/" 2>/dev/null)
  if [ "$retry" = "200" ]; then
    fix_log "✅ 网站已恢复"
    AUTO_FIXED+=("website_recovered")
    return 0
  else
    fix_log "⚠️ 网站持续不可访问，可能是 DNS 或 CDN 问题，需要人工处理"
    MANUAL_REQUIRED+=("website_down")
    return 1
  fi
}

# 知识库更新
update_knowledge() {
  local problem_type=$1
  local outcome=$2
  local lesson=$3
  
  # 简单的知识库更新逻辑
  # 实际实现应该读写 JSON 文件
  fix_log "🧠 记录经验: [$problem_type] $outcome - $lesson"
}

# 主修复逻辑
run_auto_fix() {
  echo "[$(date '+%Y-%m-%d %H:%M')] 🔧 自动修复开始" >> "$LOG_DIR/$(date '+%Y-%m-%d').log"
  
  # 根据健康状态决定修复策略
  if [ "$STATUS_API" = "RED" ]; then
    fix_api_timeout
  fi
  
  if [ "$STATUS_DB" = "RED" ]; then
    fix_db_connection
  fi
  
  if [ "$STATUS_WEB" = "RED" ]; then
    fix_website_down
  fi
  
  # 记录修复总结
  if [ ${#AUTO_FIXED[@]} -gt 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M')] ✅ 自动修复成功: ${AUTO_FIXED[*]}" >> "$LOG_DIR/$(date '+%Y-%m-%d').log"
  fi
  
  if [ ${#MANUAL_REQUIRED[@]} -gt 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M')] ⚠️ 需要人工处理: ${MANUAL_REQUIRED[*]}" >> "$LOG_DIR/$(date '+%Y-%m-%d').log"
  fi
}

run_auto_fix
