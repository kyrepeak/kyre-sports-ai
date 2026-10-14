-- Runless V2 live security hardening discovered during Task 8 advisor readback.
-- Keep the pure transition helper deterministic and immune to caller-controlled search_path.

alter function runless_v2.is_legal_transition(text, text)
    set search_path = pg_catalog;
