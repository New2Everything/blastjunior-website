#!/bin/bash
# BLXST 报告生成模块

LOG_DIR="/root/.openclaw/workspace/logs/maintenance"
REPORT_FILE="$LOG_DIR/report-$(date '+%Y-%m-%d').json"
HTML_REPORT="$LOG_DIR/report-$(date '+%Y-%m-%d').html"

# 引入状态
source /root/.openclaw/workspace/scripts/maintenance/health-check.sh 2>/dev/null

# 生成 JSON 报告
generate_json_report() {
  local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  
  cat > "$REPORT_FILE" << EOF
{
  "timestamp": "$timestamp",
  "health": {
    "api": "$STATUS_API",
    "database": "$STATUS_DB", 
    "website": "$STATUS_WEB",
    "members": "$STATUS_MEMBERS",
    "overall": "$OVERALL_STATUS",
    "api_response_time_ms": $API_RESPONSE_TIME,
    "member_count": $MEMBER_COUNT
  },
  "auto_actions": {
    "fixed": $(echo ${AUTO_FIXED[*]:-} | tr ' ' '\n' | wc -l),
    "manual_required": $(echo ${MANUAL_REQUIRED[*]:-} | tr ' ' '\n' | wc -l)
  },
  "next_check": "$(date -u -d '+5 minutes' +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -v+5M -u +"%Y-%m-%dT%H:%M:%SZ")"
}
EOF
}

# 生成 HTML 报告
generate_html_report() {
  local status_icon="✅"
  if [ "$OVERALL_STATUS" = "YELLOW" ]; then
    status_icon="⚠️"
  elif [ "$OVERALL_STATUS" = "RED" ]; then
    status_icon="🚨"
  fi
  
  cat > "$HTML_REPORT" << EOF
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>BLXST 维护报告 - $(date '+%Y-%m-%d %H:%M')</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background: #f5f5f5; }
    .card { background: white; border-radius: 12px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
    .status { font-size: 24px; margin-bottom: 10px; }
    .status-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #eee; }
    .status-row:last-child { border-bottom: none; }
    .green { color: #22c55e; } .yellow { color: #eab308; } .red { color: #ef4444; }
    .badge { display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }
    .badge-green { background: #dcfce7; color: #166534; } .badge-yellow { background: #fef9c3; color: #854d0e; } .badge-red { background: #fee2e2; color: #991b1b; }
    .timestamp { color: #666; font-size: 14px; }
  </style>
</head>
<body>
  <div class="card">
    <div class="status">$status_icon BLXST 维护报告</div>
    <div class="timestamp">生成时间: $(date '+%Y-%m-%d %H:%M:%S')</div>
  </div>
  
  <div class="card">
    <h3 style="margin-top:0;">🔍 健康状态</h3>
    <div class="status-row">
      <span>API 服务</span>
      <span class="badge badge-${STATUS_API,,}">$STATUS_API (${API_RESPONSE_TIME}ms)</span>
    </div>
    <div class="status-row">
      <span>数据库</span>
      <span class="badge badge-${STATUS_DB,,}">$STATUS_DB</span>
    </div>
    <div class="status-row">
      <span>网站</span>
      <span class="badge badge-${STATUS_WEB,,}">$STATUS_WEB</span>
    </div>
    <div class="status-row">
      <span>俱乐部成员</span>
      <span class="badge badge-green">$MEMBER_COUNT 人</span>
    </div>
  </div>
  
  <div class="card">
    <h3 style="margin-top:0;">🤖 自动执行</h3>
    <div class="status-row">
      <span>自动修复</span>
      <span>$(echo ${AUTO_FIXED[*]:-无})</span>
    </div>
    <div class="status-row">
      <span>需人工处理</span>
      <span>$(echo ${MANUAL_REQUIRED[*]:-无})</span>
    </div>
  </div>
  
  <div class="card">
    <h3 style="margin-top:0;">📊 趋势</h3>
    <p style="color:#666;">查看完整趋势分析请访问日志目录</p>
    <p class="timestamp">日志位置: $LOG_DIR/</p>
  </div>
</body>
</html>
EOF
}

# 主流程
generate_reports() {
  generate_json_report
  generate_html_report
  
  echo "[$(date '+%Y-%m-%d %H:%M')] 📊 报告已生成:" >> "$LOG_DIR/$(date '+%Y-%m-%d').log"
  echo "  - JSON: $REPORT_FILE" >> "$LOG_DIR/$(date '+%Y-%m-%d').log"
  echo "  - HTML: $HTML_REPORT" >> "$LOG_DIR/$(date '+%Y-%m-%d').log"
}

generate_reports
