BEGIN;

CREATE TABLE IF NOT EXISTS jobs(
  id uuid PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  conversation_id uuid REFERENCES conversations(id) ON DELETE SET NULL,
  idempotency_key text NOT NULL,
  kind text NOT NULL,
  input jsonb NOT NULL,
  status text NOT NULL CHECK(status IN ('queued','running','waiting_approval','succeeded','failed','cancelled')),
  priority int NOT NULL DEFAULT 0,
  attempt int NOT NULL DEFAULT 0,
  max_attempts int NOT NULL DEFAULT 3,
  estimated_cost_cents int NOT NULL DEFAULT 0,
  actual_cost_cents int NOT NULL DEFAULT 0,
  available_at timestamptz NOT NULL DEFAULT now(),
  heartbeat_at timestamptz,
  locked_by text,
  last_error text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  UNIQUE(user_id,idempotency_key)
);
CREATE INDEX IF NOT EXISTS jobs_claimable ON jobs(status,available_at,priority DESC,created_at);

CREATE TABLE IF NOT EXISTS job_attempts(
  id uuid PRIMARY KEY,
  job_id uuid NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  attempt int NOT NULL,
  worker_id text NOT NULL,
  started_at timestamptz NOT NULL DEFAULT now(),
  heartbeat_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  outcome text,
  error_code text,
  UNIQUE(job_id,attempt)
);

CREATE TABLE IF NOT EXISTS agent_runs(
  id uuid PRIMARY KEY,
  job_id uuid NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  agent text NOT NULL,
  model text,
  status text NOT NULL,
  input_hash text NOT NULL,
  output jsonb,
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz
);

CREATE TABLE IF NOT EXISTS tool_calls(
  id uuid PRIMARY KEY,
  agent_run_id uuid NOT NULL REFERENCES agent_runs(id) ON DELETE CASCADE,
  tool text NOT NULL,
  input_hash text NOT NULL,
  status text NOT NULL,
  output jsonb,
  error_code text,
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz
);

CREATE TABLE IF NOT EXISTS artifacts(
  id uuid PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  job_id uuid REFERENCES jobs(id) ON DELETE SET NULL,
  storage_key text NOT NULL,
  name text NOT NULL,
  mime_type text NOT NULL,
  size bigint NOT NULL,
  sha256 text NOT NULL,
  status text NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(user_id,sha256,storage_key)
);

CREATE TABLE IF NOT EXISTS outbox(
  id uuid PRIMARY KEY,
  aggregate_type text NOT NULL,
  aggregate_id uuid NOT NULL,
  event_type text NOT NULL,
  payload jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  published_at timestamptz,
  attempts int NOT NULL DEFAULT 0,
  last_error text
);
CREATE INDEX IF NOT EXISTS outbox_unpublished ON outbox(created_at) WHERE published_at IS NULL;

CREATE TABLE IF NOT EXISTS usage_events(
  id uuid PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  job_id uuid REFERENCES jobs(id) ON DELETE SET NULL,
  provider text NOT NULL,
  model text NOT NULL,
  input_tokens int NOT NULL DEFAULT 0,
  output_tokens int NOT NULL DEFAULT 0,
  cost_cents int NOT NULL DEFAULT 0,
  latency_ms int NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now()
);

COMMIT;
