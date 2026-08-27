from __future__ import annotations

import unittest

from sports_api.database.wnba_current_board_store import _hash
from sports_api.tools import wnba_step7g_one_shot_activation as activation
from sports_api.wnba_step7g_transactional_scheduler_commit import Step7GTransactionalSchedulerCommit


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload


class _Backend:
    def __init__(self):
        self.calls = []

    def _request(self, method, resource, **kwargs):
        self.calls.append((method, resource, kwargs))
        if resource == "rpc/wnba_step7g_commit_publication_and_run":
            body = kwargs["json_body"]
            return _Response({
                "publication_inserted": body["p_publication_row"] is not None,
                "run_inserted": True,
                "publication_id": (
                    body["p_publication_row"]["publication_id"]
                    if body["p_publication_row"] is not None
                    else None
                ),
                "run_id": body["p_run_row"]["run_id"],
            })
        raise AssertionError(resource)


class _Store:
    def __init__(self):
        self.backend = _Backend()
        self.lookups = []

    def _select(self, table, **kwargs):
        self.lookups.append((table, kwargs))
        return []


def _publication():
    content = {
        "date": "2026-08-27",
        "season": 2026,
        "season_type": "Regular Season",
        "published_at_utc": "2026-08-27T16:45:00+00:00",
        "valid_until_utc": "2026-08-27T18:45:00+00:00",
        "serving_state": "playable_pregame",
        "source_reference": {
            "selected_provider_id": "kyre",
            "line_board_fingerprint_sha256": "1" * 64,
        },
        "board": {
            "daily_board_fingerprint_sha256": "2" * 64,
            "probability_board_count": 5,
            "value_board_count": 5,
        },
        "archive_summary": {"stored_or_existing_count": 0},
        "scheduling": {},
    }
    digest = _hash(content)
    return {
        "publication_id": f"wnba-5p-publication-2026-08-27-{digest[:20]}",
        "content_sha256": digest,
        "content": content,
    }


def _run(publication_id):
    return {
        "run_id": "wnba-5p-run-20260827-test",
        "started_at_utc": "2026-08-27T16:44:00+00:00",
        "completed_at_utc": "2026-08-27T16:45:00+00:00",
        "date": "2026-08-27",
        "season": 2026,
        "outcome": "published_new_board",
        "provider_collection_attempted": True,
        "board_rebuild_attempted": True,
        "publication_id": publication_id,
        "selected_provider_id": "kyre",
        "source_feed_fingerprint_sha256": "1" * 64,
        "next_due_at_utc": "2026-08-27T16:50:00+00:00",
    }


class Step7GFailClosedTests(unittest.TestCase):
    def test_base_environment_requires_every_global_switch_off(self):
        base = {
            activation.STORAGE_BACKEND_ENV: "supabase",
            activation.PRODUCTION_RUNTIME_ENV: "false",
            activation.SCHEDULER_ENABLED_ENV: "false",
            activation.DIRECT_SYNC_ENABLED_ENV: "false",
            activation.RECONCILED_SYNC_ENABLED_ENV: "false",
            activation.CANARY_ENABLED_ENV: "false",
            activation.PRODUCTION_REFRESH_ENABLED_ENV: "false",
        }
        activation._require_base_fail_closed(base)
        for name in (
            activation.PRODUCTION_RUNTIME_ENV,
            activation.SCHEDULER_ENABLED_ENV,
            activation.DIRECT_SYNC_ENABLED_ENV,
            activation.RECONCILED_SYNC_ENABLED_ENV,
            activation.CANARY_ENABLED_ENV,
            activation.PRODUCTION_REFRESH_ENABLED_ENV,
        ):
            bad = dict(base)
            bad[name] = "true"
            with self.assertRaises(activation.WNBAStep7GActivationNotReadyError):
                activation._require_base_fail_closed(bad)

    def test_private_cycle_environment_does_not_enable_recurring_scheduler(self):
        private = activation._private_cycle_environment(
            {activation.STORAGE_BACKEND_ENV: "supabase"},
            "/tmp/step7g/wnba_market_feed.json",
        )
        self.assertEqual(private[activation.PRODUCTION_RUNTIME_ENV], "false")
        self.assertEqual(private[activation.SCHEDULER_ENABLED_ENV], "false")
        self.assertEqual(private[activation.AUTO_ARCHIVE_ENABLED_ENV], "false")
        self.assertEqual(private[activation.PRODUCTION_REFRESH_ENABLED_ENV], "false")
        self.assertEqual(private[activation.DIRECT_SYNC_ENABLED_ENV], "true")
        self.assertEqual(private[activation.RECONCILED_SYNC_ENABLED_ENV], "true")
        self.assertEqual(private[activation.CANARY_ENABLED_ENV], "false")
        self.assertEqual(private[activation.MARKET_PROVIDER_MODE_ENV], "kyre")

    def test_transaction_defers_publication_until_matching_run(self):
        store = _Store()
        tx = Step7GTransactionalSchedulerCommit(store)
        publication = _publication()
        persistence = tx.persist_publication(publication)
        self.assertTrue(persistence["stored"])
        self.assertTrue(persistence["atomic_commit_deferred"])
        self.assertEqual(store.backend.calls, [])

        run = _run(publication["publication_id"])
        committed = tx.append_scheduler_run(run)
        self.assertTrue(committed["stored"])
        self.assertTrue(committed["publication_inserted"])
        self.assertTrue(committed["atomic_commit"])
        tx.assert_clean()
        self.assertEqual(len(store.backend.calls), 1)
        method, resource, kwargs = store.backend.calls[0]
        self.assertEqual(method, "POST")
        self.assertEqual(resource, "rpc/wnba_step7g_commit_publication_and_run")
        self.assertEqual(kwargs["json_body"]["p_publication_document"], publication)
        self.assertEqual(kwargs["json_body"]["p_run_document"], run)

    def test_transaction_rejects_run_for_wrong_pending_publication(self):
        store = _Store()
        tx = Step7GTransactionalSchedulerCommit(store)
        publication = _publication()
        tx.persist_publication(publication)
        wrong = _run("wnba-5p-publication-wrong")
        with self.assertRaises(Exception):
            tx.append_scheduler_run(wrong)
        self.assertEqual(store.backend.calls, [])

    def test_frozen_activation_id_cannot_be_changed(self):
        self.assertEqual(activation.ACTIVATION_ID, "step7g-20260827-one-shot-v1")
        self.assertEqual(
            activation.EXPECTED_PRE_CYCLE_FEED_SHA256,
            "7d6363bc12e6ee2351938eb83eb636d89ec25e559fc199b6a904cdeec816b00e",
        )


if __name__ == "__main__":
    unittest.main()
