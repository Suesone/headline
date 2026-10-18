-- Only quota metadata is stored, never news text, translations, email, or keys.
CREATE TABLE IF NOT EXISTS daily_budget (
  day TEXT PRIMARY KEY,
  requests INTEGER NOT NULL DEFAULT 0,
  paused INTEGER NOT NULL DEFAULT 0
);
