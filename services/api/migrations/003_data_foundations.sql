BEGIN;
CREATE TABLE IF NOT EXISTS channels(id uuid PRIMARY KEY,user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,kind text NOT NULL CHECK(kind IN ('desktop','web','telegram','chrome')),external_id_hash text,revoked_at timestamptz,created_at timestamptz NOT NULL DEFAULT now(),UNIQUE(kind,external_id_hash));
CREATE TABLE IF NOT EXISTS memories(id uuid PRIMARY KEY,user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,conversation_id uuid REFERENCES conversations(id) ON DELETE CASCADE,kind text NOT NULL CHECK(kind IN ('summary','preference','semantic')),content text NOT NULL,source_message_id uuid REFERENCES messages(id) ON DELETE SET NULL,expires_at timestamptz,created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS data_retention(user_id uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,conversation_days int NOT NULL DEFAULT 365 CHECK(conversation_days BETWEEN 1 AND 3650),audit_days int NOT NULL DEFAULT 365 CHECK(audit_days BETWEEN 30 AND 3650),delete_requested_at timestamptz,delete_after timestamptz,updated_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS legacy_migrations(source_sha256 text PRIMARY KEY,source_label text NOT NULL,source_counts jsonb NOT NULL,imported_counts jsonb NOT NULL,completed_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS memories_user_updated ON memories(user_id,updated_at DESC);
CREATE INDEX IF NOT EXISTS channels_user_kind ON channels(user_id,kind);
COMMIT;
