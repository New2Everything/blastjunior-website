-- 评论表 SQL
-- 数据库: blast-user-db (D1)
-- 创建时间: 2026-03-07

-- 创建 comments 表
CREATE TABLE IF NOT EXISTS comments (
  comment_id TEXT PRIMARY KEY,
  target_type TEXT NOT NULL,
  target_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  content TEXT NOT NULL,
  status TEXT DEFAULT 'pending',
  ai_review_result TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引（可选，提升查询性能）
CREATE INDEX IF NOT EXISTS idx_comments_target ON comments(target_type, target_id);
CREATE INDEX IF NOT EXISTS idx_comments_status ON comments(status);
CREATE INDEX IF NOT EXISTS idx_comments_user ON comments(user_id);

-- 查看表结构
-- SELECT sql FROM sqlite_master WHERE type='table' AND name='comments';

-- 查看所有评论
-- SELECT c.*, u.username FROM comments c JOIN users u ON c.user_id = u.user_id;

-- 按target查询评论（已审核）
-- SELECT c.*, u.username, u.avatar_url 
-- FROM comments c 
-- JOIN users u ON c.user_id = u.user_id 
-- WHERE c.target_type = 'news' AND c.target_id = '1' AND c.status = 'approved'
-- ORDER BY c.created_at DESC;
