-- user_uploads 表 - 用户上传系统
-- 用于存储用户上传的照片和新闻投稿

CREATE TABLE IF NOT EXISTS user_uploads (
  upload_id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  upload_type TEXT NOT NULL,  -- 'photo', 'news'
  title TEXT,
  content TEXT,
  file_url TEXT,
  status TEXT DEFAULT 'pending',  -- 'pending', 'approved', 'rejected'
  ai_review_result TEXT,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users(user_id)
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_uploads_user_id ON user_uploads(user_id);
CREATE INDEX IF NOT EXISTS idx_uploads_status ON user_uploads(status);
CREATE INDEX IF NOT EXISTS idx_uploads_type ON user_uploads(upload_type);
CREATE INDEX IF NOT EXISTS idx_uploads_created ON user_uploads(created_at DESC);
