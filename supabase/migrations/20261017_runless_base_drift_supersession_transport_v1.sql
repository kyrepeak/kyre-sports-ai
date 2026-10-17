-- Connected base-drift supersession transport. Transport only: durable
-- runless_v2.authority_supersessions remains the authoritative read-back.

create or replace function runless_v2.request_base_drift_supersession_transport(
    p_repository text,
    p_workstream text,
    p_task_id text,
    p_old_proof_id text,
    p_old_candidate_sha text,
    p_successor_candidate_sha text,
    p_successor_expected_main_sha text,
    p_pr_number bigint,
    p_branch text,
    p_base_url text
)
returns jsonb
language plpgsql
security definer
set search_path = runless_v2, vault, extensions, public
as $$
declare
    v_token text;
    v_vercel_bypass text;
    v_body jsonb;
    v_response extensions.http_response;
    v_payload jsonb;
    v_existing runless_v2.authority_supersessions%rowtype;
    v_detail text;
begin
    if p_repository <> 'kyrepeak/kyre-sports-ai' then
        raise exception 'RUNLESS_SUPERSESSION_TRANSPORT_REPOSITORY_REJECTED';
    end if;
    if p_old_candidate_sha !~ '^[0-9a-f]{40}$' then
        raise exception 'RUNLESS_SUPERSESSION_TRANSPORT_OLD_SHA_INVALID';
    end if;
    if p_successor_candidate_sha !~ '^[0-9a-f]{40}$' then
        raise exception 'RUNLESS_SUPERSESSION_TRANSPORT_SUCCESSOR_SHA_INVALID';
    end if;
    if p_successor_expected_main_sha !~ '^[0-9a-f]{40}$' then
        raise exception 'RUNLESS_SUPERSESSION_TRANSPORT_EXPECTED_MAIN_SHA_INVALID';
    end if;
    if coalesce(p_workstream, '') = '' or coalesce(p_task_id, '') = ''
       or coalesce(p_old_proof_id, '') = '' or coalesce(p_branch, '') = '' then
        raise exception 'RUNLESS_SUPERSESSION_TRANSPORT_IDENTITY_REQUIRED';
    end if;
    if p_pr_number is null or p_pr_number <= 0 then
        raise exception 'RUNLESS_SUPERSESSION_TRANSPORT_PR_INVALID';
    end if;
    if p_base_url !~ '^https://kyre-runless-proof(?:-[a-z0-9-]+)?[.]vercel[.]app/?$' then
        raise exception 'RUNLESS_SUPERSESSION_TRANSPORT_BASE_URL_REJECTED';
    end if;

    perform pg_advisory_xact_lock(hashtextextended(
        concat_ws(E'\x1f', p_repository, p_workstream, p_task_id, p_old_proof_id,
                  p_old_candidate_sha, p_successor_candidate_sha,
                  p_successor_expected_main_sha, p_pr_number::text, p_branch),
        0
    ));

    select * into v_existing
      from runless_v2.authority_supersessions
     where old_proof_id = p_old_proof_id;

    if found then
        if v_existing.workstream <> p_workstream
           or v_existing.old_candidate_sha <> p_old_candidate_sha
           or v_existing.successor_candidate_sha <> p_successor_candidate_sha
           or v_existing.successor_expected_main_sha <> p_successor_expected_main_sha
           or coalesce(v_existing.github_pr_number, -1) <> p_pr_number
           or v_existing.github_branch <> p_branch then
            raise exception 'RUNLESS_SUPERSESSION_TRANSPORT_IDENTITY_COLLISION';
        end if;
        return jsonb_build_object(
            'supersession_id', v_existing.supersession_id,
            'workstream', v_existing.workstream,
            'old_proof_id', v_existing.old_proof_id,
            'old_candidate_sha', v_existing.old_candidate_sha,
            'old_expected_main_sha', v_existing.old_expected_main_sha,
            'successor_candidate_sha', v_existing.successor_candidate_sha,
            'successor_expected_main_sha', v_existing.successor_expected_main_sha,
            'reason', v_existing.reason,
            'github_pr_number', v_existing.github_pr_number,
            'github_branch', v_existing.github_branch,
            'old_gate_check_run_id', v_existing.old_gate_check_run_id,
            'old_receipt_digest', v_existing.old_receipt_digest,
            'created_at', v_existing.created_at,
            'transport_state', 'SUCCEEDED',
            'reused', true
        );
    end if;

    select decrypted_secret into v_token
      from vault.decrypted_secrets
     where name = 'runless_v2_transport_bearer'
     order by updated_at desc
     limit 1;
    if coalesce(v_token, '') = '' then
        raise exception 'RUNLESS_SUPERSESSION_TRANSPORT_BEARER_NOT_CONFIGURED';
    end if;

    select decrypted_secret into v_vercel_bypass
      from vault.decrypted_secrets
     where name = 'runless_v2_vercel_protection_bypass'
     order by updated_at desc
     limit 1;
    if coalesce(v_vercel_bypass, '') = '' then
        raise exception 'RUNLESS_SUPERSESSION_TRANSPORT_VERCEL_BYPASS_NOT_CONFIGURED';
    end if;

    v_body := jsonb_build_object(
        'repository', p_repository,
        'workstream', p_workstream,
        'task_id', p_task_id,
        'old_proof_id', p_old_proof_id,
        'old_candidate_sha', p_old_candidate_sha,
        'successor_candidate_sha', p_successor_candidate_sha,
        'successor_expected_main_sha', p_successor_expected_main_sha,
        'pr_number', p_pr_number,
        'branch', p_branch
    );

    perform extensions.http_set_curlopt('CURLOPT_CONNECTTIMEOUT_MS', '10000');
    perform extensions.http_set_curlopt('CURLOPT_TIMEOUT_MS', '120000');
    begin
        select * into v_response
          from extensions.http((
              'POST'::extensions.http_method,
              rtrim(p_base_url, '/') || '/supersede-base-drift',
              array[
                  row('Authorization', 'Bearer ' || v_token)::extensions.http_header,
                  row('x-vercel-protection-bypass', v_vercel_bypass)::extensions.http_header,
                  row('Accept', 'application/json')::extensions.http_header
              ],
              'application/json',
              v_body::text
          )::extensions.http_request);
    exception when others then
        perform extensions.http_reset_curlopt();
        raise exception 'RUNLESS_SUPERSESSION_TRANSPORT_HTTP_UNAVAILABLE';
    end;
    perform extensions.http_reset_curlopt();

    begin
        v_payload := v_response.content::jsonb;
    exception when others then
        raise exception 'RUNLESS_SUPERSESSION_TRANSPORT_BAD_JSON';
    end;

    if v_response.status < 200 or v_response.status >= 300 then
        v_detail := coalesce(v_payload->>'detail', '');
        if v_detail !~ '^RUNLESS_[A-Z0-9_:.-]+$' then
            v_detail := 'RUNLESS_SUPERSESSION_TRANSPORT_HTTP_ERROR';
        end if;
        raise exception 'RUNLESS_SUPERSESSION_TRANSPORT_HTTP_%:%', v_response.status, v_detail;
    end if;

    if coalesce(v_payload->>'supersession_id', '') = '' then
        raise exception 'RUNLESS_SUPERSESSION_TRANSPORT_RESPONSE_IDENTITY_REQUIRED';
    end if;

    select * into strict v_existing
      from runless_v2.authority_supersessions
     where old_proof_id = p_old_proof_id;

    if v_existing.supersession_id <> v_payload->>'supersession_id'
       or v_existing.workstream <> p_workstream
       or v_existing.old_candidate_sha <> p_old_candidate_sha
       or v_existing.successor_candidate_sha <> p_successor_candidate_sha
       or v_existing.successor_expected_main_sha <> p_successor_expected_main_sha
       or coalesce(v_existing.github_pr_number, -1) <> p_pr_number
       or v_existing.github_branch <> p_branch
       or v_existing.reason <> 'BASE_DRIFT' then
        raise exception 'RUNLESS_SUPERSESSION_TRANSPORT_DURABLE_READBACK_MISMATCH';
    end if;

    return jsonb_build_object(
        'supersession_id', v_existing.supersession_id,
        'workstream', v_existing.workstream,
        'old_proof_id', v_existing.old_proof_id,
        'old_candidate_sha', v_existing.old_candidate_sha,
        'old_expected_main_sha', v_existing.old_expected_main_sha,
        'successor_candidate_sha', v_existing.successor_candidate_sha,
        'successor_expected_main_sha', v_existing.successor_expected_main_sha,
        'reason', v_existing.reason,
        'github_pr_number', v_existing.github_pr_number,
        'github_branch', v_existing.github_branch,
        'old_gate_check_run_id', v_existing.old_gate_check_run_id,
        'old_receipt_digest', v_existing.old_receipt_digest,
        'created_at', v_existing.created_at,
        'transport_state', 'SUCCEEDED',
        'reused', false,
        'http_status', v_response.status
    );
end;
$$;

revoke all on function runless_v2.request_base_drift_supersession_transport(text,text,text,text,text,text,text,bigint,text,text)
from public, anon, authenticated;
grant execute on function runless_v2.request_base_drift_supersession_transport(text,text,text,text,text,text,text,bigint,text,text)
to service_role;
