CREATE SCHEMA IF NOT EXISTS kyre_runtime;

CREATE TABLE IF NOT EXISTS kyre_runtime.mlb_step19_live_data_checkpoints (
    checkpoint_id uuid PRIMARY KEY,
    checkpoint_key text NOT NULL,
    checkpoint_version bigint NOT NULL CHECK (checkpoint_version >= 1),
    slate_date date NOT NULL,
    contract_version text NOT NULL,
    official_slate_sha256 char(64) NOT NULL,
    market_feed_sha256 char(64) NOT NULL,
    identity_registry_sha256 char(64) NOT NULL,
    reliability_state_sha256 char(64) NOT NULL,
    envelope_content_sha256 char(64) NOT NULL,
    envelope_json jsonb NOT NULL,
    created_at timestamptz NOT NULL,
    UNIQUE (checkpoint_key, checkpoint_version),
    UNIQUE (checkpoint_key, envelope_content_sha256)
);

CREATE TABLE IF NOT EXISTS kyre_runtime.mlb_step19_live_data_checkpoint_heads (
    checkpoint_key text PRIMARY KEY,
    checkpoint_version bigint NOT NULL CHECK (checkpoint_version >= 1),
    checkpoint_id uuid NOT NULL REFERENCES kyre_runtime.mlb_step19_live_data_checkpoints(checkpoint_id),
    envelope_content_sha256 char(64) NOT NULL,
    updated_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS mlb_step19_live_data_checkpoints_slate_created_idx
    ON kyre_runtime.mlb_step19_live_data_checkpoints (slate_date, created_at DESC);
