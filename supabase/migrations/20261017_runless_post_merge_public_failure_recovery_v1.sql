-- Runless V2: truthfully retire an authority whose candidate actually merged
-- but then failed public post-merge verification. GitHub merge identity and
-- main ancestry are verified server-side before durable state changes.

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
        when 'MERGED' then p_target_state in ('POST_MERGE_VERIFY','FAILED')
        when 'POST_MERGE_VERIFY' then p_target_state in ('FREEZE','FAILED')
        when 'FREEZE' then p_target_state = 'READ_BACK'
        when 'READ_BACK' then p_target_state = 'GREEN_FROZEN'
        else false
    end;
$$;

create or replace function runless_v2.record_post_merge_public_failure(
    p_repository text,
    p_workstream text,
    p_task_id text,
    p_proof_id text,
    p_candidate_sha text,
    p_merged_main_sha text,
    p_pr_number bigint,
    p_detail text
)
returns runless_v2.proof_runs
language plpgsql
security definer
set search_path = runless_v2, extensions, public
as $$
declare
    v_now timestamptz := clock_timestamp();
    v_proof runless_v2.proof_runs%rowtype;
    v_response extensions.http_response;
    v_pr jsonb;
    v_compare jsonb;
    v_main jsonb;
    v_current_main_sha text;
    v_detail_digest text;
    v_headers extensions.http_header[] := array[
        row('Accept','application/vnd.github+json')::extensions.http_header,
        row('User-Agent','kyre-runless-v2')::extensions.http_header,
        row('X-GitHub-Api-Version','2022-11-28')::extensions.http_header
    ];
