-- WNBA PRA maximum-speed durable model artifact + cross-process refresh lease.
-- Private runless_v2 schema only. No browser/public role access.

create table if not exists runless_v2.wnba_pra_page_snapshots (
    snapshot_date date not null,
    season integer not null check (season = 2026),
    schema_version text not null,
    model_version text not null,
    content_hash text not null check (content_hash ~ '^sha256:[0-9a-f]{64}$'),
    generated_at timestamptz not null,
    artifact jsonb not null,
    updated_at timestamptz not null default now(),
    primary key (snapshot_date, season, schema_version)
);

create table if not exists runless_v2.wnba_pra_snapshot_refresh_leases (
    snapshot_date date not null,
    season integer not null check (season = 2026),
    owner_id text not null check (length(btrim(owner_id)) > 0),
    lease_token text not null check (length(btrim(lease_token)) > 0),
    acquired_at timestamptz not null,
    expires_at timestamptz not null,
    primary key (snapshot_date, season),
    check (expires_at > acquired_at)
);

create index if not exists wnba_pra_page_snapshots_generated_at_idx
    on runless_v2.wnba_pra_page_snapshots (generated_at desc);
create index if not exists wnba_pra_snapshot_refresh_leases_expires_at_idx
    on runless_v2.wnba_pra_snapshot_refresh_leases (expires_at);

create or replace function runless_v2.claim_wnba_pra_snapshot_refresh(
    p_snapshot_date date,
    p_season integer,
    p_owner_id text,
    p_ttl_seconds integer default 300
)
returns table(acquired boolean, lease_token text, expires_at timestamptz)
language plpgsql
security invoker
set search_path = runless_v2, extensions, public
as $$
declare
    v_now timestamptz := clock_timestamp();
    v_token text := extensions.gen_random_uuid()::text;
    v_expiry timestamptz;
    v_row runless_v2.wnba_pra_snapshot_refresh_leases%rowtype;
begin
    if p_snapshot_date is null or p_season <> 2026 or length(btrim(coalesce(p_owner_id, ''))) = 0 then
        raise exception 'WNBA_PRA_REFRESH_IDENTITY_INVALID';
    end if;
    if p_ttl_seconds < 30 or p_ttl_seconds > 900 then
        raise exception 'WNBA_PRA_REFRESH_TTL_INVALID';
    end if;
    v_expiry := v_now + make_interval(secs => p_ttl_seconds);

    insert into runless_v2.wnba_pra_snapshot_refresh_leases
        (snapshot_date, season, owner_id, lease_token, acquired_at, expires_at)
    values
        (p_snapshot_date, p_season, btrim(p_owner_id), v_token, v_now, v_expiry)
    on conflict (snapshot_date, season) do update
       set owner_id = excluded.owner_id,
           lease_token = excluded.lease_token,
           acquired_at = excluded.acquired_at,
           expires_at = excluded.expires_at
     where runless_v2.wnba_pra_snapshot_refresh_leases.expires_at <= v_now
    returning * into v_row;

    if found then
        return query select true, v_row.lease_token, v_row.expires_at;
        return;
    end if;

    select * into v_row
      from runless_v2.wnba_pra_snapshot_refresh_leases
     where snapshot_date = p_snapshot_date and season = p_season;
    return query select false, null::text, v_row.expires_at;
end;
$$;

create or replace function runless_v2.release_wnba_pra_snapshot_refresh(
    p_snapshot_date date,
    p_season integer,
    p_owner_id text,
    p_lease_token text
)
returns table(released boolean)
language plpgsql
security invoker
set search_path = runless_v2, public
as $$
declare
    v_deleted integer := 0;
begin
    delete from runless_v2.wnba_pra_snapshot_refresh_leases
     where snapshot_date = p_snapshot_date
       and season = p_season
       and owner_id = btrim(p_owner_id)
       and lease_token = p_lease_token;
    get diagnostics v_deleted = row_count;
    return query select v_deleted = 1;
end;
$$;

revoke all on table runless_v2.wnba_pra_page_snapshots from public, anon, authenticated;
revoke all on table runless_v2.wnba_pra_snapshot_refresh_leases from public, anon, authenticated;
revoke all on function runless_v2.claim_wnba_pra_snapshot_refresh(date, integer, text, integer) from public, anon, authenticated;
revoke all on function runless_v2.release_wnba_pra_snapshot_refresh(date, integer, text, text) from public, anon, authenticated;

grant usage on schema runless_v2 to service_role;
grant select, insert, update on table runless_v2.wnba_pra_page_snapshots to service_role;
grant select, insert, update, delete on table runless_v2.wnba_pra_snapshot_refresh_leases to service_role;
grant execute on function runless_v2.claim_wnba_pra_snapshot_refresh(date, integer, text, integer) to service_role;
grant execute on function runless_v2.release_wnba_pra_snapshot_refresh(date, integer, text, text) to service_role;
