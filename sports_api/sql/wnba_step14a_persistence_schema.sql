-- WNBA Step 14A persistence schema contract.
-- DDL only. Step 14A performs no database reads/writes and creates no lease table.

CREATE SCHEMA IF NOT EXISTS kyre_runtime;

CREATE TABLE IF NOT EXISTS kyre_runtime.wnba_runtime_checkpoints (
    checkpoint_id uuid PRIMARY KEY,
    checkpoint_key text NOT NULL,
    checkpoint_version bigint NOT NULL CHECK (checkpoint_version >= 1),
    season integer NOT NULL CHECK (season = 2026),
    season_type text NOT NULL CHECK (season_type = 'Regular Season'),
    slate_date date NOT NULL,
    step13d_frozen_sha char(40) NOT NULL,
    step13_release_id text NOT NULL,
    step13_release_content_sha256 char(64) NOT NULL,
    source_step13c_frozen_sha char(40) NOT NULL,
    source_reliability_content_sha256 char(64) NOT NULL,
    controller_state_sha256 char(64) NOT NULL,
    envelope_content_sha256 char(64) NOT NULL,
    envelope_json jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT wnba_runtime_checkpoints_key_version_unique
        UNIQUE (checkpoint_key, checkpoint_version),
    CONSTRAINT wnba_runtime_checkpoints_key_envelope_unique
        UNIQUE (checkpoint_key, envelope_content_sha256),
    CONSTRAINT wnba_runtime_checkpoints_envelope_object
        CHECK (jsonb_typeof(envelope_json) = 'object'),
    CONSTRAINT wnba_runtime_checkpoints_step13_release_hash_len
        CHECK (length(step13_release_content_sha256) = 64),
    CONSTRAINT wnba_runtime_checkpoints_source_hash_len
        CHECK (length(source_reliability_content_sha256) = 64),
    CONSTRAINT wnba_runtime_checkpoints_state_hash_len
        CHECK (length(controller_state_sha256) = 64),
    CONSTRAINT wnba_runtime_checkpoints_envelope_hash_len
        CHECK (length(envelope_content_sha256) = 64)
);

CREATE TABLE IF NOT EXISTS kyre_runtime.wnba_runtime_checkpoint_heads (
    checkpoint_key text PRIMARY KEY,
    checkpoint_version bigint NOT NULL CHECK (checkpoint_version >= 1),
    checkpoint_id uuid NOT NULL,
    envelope_content_sha256 char(64) NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT wnba_runtime_checkpoint_heads_checkpoint_fk
        FOREIGN KEY (checkpoint_id)
        REFERENCES kyre_runtime.wnba_runtime_checkpoints(checkpoint_id)
        ON DELETE RESTRICT,
    CONSTRAINT wnba_runtime_checkpoint_heads_envelope_hash_len
        CHECK (length(envelope_content_sha256) = 64)
);

CREATE INDEX IF NOT EXISTS wnba_runtime_checkpoints_slate_created_idx
    ON kyre_runtime.wnba_runtime_checkpoints (slate_date, created_at DESC);

CREATE INDEX IF NOT EXISTS wnba_runtime_checkpoints_key_version_desc_idx
    ON kyre_runtime.wnba_runtime_checkpoints (checkpoint_key, checkpoint_version DESC);

COMMENT ON TABLE kyre_runtime.wnba_runtime_checkpoints IS
    'Append-only WNBA runtime checkpoint history defined by frozen Step 14A.';

COMMENT ON TABLE kyre_runtime.wnba_runtime_checkpoint_heads IS
    'One current checkpoint head per slate-scoped checkpoint key; later adapters use version as the compare-and-swap boundary.';
