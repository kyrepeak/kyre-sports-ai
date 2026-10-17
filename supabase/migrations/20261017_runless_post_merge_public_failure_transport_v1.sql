-- Private connected transport. GitHub verification remains inside the durable
-- recovery function; callers cannot bypass it with supplied evidence.

create or replace function runless_v2.request_post_merge_public_failure_transport(
    p_repository text,
    p_workstream text,
    p_task_id text,
    p_proof_id text,
    p_candidate_sha text,
    p_merged_main_sha text,
    p_pr_number bigint,
    p_detail text
)
returns jsonb
language plpgsql
security definer
set search_path = runless_v2, public
as $$
declare
    v_result runless_v2.proof_runs%rowtype;
begin
    v_result := runless_v2.record_post_merge_public_failure(
        p_repository, p_workstream, p_task_id, p_proof_id,
        p_candidate_sha, p_merged_main_sha, p_pr_number, p_detail
    );
    return to_jsonb(v_result);
end;
$$;

revoke all on function runless_v2.request_post_merge_public_failure_transport(text,text,text,text,text,text,bigint,text) from public;
