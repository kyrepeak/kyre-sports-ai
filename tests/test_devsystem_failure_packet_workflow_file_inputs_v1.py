from pathlib import Path


def test_failure_packet_workflow_reads_collected_json_from_files() -> None:
    source = Path(".github/workflows/devsystem-failure-packet-v1.yml").read_text(
        encoding="utf-8"
    )

    # Regression: accumulated failure history can exceed the process argv limit.
    # The workflow must not expand the collected JSON into command-line arguments.
    assert '--needs-json "$(cat /tmp/devsystem-needs.json)"' not in source
    assert '--failed-steps-json "$(cat /tmp/devsystem-failed-steps.json)"' not in source
    assert '--history-json "$(cat /tmp/devsystem-history.json)"' not in source
    assert '--source-created-at "$(cat /tmp/devsystem-source-created-at.txt)"' not in source

    # The workflow should load the already-collected payloads directly from disk.
    assert 'Path("/tmp/devsystem-needs.json")' in source
    assert 'Path("/tmp/devsystem-failed-steps.json")' in source
    assert 'Path("/tmp/devsystem-history.json")' in source
    assert 'Path("/tmp/devsystem-source-created-at.txt")' in source
    assert 'failure_packet_v1.build_packet(' in source
    assert 'failure_packet_v1.write_packet(' in source
