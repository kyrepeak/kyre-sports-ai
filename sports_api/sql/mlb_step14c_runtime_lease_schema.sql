-- MLB Step 14C durable cross-process scheduler/recovery lease.
-- Additive to the frozen Step 14A checkpoint schema. This file defines only
-- the lease table and does not alter Step 14A/14B tables or activate runtime.

CREATE SCHEMA IF NOT EXISTS kyre_runtime;

CREATE TABLE IF NOT EXISTS kyre_runtime.mlb_runtime_leases (
    lease_key text PRIMARY KEY,
    owner_id text NOT NULL,
    lease_token uuid NOT NULL,
    fencing_generation bigint NOT NULL CHECK (fencing_generation >= 1),
    acquired_at timestamptz NOT NULL,
    renewed_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (length(lease_key) BETWEEN 1 AND 255),
    CHECK (length(owner_id) BETWEEN 1 AND 255),
    CHECK (acquired_at <= renewed_at),
    CHECK (expires_at > renewed_at)
);

CREATE INDEX IF NOT EXISTS mlb_runtime_leases_expires_idx
    ON kyre_runtime.mlb_runtime_leases (expires_at);

COMMENT ON TABLE kyre_runtime.mlb_runtime_leases IS
    'MLB Step 14C cross-process scheduler/recovery lease with UUID ownership token and monotonic fencing generation.';
