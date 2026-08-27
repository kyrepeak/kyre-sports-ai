-- Step 6R: Supabase durable-storage schema for the Kyre-owned WNBA market path.
-- Run this explicitly in the target Supabase project before selecting the
-- `supabase` backend. This file performs no sportsbook/provider work.

begin;

create table if not exists public.wnba_durable_objects (
    object_key text primary key,
    payload_base64 text not null,
    size_bytes integer not null,
    content_sha256 text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint wnba_durable_objects_key_safe_chk
        check (
            object_key ~ '^[A-Za-z0-9._-]{1,240}$'
            and object_key not in ('.', '..')
        ),
    constraint wnba_durable_objects_size_chk
        check (size_bytes between 0 and 5000000),
    constraint wnba_durable_objects_sha256_chk
        check (content_sha256 ~ '^[0-9a-f]{64}$')
);

create table if not exists public.wnba_durable_locks (
    lock_key text primary key,
    owner_token uuid not null,
    acquired_at timestamptz not null default now(),
    expires_at timestamptz not null,
    constraint wnba_durable_locks_key_safe_chk
        check (
            lock_key ~ '^[A-Za-z0-9._-]{1,240}$'
            and lock_key not in ('.', '..')
        ),
    constraint wnba_durable_locks_expiry_chk
        check (expires_at > acquired_at)
);

alter table public.wnba_durable_objects enable row level security;
alter table public.wnba_durable_locks enable row level security;

-- These are server-owned tables. No browser/user role receives direct access.
revoke all on table public.wnba_durable_objects from public, anon, authenticated;
revoke all on table public.wnba_durable_locks from public, anon, authenticated;
grant select, insert, update, delete on table public.wnba_durable_objects to service_role;
grant select, insert, update, delete on table public.wnba_durable_locks to service_role;

create or replace function public.wnba_durable_lock_acquire(
    p_lock_key text,
    p_owner_token uuid,
    p_lease_seconds integer
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
    acquired boolean := false;
begin
    if p_lock_key is null
       or p_lock_key !~ '^[A-Za-z0-9._-]{1,240}$'
       or p_lock_key in ('.', '..') then
        raise exception 'invalid durable lock key';
    end if;
    if p_owner_token is null then
        raise exception 'owner token is required';
    end if;
    if p_lease_seconds < 30 or p_lease_seconds > 900 then
        raise exception 'lease seconds must be between 30 and 900';
    end if;

    insert into public.wnba_durable_locks (
        lock_key,
        owner_token,
        acquired_at,
        expires_at
    )
    values (
        p_lock_key,
        p_owner_token,
        now(),
        now() + make_interval(secs => p_lease_seconds)
    )
    on conflict (lock_key) do update
    set owner_token = excluded.owner_token,
        acquired_at = excluded.acquired_at,
        expires_at = excluded.expires_at
    where public.wnba_durable_locks.expires_at <= now()
       or public.wnba_durable_locks.owner_token = excluded.owner_token
    returning true into acquired;

    return coalesce(acquired, false);
end;
$$;

create or replace function public.wnba_durable_lock_release(
    p_lock_key text,
    p_owner_token uuid
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
    released boolean := false;
begin
    if p_lock_key is null
       or p_lock_key !~ '^[A-Za-z0-9._-]{1,240}$'
       or p_lock_key in ('.', '..') then
        raise exception 'invalid durable lock key';
    end if;
    if p_owner_token is null then
        raise exception 'owner token is required';
    end if;

    delete from public.wnba_durable_locks
    where lock_key = p_lock_key
      and owner_token = p_owner_token;

    released := found;
    return released;
end;
$$;

revoke all on function public.wnba_durable_lock_acquire(text, uuid, integer)
    from public, anon, authenticated;
revoke all on function public.wnba_durable_lock_release(text, uuid)
    from public, anon, authenticated;
grant execute on function public.wnba_durable_lock_acquire(text, uuid, integer)
    to service_role;
grant execute on function public.wnba_durable_lock_release(text, uuid)
    to service_role;

commit;