begin
    if p_repository <> 'kyrepeak/kyre-sports-ai' then
        raise exception 'RUNLESS_V2_POST_MERGE_FAILURE_REPOSITORY_MISMATCH';
    end if;
    if p_candidate_sha !~ '^[0-9a-f]{40}$' or p_merged_main_sha !~ '^[0-9a-f]{40}$' then
        raise exception 'RUNLESS_V2_POST_MERGE_FAILURE_SHA_INVALID';
    end if;
    if coalesce(p_workstream,'')='' or coalesce(p_task_id,'')=''
       or coalesce(p_proof_id,'')='' or coalesce(p_detail,'')='' then
        raise exception 'RUNLESS_V2_POST_MERGE_FAILURE_IDENTITY_REQUIRED';
    end if;
    if p_pr_number is null or p_pr_number <= 0 then
        raise exception 'RUNLESS_V2_POST_MERGE_FAILURE_PR_INVALID';
    end if;

    -- Verify exact merged PR identity from GitHub first.
    select * into v_response
      from extensions.http((
        'GET'::extensions.http_method,
        'https://api.github.com/repos/kyrepeak/kyre-sports-ai/pulls/' || p_pr_number::text,
        v_headers, null, null
      )::extensions.http_request);
    if v_response.status < 200 or v_response.status >= 300 then
        raise exception 'RUNLESS_V2_POST_MERGE_GITHUB_PR_HTTP_%', v_response.status;
    end if;
    v_pr := coalesce(v_response.content,'{}')::jsonb;
    if coalesce((v_pr->>'merged')::boolean,false) is not true
       or coalesce(v_pr->>'merged_at','')=''
       or coalesce(v_pr->>'merge_commit_sha','') <> p_merged_main_sha
       or coalesce(v_pr#>>'{head,sha}','') <> p_candidate_sha
       or coalesce(v_pr#>>'{head,repo,full_name}','') <> p_repository
       or coalesce(v_pr#>>'{base,repo,full_name}','') <> p_repository then
        raise exception 'RUNLESS_V2_POST_MERGE_GITHUB_IDENTITY_MISMATCH';
    end if;

    -- Candidate must be an ancestor of the recorded merge commit.
    select * into v_response
      from extensions.http((
        'GET'::extensions.http_method,
        'https://api.github.com/repos/kyrepeak/kyre-sports-ai/compare/' || p_candidate_sha || '...' || p_merged_main_sha,
        v_headers, null, null
      )::extensions.http_request);
    if v_response.status < 200 or v_response.status >= 300 then
        raise exception 'RUNLESS_V2_POST_MERGE_GITHUB_CANDIDATE_COMPARE_HTTP_%', v_response.status;
    end if;
    v_compare := coalesce(v_response.content,'{}')::jsonb;
    if coalesce(v_compare->>'status','') not in ('ahead','identical') then
        raise exception 'RUNLESS_V2_POST_MERGE_CANDIDATE_NOT_MERGED';
    end if;

    -- Resolve current main, then require the merge commit to remain in main history.
    select * into v_response
      from extensions.http((
        'GET'::extensions.http_method,
        'https://api.github.com/repos/kyrepeak/kyre-sports-ai/git/ref/heads/main',
        v_headers, null, null
      )::extensions.http_request);
    if v_response.status < 200 or v_response.status >= 300 then
        raise exception 'RUNLESS_V2_POST_MERGE_GITHUB_MAIN_HTTP_%', v_response.status;
    end if;
    v_main := coalesce(v_response.content,'{}')::jsonb;
    v_current_main_sha := coalesce(v_main#>>'{object,sha}','');
    if v_current_main_sha !~ '^[0-9a-f]{40}$' then
        raise exception 'RUNLESS_V2_POST_MERGE_CURRENT_MAIN_SHA_INVALID';
    end if;

    select * into v_response
      from extensions.http((
        'GET'::extensions.http_method,
        'https://api.github.com/repos/kyrepeak/kyre-sports-ai/compare/' || p_merged_main_sha || '...' || v_current_main_sha,
        v_headers, null, null
      )::extensions.http_request);
    if v_response.status < 200 or v_response.status >= 300 then
        raise exception 'RUNLESS_V2_POST_MERGE_GITHUB_MAIN_COMPARE_HTTP_%', v_response.status;
    end if;
    v_compare := coalesce(v_response.content,'{}')::jsonb;
    if coalesce(v_compare->>'status','') not in ('ahead','identical') then
        raise exception 'RUNLESS_V2_POST_MERGE_NOT_IN_MAIN_HISTORY';
    end if;

    -- Only after GitHub proof succeeds do we lock and mutate Runless state.
    select * into v_proof
      from runless_v2.proof_runs
     where proof_id = p_proof_id
     for update;
    if not found then raise exception 'RUNLESS_V2_PROOF_NOT_FOUND'; end if;
    perform pg_advisory_xact_lock(hashtextextended(v_proof.workstream, 0));

    if v_proof.workstream <> p_workstream
       or v_proof.task_id <> p_task_id
       or v_proof.candidate_sha <> p_candidate_sha then
        raise exception 'RUNLESS_V2_POST_MERGE_FAILURE_IDENTITY_MISMATCH';
    end if;
    if v_proof.receipt_digest is null or v_proof.gate_check_run_id is null then
        raise exception 'RUNLESS_V2_POST_MERGE_FAILURE_MISSING_EVIDENCE';
    end if;
    if exists (select 1 from runless_v2.workstream_leases where workstream = p_workstream) then
        raise exception 'RUNLESS_V2_WORKSTREAM_BUSY';
    end if;

    if v_proof.state = 'FAILED' then
        if v_proof.failure_class = 'PUBLIC_PROOF'
           and v_proof.merged_main_sha = p_merged_main_sha
           and v_proof.detail = p_detail then
            return v_proof;
        end if;
        raise exception 'RUNLESS_V2_POST_MERGE_FAILURE_STATE_REJECTED';
    end if;

    if v_proof.state = 'MERGE_AUTHORIZED' then
        if not runless_v2.is_legal_transition('MERGE_AUTHORIZED','MERGED') then
            raise exception 'RUNLESS_V2_ILLEGAL_TRANSITION';
        end if;
        update runless_v2.proof_runs
           set state='MERGED', merged_main_sha=p_merged_main_sha, updated_at=v_now
         where proof_id=p_proof_id
         returning * into v_proof;
    elsif v_proof.merged_main_sha is distinct from p_merged_main_sha then
        raise exception 'RUNLESS_V2_POST_MERGE_FAILURE_MERGE_SHA_MISMATCH';
    end if;

    if v_proof.state not in ('MERGED','POST_MERGE_VERIFY')
       or not runless_v2.is_legal_transition(v_proof.state,'FAILED') then
        raise exception 'RUNLESS_V2_POST_MERGE_FAILURE_STATE_REJECTED';
    end if;

    v_detail_digest := encode(digest(coalesce(p_detail,''),'sha256'),'hex');
    insert into runless_v2.failed_fingerprints(
        request_fingerprint, workstream, proof_id, failure_class, detail_digest
    ) values (
        v_proof.request_fingerprint, v_proof.workstream, p_proof_id,
        'PUBLIC_PROOF', v_detail_digest
    ) on conflict (request_fingerprint) do nothing;

    -- receipt_digest and gate_check_run_id are intentionally preserved.
    update runless_v2.proof_runs
       set state='FAILED', failure_class='PUBLIC_PROOF', detail=p_detail,
           merged_main_sha=p_merged_main_sha, terminal_at=v_now, updated_at=v_now
     where proof_id=p_proof_id
     returning * into v_proof;
    return v_proof;
end;
$$;

revoke all on function runless_v2.record_post_merge_public_failure(text,text,text,text,text,text,bigint,text) from public;
