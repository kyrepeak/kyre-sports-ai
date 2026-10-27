-- KYRE GUARDIAN Security + Configuration Hardening V1
-- Production parity record for the Guardian-only hardening applied on 2026-10-27.
-- This migration does not alter sports model logic or API2/MONSTER private state.

-- Remove proven-orphaned API2 temporary registry/construction artifacts.
drop function if exists public.api2_registry_step4_final_freeze_payload_temp();
drop function if exists public.api2_registry_step4_rebind_payload_temp();
drop function if exists public.api2_registry_step4_target_payload_temp();
drop function if exists public._api2_canonical_jsonb_temp(jsonb);
drop function if exists public._api2_json_ascii_string_temp(text);
drop function if exists public._api2_temp_canonical_jsonb(jsonb);
drop function if exists public.api2_pycanon_temp(jsonb);
drop table if exists public._api2_temp_registry_reconciled_step5;
drop table if exists public._api2_temp_step7_registry_target;

-- Preserve Runless transition semantics while fixing mutable search_path.
do $$
begin
  if to_regprocedure('runless_v2.is_legal_transition(text,text)') is not null then
    execute 'alter function runless_v2.is_legal_transition(text,text) set search_path = pg_catalog';
  end if;
end
$$;

-- Relocate pg_net only when it is still installed in public and has no queued work.
-- pg_net 0.20.x is not relocatable in place, so a clean reinstall is required.
do $$
declare
  v_schema text;
  v_queue_count bigint := 0;
begin
  select n.nspname
    into v_schema
    from pg_extension e
    join pg_namespace n on n.oid = e.extnamespace
   where e.extname = 'pg_net';

  if v_schema = 'public' then
    if to_regclass('net.http_request_queue') is not null then
      execute 'select count(*) from net.http_request_queue' into v_queue_count;
    end if;
    if v_queue_count <> 0 then
      raise exception 'GUARDIAN_PG_NET_QUEUE_NOT_EMPTY';
    end if;
    execute 'drop extension pg_net';
    execute 'create extension pg_net with schema extensions';
  end if;
end
$$;

-- Cover foreign keys identified by the Supabase Performance Advisor.
create index if not exists mlb_runtime_checkpoint_heads_checkpoint_id_idx
  on kyre_runtime.mlb_runtime_checkpoint_heads (checkpoint_id);
create index if not exists wnba_runtime_checkpoint_heads_checkpoint_id_idx
  on kyre_runtime.wnba_runtime_checkpoint_heads (checkpoint_id);
create index if not exists wnba_step7g_board_scheduler_runs_publication_id_idx
  on public.wnba_step7g_board_scheduler_runs (publication_id);
create index if not exists wnba_step7g_prop_feed_attempts_snapshot_id_idx
  on public.wnba_step7g_prop_feed_attempts (snapshot_id);
