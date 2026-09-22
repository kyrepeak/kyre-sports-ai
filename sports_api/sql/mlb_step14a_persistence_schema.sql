-- MLB Step 14A scheduler/recovery persistence schema contract.
-- DDL only. Step 14A performs no database reads or writes and defines no lease table.

CREATE SCHEMA IF NOT EXISTS kyre_runtime;

CREATE TABLE IF NOT EXISTS kyre_runtime.mlb_runtime_checkpoints (
    checkpoint_id uuid PRIMARY KEY,
    checkpoint_key text NOT NULL,
    checkpoint_version bigint NOT NULL CHECK (checkpoint_version >= 1),
    season integer NOT NULL CHECK (season = 2026),
    season_type text NOT NULL CHECK (season_type = 'Regular Season'),
    slate_date date NOT NULL,
    step13d_merge_sha char(40) NOT NULL,
    step13d_source_blob_sha char(40) NOT NULL,
    step13d_freeze_manifest_sha256 char(64) NOT NULL,
    source_reliability_sha256 char(64) NOT NULL,
    source_supervision_sha256 char(64) NOT NULL,
    cycle_id char(64),
    cycle_slot_utc timestamptz,
    scheduler_state_sha256 char(64) NOT NULL,
    recovery_state_sha256 char(64) NOT NULL,
    recovery_handoff_sha256 char(64) NOT NULL,
    envelope_content_sha256 char(64) NOT NULL,
    envelope_json jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT mlb_runtime_checkpoints_key_version_unique
        UNIQUE (checkpoint_key, checkpoint_version),
    CONSTRAINT mlb_runtime_checkpoints_key_envelope_unique
        UNIQUE (checkpoint_key, envelope_content_sha256),
    CONSTRAINT mlb_runtime_checkpoints_envelope_object
        CHECK (jsonb_typeof(envelope_json) = 'object'),
    CONSTRAINT mlb_runtime_checkpoints_cycle_identity_pair
        CHECK ((cycle_id IS NULL AND cycle_slot_utc IS NULL) OR
               (cycle_id IS NOT NULL AND cycle_slot_utc IS NOT NULL)),
    CONSTRAINT mlb_runtime_checkpoints_step13d_merge_sha_len
        CHECK (length(step13d_merge_sha) = 40),
    CONSTRAINT mlb_runtime_checkpoints_step13d_blob_sha_len
        CHECK (length(step13d_source_blob_sha) = 40),
    CONSTRAINT mlb_runtime_checkpoints_step13d_manifest_hash_len
        CHECK (length(step13d_freeze_manifest_sha256) = 64),
    CONSTRAINT mlb_runtime_checkpoints_source_reliability_hash_len
        CHECK (length(source_reliability_sha256) = 64),
    CONSTRAINT mlb_runtime_checkpoints_source_supervision_hash_len
        CHECK (length(source_supervision_sha256) = 64),
    CONSTRAINT mlb_runtime_checkpoints_scheduler_state_hash_len
        CHECK (length(scheduler_state_sha256) = 64),
    CONSTRAINT mlb_runtime_checkpoints_recovery_state_hash_len
        CHECK (length(recovery_state_sha256) = 64),
    CONSTRAINT mlb_runtime_checkpoints_recovery_handoff_hash_len
        CHECK (length(recovery_handoff_sha256) = 64),
    CONSTRAINT mlb_runtime_checkpoints_envelope_hash_len
        CHECK (length(envelope_content_sha256) = 64)
);

CREATE TABLE IF NOT EXISTS kyre_runtime.mlb_runtime_checkpoint_heads (
    checkpoint_key text PRIMARY KEY,
    checkpoint_version bigint NOT NULL CHECK (checkpoint_version >= 1),
    checkpoint_id uuid NOT NULL,
    envelope_content_sha256 char(64) NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT mlb_runtime_checkpoint_heads_checkpoint_fk
        FOREIGN KEY (checkpoint_id)
        REFERENCES kyre_runtime.mlb_runtime_checkpoints(checkpoint_id)
        ON DELETE RESTRICT,
    CONSTRAINT mlb_runtime_checkpoint_heads_envelope_hash_len
        CHECK (length(envelope_content_sha256) = 64)
);

CREATE INDEX IF NOT EXISTS mlb_runtime_checkpoints_slate_created_idx
    ON kyre_runtime.mlb_runtime_checkpoints (slate_date, created_at DESC);

CREATE INDEX IF NOT EXISTS mlb_runtime_checkpoints_key_version_desc_idx
    ON kyre_runtime.mlb_runtime_checkpoints (checkpoint_key, checkpoint_version DESC);

CREATE INDEX IF NOT EXISTS mlb_runtime_checkpoints_cycle_idx
    ON kyre_runtime.mlb_runtime_checkpoints (cycle_id, created_at DESC)
    WHERE cycle_id IS NOT NULL;

COMMENT ON TABLE kyre_runtime.mlb_runtime_checkpoints IS
    'Append-only MLB scheduler/recovery checkpoint history defined by frozen Step 14A.';

COMMENT ON TABLE kyre_runtime.mlb_runtime_checkpoint_heads IS
    'One current MLB checkpoint head per slate-scoped key; later adapters use checkpoint_version as a compare-and-swap boundary.';
