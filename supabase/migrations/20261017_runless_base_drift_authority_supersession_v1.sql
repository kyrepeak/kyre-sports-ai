-- Audited Runless V2 recovery for MERGE_AUTHORIZED candidates made stale only by verified base drift.
-- This migration adds historical authority retirement; it does not authorize or prove a successor.

alter table runless_v2.proof_runs
    drop constraint if exists proof_runs_state_check;

alter table runless_v2.proof_runs
    add constraint proof_runs_state_check check (state in (
        'IDENTIFY','2A_LOCK','FINGERPRINT','REUSE_OR_PROVE','PUBLIC_CHECK_IF_REQUIRED',
        'RECEIPT','RUNLESS_FINAL_GATE','MERGE_AUTHORIZED','SUPERSEDED_BASE_DRIFT',
        'MERGED','POST_MERGE_VERIFY','FREEZE','READ_BACK','GREEN_FROZEN','FAILED'
    ));

create table if not exists runless_v2.authority_supersessions (
    supersession_id text primary key,
    workstream text not null,
    old_proof_id text not null references runless_v2.proof_runs(proof_id),
    old_candidate_sha text not null check (old_candidate_sha ~ '^[0-9a-f]{40}$'),
    old_expected_main_sha text null check (old_expected_main_sha is null or old_expected_main_sha ~ '^[0-9a-f]{40}$'),
    successor_candidate_sha text not null check (successor_candidate_sha ~ '^[0-9a-f]{40}$'),
    successor_expected_main_sha text not null check (successor_expected_main_sha ~ '^[0-9a-f]{40}$'),
    reason text not null check (reason = 'BASE_DRIFT'),
    github_pr_number bigint null check (github_pr_number is null or github_pr_number > 0),
    github_branch text not null check (length(github_branch) > 0),
    old_gate_check_run_id bigint not null,
    old_receipt_digest text not null,
    created_at timestamptz not null default clock_timestamp(),
    unique (old_proof_id),
    unique (workstream, successor_candidate_sha)
);

create index if not exists runless_v2_authority_supersessions_workstream_created_idx
    on runless_v2.authority_supersessions (workstream, created_at desc);

create or replace function runless_v2.is_legal_transition(p_expected_state text, p_target_state text)
returns boolean
language sql
immutable
as $$
    select case p_expected_state
        when 'IDENTIFY' then p_target_state in ('2A_LOCK','FAILED')
        when '2A_LOCK' then p_target_state in ('FINGERPRINT','FAILED')
        when 'FINGERPRINT' then p_target_state in ('REUSE_OR_PROVE','FAILED')
        when 'REUSE_OR_PROVE' then p_target_state in ('PUBLIC_CHECK_IF_REQUIRED','FAILED')
        when 'PUBLIC_CHECK_IF_REQUIRED' then p_target_state in ('RECEIPT','FAILED')
        when 'RECEIPT' then p_target_state in ('RUNLESS_FINAL_GATE','FAILED')
        when 'RUNLESS_FINAL_GATE' then p_target_state in ('MERGE_AUTHORIZED','FAILED')
        when 'MERGE_AUTHORIZED' then p_target_state in ('MERGED','SUPERSEDED_BASE_DRIFT')
        when 'MERGED' then p_target_state = 'POST_MERGE_VERIFY'
        when 'POST_MERGE_VERIFY' then p_target_state = 'FREEZE'
        when 'FREEZE' then p_target_state = 'READ_BACK'
        when 'READ_BACK' then p_target_state = 'GREEN_FROZEN'
        else false
    end;
$$;

create or replace function runless_v2.supersede_base_drift_authority(
    p_workstream text,
    p_task_id text,
    p_old_proof_id text,
    p_old_candidate_sha text,
    p_successor_candidate_sha text,
    p_successor_expected_main_sha text,
    p_github_pr_number bigint,
    p_github_branch text
)
returns runless_v2.authority_supersessions
language plpgsql
security definer
set search_path = runless_v2, extensions, public
as $$
declare
    v_now timestamptz := clock_timestamp();
    v_old runless_v2.proof_runs%rowtype;
    v_existing runless_v2.authority_supersessions%rowtype;
    v_result runless_v2.authority_supersessions%rowtype;
    v_supersession_id text;
