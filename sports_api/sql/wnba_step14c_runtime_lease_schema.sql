-- WNBA Step 14C durable cross-process scheduler lease.
-- Additive to the frozen Step 14A checkpoint schema; this file does not alter
-- Step 14A tables and does not activate any production/background runtime.

CREATE SCHEMA IF NOT EXISTS kyre_runtime;

CREATE TABLE IF NOT EXISTS kyre_runtime.wnba_runtime_leases (
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
    CHECK (expires_at > renewed_at)
);

CREATE INDEX IF NOT EXISTS wnba_runtime_leases_expires_idx
    ON kyre_runtime.wnba_runtime_leases (expires_at);
