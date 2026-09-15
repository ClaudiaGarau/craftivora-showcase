BEGIN;
CREATE TABLE IF NOT EXISTS users(id uuid PRIMARY KEY,email text UNIQUE NOT NULL,name text NOT NULL,avatar_url text,created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS sessions(id uuid PRIMARY KEY,user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,refresh_hash text NOT NULL,expires_at timestamptz NOT NULL,revoked_at timestamptz,rotated_from uuid,created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS conversations(id uuid PRIMARY KEY,user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,title text NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS messages(id uuid PRIMARY KEY,conversation_id uuid NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,role text NOT NULL,content text NOT NULL,channel text NOT NULL,created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS approvals(id uuid PRIMARY KEY,user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,action text NOT NULL,target text NOT NULL,risk text NOT NULL,data_summary text NOT NULL,consequences text NOT NULL,estimated_cost_cents int NOT NULL DEFAULT 0,status text NOT NULL DEFAULT 'pending',expires_at timestamptz NOT NULL,decided_at timestamptz,created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS audit_log(id bigserial PRIMARY KEY,user_id uuid,action text NOT NULL,target text,outcome text NOT NULL,metadata jsonb NOT NULL DEFAULT '{}',created_at timestamptz NOT NULL DEFAULT now());
COMMIT;
