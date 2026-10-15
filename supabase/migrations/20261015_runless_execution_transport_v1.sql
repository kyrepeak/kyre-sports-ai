-- Connected Runless proof transport. This function is transport only;
-- runless_v2.proof_runs and the existing /prove service remain proof authority.

create or replace function runless_v2.request_proof_transport(
    p_repository text,
    p_workstream text,
    p_task_id text,
    p_candidate_sha text,
    p_lease_id text,
    p_authorization_id text,
    p_base_url text,
    p_expected_main_sha text default null
)
returns jsonb
language plpgsql
security definer
set search_path = runless_v2, vault, extensions, public
as $$
declare
    v_token text;
    v_body jsonb;
    v_response extensions.http_response;
    v_payload jsonb;
    v_existing runless_v2.proof_runs%rowtype;
    v_detail text;
begin
    if p_repository <> 'kyrepeak/kyre-sports-ai' then
        raise exception 'RUNLESS_TRANSPORT_REPOSITORY_REJECTED';
    end if;
    if p_candidate_sha !~ '^[0-9a-f]{40}$' then
        raise exception 'RUNLESS_TRANSPORT_CANDIDATE_SHA_INVALID';
    end if;
    if p_expected_main_sha is not null and p_expected_main_sha !~ '^[0-9a-f]{40}$' then
        raise exception 'RUNLESS_TRANSPORT_EXPECTED_MAIN_SHA_INVALID';
    end if;
    if coalesce(p_workstream, '') = '' or coalesce(p_task_id, '') = ''
       or coalesce(p_lease_id, '') = '' or coalesce(p_authorization_id, '') = '' then
        raise exception 'RUNLESS_TRANSPORT_IDENTITY_REQUIRED';
    end if;
    if p_base_url !~ '^https://kyre-runless-proof(?:-[a-z0-9-]+)?[.]vercel[.]app/?$' then
        raise exception 'RUNLESS_TRANSPORT_BASE_URL_REJECTED';
    end if;

    perform pg_advisory_xact_lock(hashtextextended(
        concat_ws(E'\x1f', p_repository, p_workstream, p_task_id, p_candidate_sha,
                  p_lease_id, p_authorization_id, coalesce(p_expected_main_sha, '')),
        0
    ));

    select * into v_existing
      from runless_v2.proof_runs
     where workstream = p_workstream
       and task_id = p_task_id
       and candidate_sha = p_candidate_sha
       and scope_lease_id = p_lease_id
       and authorization_id = p_authorization_id
       and coalesce(expected_main_sha, '') = coalesce(p_expected_main_sha, '')
     order by created_at desc
     limit 1;

    if found then
        return jsonb_build_object(
            'proof_id', v_existing.proof_id,
            'candidate_sha', v_existing.candidate_sha,
            'state', v_existing.state,
            'transport_state', case
                when v_existing.state = 'IDENTIFY' then 'REQUESTED'
                when v_existing.state in ('2A_LOCK','FINGERPRINT') then 'QUEUED'
                when v_existing.state in ('REUSE_OR_PROVE','PUBLIC_CHECK_IF_REQUIRED','RECEIPT','RUNLESS_FINAL_GATE') then 'RUNNING'
                when v_existing.state = 'FAILED' then 'FAILED'
                else 'SUCCEEDED'
            end,
            'fencing_generation', v_existing.fencing_generation,
            'receipt_digest', v_existing.receipt_digest,
            'gate_check_run_id', v_existing.gate_check_run_id,
            'execution_identity', v_existing.proof_id,
            'failure_class', v_existing.failure_class,
            'detail', v_existing.detail,
            'reused', true
        );
    end if;

    select decrypted_secret into v_token
      from vault.decrypted_secrets
     where name = 'runless_v2_transport_bearer'
     order by updated_at desc
     limit 1;
    if coalesce(v_token, '') = '' then
        raise exception 'RUNLESS_TRANSPORT_BEARER_NOT_CONFIGURED';
    end if;

    v_body := jsonb_build_object(
        'task_id', p_task_id,
        'workstream', p_workstream,
        'candidate_sha', p_candidate_sha,
        'lease_id', p_lease_id,
        'authorization_id', p_authorization_id
    );
    if p_expected_main_sha is not null then
        v_body := v_body || jsonb_build_object('expected_main_sha', p_expected_main_sha);
    end if;

    perform extensions.http_set_curlopt('CURLOPT_CONNECTTIMEOUT_MS', '10000');
    perform extensions.http_set_curlopt('CURLOPT_TIMEOUT_MS', '900000');
    begin
        select * into v_response
          from extensions.http((
              'POST'::extensions.http_method,
              rtrim(p_base_url, '/') || '/prove',
              array[
                  row('Authorization', 'Bearer ' || v_token)::extensions.http_header,
                  row('Accept', 'application/json')::extensions.http_header
              ],
              'application/json',
              v_body::text
          )::extensions.http_request);
    exception when others then
        perform extensions.http_reset_curlopt();
        raise exception 'RUNLESS_TRANSPORT_HTTP_UNAVAILABLE';
    end;
    perform extensions.http_reset_curlopt();

    begin
        v_payload := v_response.content::jsonb;
    exception when others then
        raise exception 'RUNLESS_TRANSPORT_BAD_JSON';
    end;

    if v_response.status < 200 or v_response.status >= 300 then
        v_detail := coalesce(v_payload->>'detail', '');
        if v_detail !~ '^RUNLESS_[A-Z0-9_:.-]+$' then
            v_detail := 'RUNLESS_TRANSPORT_HTTP_ERROR';
        end if;
        raise exception 'RUNLESS_TRANSPORT_HTTP_%:%', v_response.status, v_detail;
    end if;

    if coalesce(v_payload->>'proof_id', '') = '' then
        raise exception 'RUNLESS_TRANSPORT_RESPONSE_IDENTITY_REQUIRED';
    end if;

    select * into strict v_existing
      from runless_v2.proof_runs
     where proof_id = v_payload->>'proof_id';

    return jsonb_build_object(
        'proof_id', v_existing.proof_id,
        'candidate_sha', v_existing.candidate_sha,
        'state', v_existing.state,
        'transport_state', case
            when v_existing.state = 'IDENTIFY' then 'REQUESTED'
            when v_existing.state in ('2A_LOCK','FINGERPRINT') then 'QUEUED'
            when v_existing.state in ('REUSE_OR_PROVE','PUBLIC_CHECK_IF_REQUIRED','RECEIPT','RUNLESS_FINAL_GATE') then 'RUNNING'
            when v_existing.state = 'FAILED' then 'FAILED'
            else 'SUCCEEDED'
        end,
        'fencing_generation', v_existing.fencing_generation,
        'receipt_digest', v_existing.receipt_digest,
        'gate_check_run_id', v_existing.gate_check_run_id,
        'execution_identity', v_existing.proof_id,
        'failure_class', v_existing.failure_class,
        'detail', v_existing.detail,
        'reused', false,
        'http_status', v_response.status
    );
end;
$$;

revoke all on function runless_v2.request_proof_transport(text,text,text,text,text,text,text,text)
from public, anon, authenticated;
grant execute on function runless_v2.request_proof_transport(text,text,text,text,text,text,text,text)
to service_role;
