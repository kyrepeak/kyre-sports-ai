-- Runless V2 Task 8 performance hardening from Supabase advisor readback.
-- Cover the two foreign-key columns identified by the advisor.

create index if not exists runless_v2_failed_fingerprints_proof_id_idx
    on runless_v2.failed_fingerprints (proof_id);

create index if not exists runless_v2_workstream_leases_owner_proof_id_idx
    on runless_v2.workstream_leases (owner_proof_id);