begin
    if coalesce(p_workstream, '') = '' or coalesce(p_task_id, '') = ''
       or coalesce(p_old_proof_id, '') = '' or coalesce(p_github_branch, '') = '' then
        raise exception 'RUNLESS_V2_SUPERSESSION_IDENTITY_REQUIRED';
    end if;
    if p_old_candidate_sha !~ '^[0-9a-f]{40}$'
       or p_successor_candidate_sha !~ '^[0-9a-f]{40}$'
       or p_successor_expected_main_sha !~ '^[0-9a-f]{40}$' then
        raise exception 'RUNLESS_V2_SUPERSESSION_SHA_INVALID';
    end if;
    if p_github_pr_number is null or p_github_pr_number <= 0 then
        raise exception 'RUNLESS_V2_SUPERSESSION_PR_INVALID';
    end if;

    perform pg_advisory_xact_lock(hashtextextended(p_workstream, 0));

    select * into v_old
      from runless_v2.proof_runs
     where proof_id = p_old_proof_id
     for update;
    if not found then
        raise exception 'RUNLESS_V2_SUPERSESSION_OLD_PROOF_NOT_FOUND';
    end if;

    if v_old.workstream <> p_workstream
       or v_old.task_id <> p_task_id
       or v_old.candidate_sha <> p_old_candidate_sha then
        raise exception 'RUNLESS_V2_SUPERSESSION_OLD_IDENTITY_MISMATCH';
    end if;

    select * into v_existing
      from runless_v2.authority_supersessions
     where old_proof_id = p_old_proof_id;
    if found then
        if v_existing.workstream <> p_workstream
           or v_existing.old_candidate_sha <> p_old_candidate_sha
           or v_existing.successor_candidate_sha <> p_successor_candidate_sha
           or v_existing.successor_expected_main_sha <> p_successor_expected_main_sha
           or coalesce(v_existing.github_pr_number, -1) <> p_github_pr_number
           or v_existing.github_branch <> p_github_branch then
            raise exception 'RUNLESS_V2_SUPERSESSION_IDENTITY_COLLISION';
        end if;
        return v_existing;
    end if;

    if v_old.state <> 'MERGE_AUTHORIZED' then
        raise exception 'RUNLESS_V2_SUPERSESSION_OLD_STATE_INVALID';
    end if;
    if p_successor_candidate_sha = p_old_candidate_sha then
        raise exception 'RUNLESS_V2_SUPERSESSION_SUCCESSOR_UNCHANGED';
    end if;
    if coalesce(v_old.expected_main_sha, '') = p_successor_expected_main_sha then
        raise exception 'RUNLESS_V2_SUPERSESSION_MAIN_UNCHANGED';
    end if;
    if v_old.receipt_digest is null or v_old.gate_check_run_id is null then
        raise exception 'RUNLESS_V2_SUPERSESSION_MISSING_EVIDENCE';
    end if;

    if exists (
        select 1 from runless_v2.workstream_leases
         where workstream = p_workstream
           and expires_at > v_now
    ) then
        raise exception 'RUNLESS_V2_SUPERSESSION_WORKSTREAM_BUSY';
    end if;

    if exists (
        select 1
          from runless_v2.proof_runs p
         where p.workstream = p_workstream
           and p.proof_id <> p_old_proof_id
           and p.state in ('MERGE_AUTHORIZED','MERGED','POST_MERGE_VERIFY','FREEZE','READ_BACK')
    ) then
        raise exception 'RUNLESS_V2_SUPERSESSION_AUTHORITY_CONFLICT';
    end if;

    v_supersession_id := 'base-drift-' || encode(
        extensions.digest(
            concat_ws(E'\x1f', p_workstream, p_old_proof_id, p_old_candidate_sha,
                      p_successor_candidate_sha, p_successor_expected_main_sha,
                      p_github_pr_number::text, p_github_branch)::bytea,
            'sha256'
        ),
        'hex'
    );

    insert into runless_v2.authority_supersessions (
        supersession_id, workstream, old_proof_id, old_candidate_sha, old_expected_main_sha,
        successor_candidate_sha, successor_expected_main_sha, reason,
        github_pr_number, github_branch, old_gate_check_run_id, old_receipt_digest, created_at
    ) values (
        v_supersession_id, p_workstream, p_old_proof_id, p_old_candidate_sha, v_old.expected_main_sha,
        p_successor_candidate_sha, p_successor_expected_main_sha, 'BASE_DRIFT',
        p_github_pr_number, p_github_branch, v_old.gate_check_run_id, v_old.receipt_digest, v_now
    )
    returning * into v_result;

    update runless_v2.proof_runs
       set state = 'SUPERSEDED_BASE_DRIFT',
           detail = 'RUNLESS_V2_BASE_DRIFT_AUTHORITY_SUPERSEDED:' || v_supersession_id,
           terminal_at = v_now,
           updated_at = v_now
     where proof_id = p_old_proof_id
       and state = 'MERGE_AUTHORIZED';
    if not found then
        raise exception 'RUNLESS_V2_SUPERSESSION_OLD_STATE_INVALID';
    end if;

    return v_result;
end;
$$;

revoke all on table runless_v2.authority_supersessions from public, anon, authenticated;
grant select on table runless_v2.authority_supersessions to service_role;

revoke all on function runless_v2.supersede_base_drift_authority(text,text,text,text,text,text,bigint,text)
from public, anon, authenticated;
grant execute on function runless_v2.supersede_base_drift_authority(text,text,text,text,text,text,bigint,text)
to service_role;
