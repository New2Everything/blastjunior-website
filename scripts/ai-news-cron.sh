#!/bin/bash
# AI-NEWS 自动生成脚本
# 每天早上8点执行：搜索HADO最新发布新闻资讯并

set -e

# 配置
TAVILY_API_KEY="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"
ADMIN_TOKEN="blx-admin-2025-super-secret"
NEWS_API_URL="https://blastjunior.com/news"

# 日志文件
LOG_FILE="/root/.openclaw/workspace/logs/ai-news-$(date +%Y-%m-%d).log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=== 开始AI-NEWS任务 ==="

# 1. 使用tavily搜索HADO最新资讯
log "搜索HADO最新资讯..."

export TAVILY_API_KEY

SEARCH_RESULT=$(/root/.openclaw/workspace/skills/tavily-search/scripts/search.mjs "HADO XR sports gaming AR" --topic news --days 7 -n 5 2>&1) || {
    log "错误：Tavily搜索失败"
    echo "$SEARCH_RESULT" >> "$LOG_FILE"
    exit 1
}

log "搜索完成"

# 解析搜索结果
# 提取answer部分作为新闻内容
ANSWER=$(echo "$SEARCH_RESULT" | sed -n '/^## Answer$/,/^---$/p' | sed '1d;$d' | head -c 1000)
SOURCES=$(echo "$SEARCH_RESULT" | sed -n '/^## Sources$/,$p' | tail -n +2)

# 如果没有answer，使用sources作为内容
if [ -z "$ANSWER" ]; then
    CONTENT="$SOURCES"
else
    CONTENT="$ANSWER\n\n---\n来源:\n$SOURCES"
fi

# 生成标题
TODAY=$(date +%Y年%m月%d日)
TITLE="AI-NEWS: HADO最新资讯 - $TODAY"

# 限制内容长度
CONTENT_TRUNCATED=$(echo -e "$CONTENT" | head -c 5000)

log "标题: $TITLE"
log "内容长度: $(echo -e "$CONTENT_TRUNCATED" | wc -c) 字符"

# 2. 调用news-admin-api发布新闻
log "发布新闻到blastjunior..."

RESPONSE=$(curl -s -X POST "$NEWS_API_URL" \
    -H "Content-Type: application/json" \
    -H "X-Admin-Token: $ADMIN_TOKEN" \
    -d "{
        \"title\": \"$TITLE\",
        \"content\": $(echo -e "$CONTENT_TRUNCATED" | jq -Rs .),
        \"author\": \"AI-Auto\",
        \"real_name\": \"AI自动生成\",
        \"category\": \"HADO\",
        \"sync_to_chat\": true
    }")

log "API响应: $RESPONSE"

# 检查是否成功
if echo "$RESPONSE" | grep -q '"ok":true'; then
    NEWS_ID=$(echo "$RESPONSE" | grep -o '"news_id":[0-9]*' | cut -d: -f2)
    log "新闻发布成功! ID: $NEWS_ID"
    
    if echo "$RESPONSE" | grep -q '"synced_to_chat":true'; then
        log "已同步到聊天室"
    fi
else
    ERROR=$(echo "$RESPONSE" | grep -o '"error":"[^"]*"' | cut -d'"' -f4)
    log "错误: $ERROR"
    exit 1
fi

log "=== AI-NEWS任务完成 ==="
