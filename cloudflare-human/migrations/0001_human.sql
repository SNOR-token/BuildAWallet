CREATE TABLE IF NOT EXISTS wallets (
  code TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  spec TEXT NOT NULL,
  email TEXT,
  is_public INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_wallets_public ON wallets(is_public, created_at DESC);
