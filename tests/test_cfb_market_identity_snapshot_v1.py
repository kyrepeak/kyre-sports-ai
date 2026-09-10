from datetime import datetime, timezone
import json
from pathlib import Path
import textwrap

import pytest

from scripts import build_cfb_market_identity_snapshot_v1 as snapshot


def _event(event_id, date, away_id, away, home_id, home):
    return {
        "id": str(event_id),
        "date": date,
        "competitions": [
            {
                "competitors": [
                    {
                        "homeAway": "away",
                        "team": {"id": str(away_id), "displayName": away},
                    },
                    {
                        "homeAway": "home",
                        "team": {"id": str(home_id), "displayName": home},
                    },
                ],
                "venue": {"fullName": "Test Stadium"},
                "broadcasts": [{"names": ["Test Network"]}],
            }
        ],
        "status": {"type": {"description": "Scheduled"}},
    }


def _fetcher(url, params, headers):
    if "fanduel" in url:
        return {
            "attachments": {
                "events": {
                    "a": {
                        "name": "Baylor Bears @ Kansas Jayhawks",
                        "openDate": "2026-09-18T23:00:00Z",
                    },
                    "b": {
                        "name": "Duke Blue Devils @ Syracuse Orange",
                        "openDate": "2026-09-19T00:00:00Z",
                    },
                    "c": {
                        "name": "Oklahoma State Cowboys @ Tulsa Golden Hurricane",
                        "openDate": "2026-09-19T16:00:00Z",
                    },
                    "old": {
                        "name": "Old Team @ Past Team",
                        "openDate": "2026-09-01T16:00:00Z",
                    },
                }
            }
        }

    day = str(params["dates"])
    group = int(params["groups"])
    if day == "20260918":
        events = [
            _event(
                401900001,
                "2026-09-18T23:00:00Z",
                239,
                "Baylor Bears",
                2305,
                "Kansas Jayhawks",
            ),
            _event(
                401900002,
                "2026-09-19T00:00:00Z",
                150,
                "Duke Blue Devils",
                183,
                "Syracuse Orange",
            ),
        ]
    elif day == "20260919":
        events = [
            _event(
                401900003,
                "2026-09-19T16:00:00Z",
                197,
                "Oklahoma State Cowboys",
                202,
                "Tulsa Golden Hurricane",
            ),
            _event(
                401900004,
                "2026-09-19T19:00:00Z",
                356,
                "Illinois Fighting Illini",
                77,
                "Northwestern Wildcats",
            ),
            _event(
                401900005,
                "2026-09-19T23:00:00Z",
                2509,
                "Purdue Boilermakers",
                84,
                "Indiana Hoosiers",
            ),
        ]
    else:
        events = []

    # Return the same rows from FBS/FCS to prove official-ID dedupe is safe.
    assert group in {80, 81}
    return {"events": events}


def test_snapshot_tracks_live_market_dates_and_uses_only_official_espn_ids():
    payload = snapshot.build_snapshot(
        now_utc=datetime(2026, 9, 10, 20, 0, tzinfo=timezone.utc),
        fetch_json=_fetcher,
    )

    assert payload["market_dates"] == ["2026-09-18", "2026-09-19"]
    assert payload["window"] == {"start": "2026-09-18", "end": "2026-09-19"}
    assert payload["identity_policy"] == {
        "authority": "ESPN",
        "official_event_ids_only": True,
        "synthetic_ids": False,
        "fuzzy_matching": False,
        "sportsbook_projection_weight": 0.0,
    }

    games = payload["games"]
    ids = [row["event_id"] for row in games]
    assert ids == [
        "401900001",
        "401900002",
        "401900003",
        "401900004",
        "401900005",
    ]
    assert len(ids) == len(set(ids))
    assert all(event_id.isdigit() for event_id in ids)
    assert all(row["away_team_id"] and row["home_team_id"] for row in games)
    assert all(row["source_divisions"] == ["FBS", "FCS"] for row in games)


def test_write_snapshot_ignores_timestamp_only_changes(tmp_path):
    path = tmp_path / "identity.json"
    payload = snapshot.build_snapshot(
        now_utc=datetime(2026, 9, 10, 20, 0, tzinfo=timezone.utc),
        fetch_json=_fetcher,
    )
    assert snapshot.write_snapshot(payload, path) is True

    later = dict(payload)
    later["generated_at"] = "2026-09-10T21:00:00Z"
    later["provider_future_matchups"] = 999
    assert snapshot.write_snapshot(later, path) is False


def _run_publish_validation(tmp_path, monkeypatch, weight, *, missing=False):
    """Execute the real refresh validator without running its Git publish commands."""
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github/workflows/cfb-market-identity-snapshot-v1.yml"
    ).read_text(encoding="utf-8")
    publish_step = workflow.split(
        "- name: Validate and publish identity runtime branch", 1
    )[1]
    validator = textwrap.dedent(
        publish_step.split("python - <<'PY'\n", 1)[1].split("\n          PY", 1)[0]
    )
    payload = snapshot.build_snapshot(
        now_utc=datetime(2026, 9, 10, 20, 0, tzinfo=timezone.utc),
        fetch_json=_fetcher,
    )
    if missing:
        payload["identity_policy"].pop("sportsbook_projection_weight")
    else:
        payload["identity_policy"]["sportsbook_projection_weight"] = weight
    path = tmp_path / "data/cfb_market_identity_snapshot_v1.json"
    path.parent.mkdir()
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    exec(compile(validator, "cfb-market-identity-snapshot-v1.yml:refresh", "exec"), {})


@pytest.mark.parametrize("weight", [0, 0.0])
def test_publish_validator_accepts_required_zero_weight(tmp_path, monkeypatch, weight):
    _run_publish_validation(tmp_path, monkeypatch, weight)


@pytest.mark.parametrize("weight", [0.01, -1, None, "invalid", "NaN", "Infinity"])
def test_publish_validator_fails_closed_for_invalid_weight(tmp_path, monkeypatch, weight):
    with pytest.raises((SystemExit, TypeError, ValueError)):
        _run_publish_validation(tmp_path, monkeypatch, weight)


def test_publish_validator_fails_closed_for_missing_weight(tmp_path, monkeypatch):
    with pytest.raises(SystemExit, match="sportsbook projection weight drift"):
        _run_publish_validation(tmp_path, monkeypatch, None, missing=True)
