#!/bin/bash
# BLXST 自主维护系统 - 主入口
# 每5分钟执行一次

DATE=$(date '+%Y-%m-%d %H:%M')
LOG_DIR="/root/.openclaw/workspace/logs/maintenance"
KB_FILE="/root/.openclaw/workspace/scripts/maintenance/knowledge-base.json"
REPORT_FILE="$LOG_DIR/report-$(date '+%Y-%m-%d').json"

# 确保日志目录存在
mkdir -p "$LOG_DIR"

# 记录开始时间
START_TIME=$(date +%s)

# 日志函数
log() {
  echo "[$DATE] $1" | tee -a "$LOG_DIR/$(date '+%Y-%m-%d').log"
}

# 检查是否为首次运行（初始化知识库）
init_knowledge_base() {
  if [ ! -f "$KB_FILE" ]; then
    log "📚 初始化知识库..."
    cat > "$KB_FILE" << 'EOF'
{
  "version": "1.0",
  "last_updated": "2026-04-18T00:00:00Z",
  "solutions": [],
  "patterns": [],
  "stats": {
    "total_incidents": 0,
    "auto_resolved": 0,
    "manual_required": 0
  }
}
EOF
  fi
}

# 主要流程
main() {
  log "========================================"
  log "🚀 BLXST 自主维护开始"
  log "========================================"
  
  # 1. 初始化
  init_knowledge_base
  
  # 2. 健康检测
  log "🔍 执行健康检测..."
  source /root/.openclaw/workspace/scripts/maintenance/health-check.sh
  
  # 3. 问题诊断与自动修复
  log "🔧 检查需要修复的问题..."
  source /root/.openclaw/workspace/scripts/maintenance/auto-fix.sh
  
  # 4. 知识库更新
  log "🧠 更新知识库..."
  source /root/.openclaw/workspace/scripts/maintenance/knowledge-update.sh
  
  # 5. 生成报告
  log "📊 生成维护报告..."
  source /root/.openclaw/workspace/scripts/maintenance/report-generator.sh
  
  END_TIME=$(date +%s)
  DURATION=$((END_TIME - START_TIME))
  log "✅ 维护完成，耗时 ${DURATION} 秒"
  log "========================================"
}

# 执行
main "$@"
