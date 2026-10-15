-- Connected frozen-registry thaw transport.
-- This function is transport only; Runless V2 GithubAuthority and the
-- authoritative monster-frozen-artifact-registry ref remain mutation truth.

create or replace function runless_v2.request_registry_thaw_transport(
    p_repository text,
    p_workstream text,
    p_task_id text,
    p_candidate_sha text,
    p_thaw_id text,
    p_path text,
    p_from_blob text,
    p_to_blob text,
    p_expected_main_sha text,
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
    v_detail text;
    v_failure_class text;
begin
    if p_repository <> 'kyrepeak/kyre-sports-ai' then
        raise exception 'RUNLESS_REGISTRY_THAW_TRANSPORT_REPOSITORY_REJECTED';
    end if;
    if p_candidate_sha !~ '^[0-9a-f]{40}$' then
        raise exception 'RUNLESS_REGISTRY_THAW_TRANSPORT_CANDIDATE_SHA_INVALID';
    end if;
    if p_from_blob !~ '^[0-9a-f]{40}$' then
        raise exception 'RUNLESS_REGISTRY_THAW_TRANSPORT_FROM_BLOB_INVALID';
    end if;
    if p_to_blob !~ '^[0-9a-f]{40}$' then
        raise exception 'RUNLESS_REGISTRY_THAW_TRANSPORT_TO_BLOB_INVALID';
    end if;
    if p_expected_main_sha !~ '^[0-9a-f]{40}$' then
        raise exception 'RUNLESS_REGISTRY_THAW_TRANSPORT_EXPECTED_MAIN_SHA_INVALID';
    end if;
    if p_from_blob = p_to_blob then
        raise exception 'RUNLESS_REGISTRY_THAW_TRANSPORT_NOOP_REJECTED';
    end if;
    if coalesce(p_workstream, '') = ''
       or coalesce(p_task_id, '') = ''
       or coalesce(p_thaw_id, '') = ''
       or coalesce(p_path, '') = '' then
        raise exception 'RUNLESS_REGISTRY_THAW_TRANSPORT_IDENTITY_REQUIRED';
    end if;
    if p_base_url !~ '^https://kyre-runless-proof(?:-[a-z0-9-]+)?[.]vercel[.]app/?$' then
        raise exception 'RUNLESS_REGISTRY_THAW_TRANSPORT_BASE_URL_REJECTED';
    end if;

    -- Serialize the exact thaw identity. A concurrent identical request waits,
    -- then the Runless endpoint reads the durable registry and returns REUSED.
    perform pg_advisory_xact_lock(hashtextextended(
        concat_ws(E'\x1f',
            p_repository,
            p_workstream,
            p_task_id,
            p_candidate_sha,
            p_thaw_id,
            p_path,
            p_from_blob,
            p_to_blob,
            p_expected_main_sha
        ),
        0
    ));

    select decrypted_secret into v_token
      from vault.decrypted_secrets
     where name = 'runless_v2_transport_bearer'
     order by updated_at desc
     limit 1;
    if coalesce(v_token, '') = '' then
        raise exception 'RUNLESS_REGISTRY_THAW_TRANSPORT_BEARER_NOT_CONFIGURED';
    end if;

    select decrypted_secret into v_vercel_bypass
      from vault.decrypted_secrets
     where name = 'runless_v2_vercel_protection_bypass'
     order by updated_at desc
     limit 1;
    if coalesce(v_vercel_bypass, '') = '' then
        raise exception 'RUNLESS_REGISTRY_THAW_TRANSPORT_VERCEL_BYPASS_NOT_CONFIGURED';
    end if;

    v_body := jsonb_build_object(
        'repository', p_repository,
        'workstream', p_workstream,
        'task_id', p_task_id,
        'candidate_sha', p_candidate_sha,
        'thaw_id', p_thaw_id,
        'path', p_path,
        'from_blob', p_from_blob,
        'to_blob', p_to_blob,
        'expected_main_sha', p_expected_main_sha
    );

    perform extensions.http_set_curlopt('CURLOPT_CONNECTTIMEOUT_MS', '10000');
    perform extensions.http_set_curlopt('CURLOPT_TIMEOUT_MS', '120000');
    begin
        select * into v_response
          from extensions.http((
              'POST'::extensions.http_method,
              rtrim(p_base_url, '/') || '/registry-thaw',
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
        raise exception 'RUNLESS_REGISTRY_THAW_TRANSPORT_HTTP_UNAVAILABLE';
    end;
    perform extensions.http_reset_curlopt();

    begin
        v_payload := v_response.content::jsonb;
    exception when others then
        raise exception 'RUNLESS_REGISTRY_THAW_TRANSPORT_BAD_JSON';
    end;

    if v_response.status < 200 or v_response.status >= 300 then
        v_detail := coalesce(v_payload->>'detail', 'RUNLESS_REGISTRY_THAW_TRANSPORT_HTTP_ERROR');
        if v_detail !~ '^(REGISTRY_THAW_[A-Z0-9_:.-]+|STALE_REGISTRY_CAS|RUNLESS_V2_[A-Z0-9_:.-]+)$' then
            v_detail := 'RUNLESS_REGISTRY_THAW_TRANSPORT_HTTP_ERROR';
        end if;
        v_failure_class := case
            when v_detail in (
                'REGISTRY_THAW_REPOSITORY_MISMATCH',
                'REGISTRY_THAW_CANDIDATE_IDENTITY_MISMATCH',
                'REGISTRY_THAW_MAIN_IDENTITY_DRIFT'
            ) then 'IDENTITY'
            when v_detail = 'STALE_REGISTRY_CAS' or v_detail like 'REGISTRY_THAW_%' then 'REGISTRY'
            else 'INFRA'
        end;
        return jsonb_build_object(
            'thaw_id', p_thaw_id,
            'target_head_sha', p_candidate_sha,
            'path', p_path,
            'from_blob', p_from_blob,
            'to_blob', p_to_blob,
            'previous_registry_revision', null,
            'current_registry_revision', null,
            'previous_state_hash', null,
            'current_state_hash', null,
            'registry_commit_sha', null,
            'state', 'FAILED',
            'reused', false,
            'failure_class', v_failure_class,
            'detail', v_detail
        );
    end if;

    if coalesce(v_payload->>'thaw_id', '') <> p_thaw_id
       or coalesce(v_payload->>'target_head_sha', '') <> p_candidate_sha
       or coalesce(v_payload->>'path', '') <> p_path
       or coalesce(v_payload->>'from_blob', '') <> p_from_blob
       or coalesce(v_payload->>'to_blob', '') <> p_to_blob then
        raise exception 'RUNLESS_REGISTRY_THAW_TRANSPORT_RESPONSE_IDENTITY_MISMATCH';
    end if;

    return jsonb_build_object(
        'thaw_id', v_payload->>'thaw_id',
        'target_head_sha', v_payload->>'target_head_sha',
        'path', v_payload->>'path',
        'from_blob', v_payload->>'from_blob',
        'to_blob', v_payload->>'to_blob',
        'previous_registry_revision', v_payload->'previous_registry_revision',
        'current_registry_revision', v_payload->'current_registry_revision',
        'previous_state_hash', v_payload->>'previous_state_hash',
        'current_state_hash', v_payload->>'current_state_hash',
        'registry_commit_sha', v_payload->>'registry_commit_sha',
        'state', v_payload->>'state',
        'reused', coalesce((v_payload->>'reused')::boolean, false),
        'failure_class', coalesce(v_payload->>'failure_class', 'INFRA'),
        'detail', coalesce(v_payload->>'detail', '')
    );
end;
$$;

revoke all on function runless_v2.request_registry_thaw_transport(text,text,text,text,text,text,text,text,text,text)
from public, anon, authenticated;
grant execute on function runless_v2.request_registry_thaw_transport(text,text,text,text,text,text,text,text,text,text)
to service_role;
