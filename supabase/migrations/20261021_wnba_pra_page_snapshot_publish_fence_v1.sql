-- Atomic fenced publish for WNBA PRA page model artifacts.

create or replace function runless_v2.publish_wnba_pra_page_snapshot(
    p_snapshot_date date,
    p_season integer,
    p_schema_version text,
    p_model_version text,
    p_content_hash text,
    p_generated_at timestamptz,
    p_artifact jsonb,
    p_owner_id text,
    p_lease_token text
)
returns table(stored boolean, content_hash text)
language plpgsql
security invoker
set search_path = runless_v2, public
as $$
declare
    v_lease runless_v2.wnba_pra_snapshot_refresh_leases%rowtype;
begin
    if p_snapshot_date is null or p_season <> 2026
       or length(btrim(coalesce(p_schema_version, ''))) = 0
       or length(btrim(coalesce(p_model_version, ''))) = 0
       or p_content_hash !~ '^sha256:[0-9a-f]{64}$'
       or p_generated_at is null or p_artifact is null
       or length(btrim(coalesce(p_owner_id, ''))) = 0
       or length(btrim(coalesce(p_lease_token, ''))) = 0 then
        raise exception 'WNBA_PRA_SNAPSHOT_PUBLISH_INPUT_INVALID';
    end if;

    select * into v_lease
      from runless_v2.wnba_pra_snapshot_refresh_leases
     where snapshot_date = p_snapshot_date
       and season = p_season
       and owner_id = btrim(p_owner_id)
       and lease_token = p_lease_token
       and expires_at > clock_timestamp()
     for update;

    if not found then
        raise exception 'WNBA_PRA_SNAPSHOT_PUBLISH_FENCE_INVALID';
    end if;

    insert into runless_v2.wnba_pra_page_snapshots
        (snapshot_date, season, schema_version, model_version, content_hash, generated_at, artifact, updated_at)
    values
        (p_snapshot_date, p_season, btrim(p_schema_version), btrim(p_model_version), p_content_hash,
         p_generated_at, p_artifact, clock_timestamp())
    on conflict (snapshot_date, season, schema_version) do update
       set model_version = excluded.model_version,
           content_hash = excluded.content_hash,
           generated_at = excluded.generated_at,
           artifact = excluded.artifact,
           updated_at = excluded.updated_at;

    delete from runless_v2.wnba_pra_snapshot_refresh_leases
     where snapshot_date = p_snapshot_date
       and season = p_season
       and owner_id = btrim(p_owner_id)
       and lease_token = p_lease_token;

    return query select true, p_content_hash;
end;
$$;

revoke all on function runless_v2.publish_wnba_pra_page_snapshot(date, integer, text, text, text, timestamptz, jsonb, text, text)
    from public, anon, authenticated;
grant execute on function runless_v2.publish_wnba_pra_page_snapshot(date, integer, text, text, text, timestamptz, jsonb, text, text)
    to service_role;
