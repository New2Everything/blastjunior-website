-- BLXST 用户系统数据库 schema
-- D1: blast-user-db

-- 用户表
CREATE TABLE users (
  user_id TEXT PRIMARY KEY,
  email TEXT UNIQUE NOT NULL,
  username TEXT,
  avatar_url TEXT,
  role TEXT DEFAULT 'member',
  username_changed INTEGER DEFAULT 0,  -- 是否已经修改过昵称
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME
);

-- 验证码表
CREATE TABLE verification_codes (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL,
  code TEXT NOT NULL,
  purpose TEXT NOT NULL,  -- register, login, reset
  expires_at DATETIME NOT NULL,
  used_at DATETIME,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 创建索引
CREATE INDEX idx_verification_codes_email ON verification_codes(email);
CREATE INDEX idx_verification_codes_code ON verification_codes(code);

-- 插入一个测试用户 (password: test123)
-- INSERT INTO users (user_id, email, username, role, password_hash)
-- VALUES ('test-user-001', 'test@blastjunior.com', '测试用户', 'member', 'ecd71870d1963316a97e3ac3408c9835ad8cf0f3c1bc703527c30265534f75ae');
