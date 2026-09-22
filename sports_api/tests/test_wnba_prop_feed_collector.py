import copy
import json
from pathlib import Path
import unittest

import httpx
from fastapi import HTTPException

import sports_api.api.wnba_prop_feed_collector as api
import sports_api.collectors.wnba_prop_feed_collector as m


def provider(**overrides):
    row = {
        "provider_id": "demo",
        "enabled": True,
        "url": "https://feed.example.com/wnba/{date}?season={season}",
        "feed_source": "Demo Feed",
        "feed_format": "canonical_offers_v1",
        "odds_format": "american",
    }
    row.update(overrides)
    return row


def env_for(*providers, default=None, secrets=None, object_form=True):
    if not providers:
        providers = (provider(),)
    if object_form:
        doc = {"providers": list(providers)}
        if default is not None:
            doc["default_provider_id"] = default
        result = {m.PROVIDERS_ENV: json.dumps(doc)}
    else:
        result = {m.PROVIDERS_ENV: json.dumps(list(providers))}
    if secrets:
        result.update(secrets)
    return result


class FakeResponse:
    def __init__(self, payload=None, *, status_code=200, content=None, json_error=None, headers=None):
        self.status_code = status_code
        self._payload = {} if payload is None else payload
        self._json_error = json_error
        self.headers = headers or {"content-type": "application/json"}
        if content is None:
            try:
                content = json.dumps(self._payload).encode("utf-8")
            except Exception:
                content = b""
        self.content = content

    def json(self):
        if self._json_error is not None:
            raise self._json_error
        return copy.deepcopy(self._payload)


class Recorder:
    def __init__(self, response=None, error=None):
        self.response = response or FakeResponse({"offers": []})
        self.error = error
        self.calls = []

    def __call__(self, url, **kwargs):
        self.calls.append((url, copy.deepcopy(kwargs)))
        if self.error is not None:
            raise self.error
        return self.response


class Step5NTests(unittest.TestCase):
    def test_01_empty_registry_is_valid_description(self):
        result = m.describe_provider_registry({})
        self.assertEqual(result["configured_provider_count"], 0)
        self.assertEqual(result["ready_provider_count"], 0)

    def test_02_registry_accepts_list_form(self):
        reg = m.load_provider_registry(env_for(provider(), object_form=False))
        self.assertEqual(reg["providers"][0]["provider_id"], "demo")

    def test_03_registry_accepts_object_form(self):
        reg = m.load_provider_registry(env_for(provider(), default="demo"))
        self.assertEqual(reg["default_provider_id"], "demo")

    def test_04_default_env_overrides_document_default(self):
        e = env_for(provider(), provider(provider_id="backup"), default="backup")
        e[m.DEFAULT_PROVIDER_ENV] = "demo"
        self.assertEqual(m.load_provider_registry(e)["default_provider_id"], "demo")

    def test_05_duplicate_provider_ids_rejected(self):
        with self.assertRaises(m.WNBAPropFeedCollectorConfigError):
            m.load_provider_registry(env_for(provider(), provider()))

    def test_06_provider_count_limit(self):
        rows = [provider(provider_id=f"p{i}") for i in range(m.MAX_PROVIDER_COUNT + 1)]
        with self.assertRaises(m.WNBAPropFeedCollectorConfigError):
            m.load_provider_registry({m.PROVIDERS_ENV: json.dumps(rows)})

    def test_07_invalid_registry_json(self):
        with self.assertRaises(m.WNBAPropFeedCollectorConfigError):
            m.load_provider_registry({m.PROVIDERS_ENV: "{"})

    def test_08_object_providers_must_be_list(self):
        with self.assertRaises(m.WNBAPropFeedCollectorConfigError):
            m.load_provider_registry({m.PROVIDERS_ENV: json.dumps({"providers": {}})})

    def test_09_provider_row_must_be_object(self):
        with self.assertRaises(m.WNBAPropFeedCollectorConfigError):
            m.load_provider_registry({m.PROVIDERS_ENV: json.dumps(["bad"])})

    def test_10_invalid_provider_id_rejected(self):
        with self.assertRaises(m.WNBAPropFeedCollectorConfigError):
            m.load_provider_registry(env_for(provider(provider_id="bad id")))

    def test_11_provider_id_normalized_casefold(self):
        reg = m.load_provider_registry(env_for(provider(provider_id="DEMO")))
        self.assertEqual(reg["providers"][0]["provider_id"], "demo")

    def test_12_enabled_must_be_boolean(self):
        with self.assertRaises(m.WNBAPropFeedCollectorConfigError):
            m.load_provider_registry(env_for(provider(enabled="yes")))

    def test_13_http_url_rejected(self):
        with self.assertRaises(m.WNBAPropFeedCollectorConfigError):
            m.load_provider_registry(env_for(provider(url="http://feed.example.com/x")))

    def test_14_url_requires_hostname(self):
        with self.assertRaises(m.WNBAPropFeedCollectorConfigError):
            m.load_provider_registry(env_for(provider(url="https:///x")))

    def test_15_embedded_url_credentials_rejected(self):
        with self.assertRaises(m.WNBAPropFeedCollectorConfigError):
            m.load_provider_registry(env_for(provider(url="https://user:pass@feed.example.com/x")))

    def test_16_url_fragment_rejected(self):
        with self.assertRaises(m.WNBAPropFeedCollectorConfigError):
            m.load_provider_registry(env_for(provider(url="https://feed.example.com/x#secret")))

    def test_17_localhost_rejected(self):
        with self.assertRaises(m.WNBAPropFeedCollectorConfigError):
            m.load_provider_registry(env_for(provider(url="https://localhost/x")))

    def test_18_dot_local_rejected(self):
        with self.assertRaises(m.WNBAPropFeedCollectorConfigError):
            m.load_provider_registry(env_for(provider(url="https://feed.local/x")))

    def test_19_dot_internal_rejected(self):
        with self.assertRaises(m.WNBAPropFeedCollectorConfigError):
            m.load_provider_registry(env_for(provider(url="https://feed.internal/x")))

    def test_20_private_ipv4_rejected(self):
        with self.assertRaises(m.WNBAPropFeedCollectorConfigError):
            m.load_provider_registry(env_for(provider(url="https://10.0.0.1/x")))

    def test_21_loopback_ipv4_rejected(self):
        with self.assertRaises(m.WNBAPropFeedCollectorConfigError):
            m.load_provider_registry(env_for(provider(url="https://127.0.0.1/x")))

    def test_22_link_local_ipv4_rejected(self):
        with self.assertRaises(m.WNBAPropFeedCollectorConfigError):
            m.load_provider_registry(env_for(provider(url="https://169.254.169.254/x")))

    def test_23_private_ipv6_rejected(self):
        with self.assertRaises(m.WNBAPropFeedCollectorConfigError):
            m.load_provider_registry(env_for(provider(url="https://[::1]/x")))

    def test_24_hostname_template_rejected(self):
        with self.assertRaises(m.WNBAPropFeedCollectorConfigError):
            m.load_provider_registry(env_for(provider(url="https://{date}.example.com/x")))

    def test_25_sensitive_url_query_key_rejected(self):
        with self.assertRaises(m.WNBAPropFeedCollectorConfigError):
            m.load_provider_registry(env_for(provider(url="https://feed.example.com/x?api_key=literal")))

    def test_26_nonsecret_url_query_allowed(self):
        reg = m.load_provider_registry(env_for(provider(url="https://feed.example.com/x?league=wnba")))
        self.assertEqual(reg["providers"][0]["provider_id"], "demo")

    def test_27_unsupported_template_rejected(self):
        with self.assertRaises(m.WNBAPropFeedCollectorConfigError):
            m.load_provider_registry(env_for(provider(url="https://feed.example.com/{team}")))

    def test_28_literal_authorization_header_rejected(self):
        with self.assertRaises(m.WNBAPropFeedCollectorConfigError):
            m.load_provider_registry(env_for(provider(headers={"Authorization": "Bearer literal"})))

    def test_29_literal_api_key_header_rejected(self):
        with self.assertRaises(m.WNBAPropFeedCollectorConfigError):
            m.load_provider_registry(env_for(provider(headers={"X-API-Key": "literal"})))

    def test_30_header_newline_rejected(self):
        with self.assertRaises(m.WNBAPropFeedCollectorConfigError):
            m.load_provider_registry(env_for(provider(headers={"X-Test": "a\nb"})))

    def test_31_invalid_header_name_rejected(self):
        with self.assertRaises(m.WNBAPropFeedCollectorConfigError):
            m.load_provider_registry(env_for(provider(headers={"Bad Header": "x"})))

    def test_32_sensitive_static_query_rejected(self):
        with self.assertRaises(m.WNBAPropFeedCollectorConfigError):
            m.load_provider_registry(env_for(provider(query_params={"token": "literal"})))

    def test_33_empty_static_query_value_rejected(self):
        with self.assertRaises(m.WNBAPropFeedCollectorConfigError):
            m.load_provider_registry(env_for(provider(query_params={"league": ""})))

    def test_34_invalid_secret_env_name_rejected(self):
        with self.assertRaises(m.WNBAPropFeedCollectorConfigError):
            m.load_provider_registry(env_for(provider(secret_header_env={"Authorization": "bad-name"})))

    def test_35_secret_header_binding_is_valid(self):
        reg = m.load_provider_registry(env_for(provider(secret_header_env={"Authorization": "FEED_TOKEN"})))
        self.assertEqual(reg["providers"][0]["secret_header_env"]["Authorization"], "FEED_TOKEN")

    def test_36_static_secret_header_overlap_rejected(self):
        with self.assertRaises(m.WNBAPropFeedCollectorConfigError):
            m.load_provider_registry(env_for(provider(headers={"X-Test": "x"}, secret_header_env={"x-test": "TOKEN"})))

    def test_37_static_secret_query_overlap_rejected(self):
        with self.assertRaises(m.WNBAPropFeedCollectorConfigError):
            m.load_provider_registry(env_for(provider(query_params={"league": "wnba"}, secret_query_env={"league": "TOKEN"})))

    def test_38_response_path_must_be_list(self):
        with self.assertRaises(m.WNBAPropFeedCollectorConfigError):
            m.load_provider_registry(env_for(provider(response_json_path="data")))

    def test_39_response_path_depth_limit(self):
        with self.assertRaises(m.WNBAPropFeedCollectorConfigError):
            m.load_provider_registry(env_for(provider(response_json_path=["x"] * (m.MAX_RESPONSE_JSON_PATH_DEPTH + 1))))

    def test_40_list_wrapper_must_match_feed_format(self):
        with self.assertRaises(m.WNBAPropFeedCollectorConfigError):
            m.load_provider_registry(env_for(provider(list_wrapper_key="events")))

    def test_41_timeout_range_enforced(self):
        for value in (0, 31):
            with self.subTest(value=value):
                with self.assertRaises(m.WNBAPropFeedCollectorConfigError):
                    m.load_provider_registry(env_for(provider(timeout_seconds=value)))

    def test_42_response_size_range_enforced(self):
        with self.assertRaises(m.WNBAPropFeedCollectorConfigError):
            m.load_provider_registry(env_for(provider(max_response_bytes=m.MAX_RESPONSE_BYTES + 1)))

    def test_43_feed_format_enforced(self):
        with self.assertRaises(m.WNBAPropFeedCollectorConfigError):
            m.load_provider_registry(env_for(provider(feed_format="mystery")))

    def test_44_odds_format_enforced(self):
        with self.assertRaises(m.WNBAPropFeedCollectorConfigError):
            m.load_provider_registry(env_for(provider(odds_format="fractional")))

    def test_45_default_must_exist(self):
        with self.assertRaises(m.WNBAPropFeedCollectorConfigError):
            m.load_provider_registry(env_for(provider(), default="missing"))

    def test_46_default_cannot_be_disabled(self):
        with self.assertRaises(m.WNBAPropFeedCollectorConfigError):
            m.load_provider_registry(env_for(provider(enabled=False), default="demo"))

    def test_47_single_enabled_provider_auto_selected(self):
        rec = Recorder(FakeResponse({"offers": []}))
        result = m.collect_provider_feed(None, env=env_for(provider()), requester=rec, date="2026-08-26")
        self.assertEqual(result["provider_id"], "demo")

    def test_48_multiple_enabled_without_default_not_ready(self):
        e = env_for(provider(), provider(provider_id="backup"))
        with self.assertRaises(m.WNBAPropFeedCollectorNotReadyError):
            m.collect_provider_feed(None, env=e, requester=Recorder())

    def test_49_no_provider_not_ready(self):
        with self.assertRaises(m.WNBAPropFeedCollectorNotReadyError):
            m.collect_provider_feed(None, env={}, requester=Recorder())

    def test_50_unknown_provider_is_model_input_error(self):
        with self.assertRaises(m.WNBAPropFeedCollectorModelInputError):
            m.collect_provider_feed("missing", env=env_for(provider()), requester=Recorder())

    def test_51_disabled_provider_not_ready(self):
        with self.assertRaises(m.WNBAPropFeedCollectorNotReadyError):
            m.collect_provider_feed("demo", env=env_for(provider(enabled=False)), requester=Recorder())

    def test_52_missing_secret_not_ready(self):
        e = env_for(provider(secret_header_env={"Authorization": "FEED_TOKEN"}))
        with self.assertRaises(m.WNBAPropFeedCollectorNotReadyError):
            m.collect_provider_feed("demo", env=e, requester=Recorder())

    def test_53_registry_never_returns_secret_value(self):
        e = env_for(
            provider(secret_header_env={"Authorization": "FEED_TOKEN"}),
            secrets={"FEED_TOKEN": "super-secret-value"},
        )
        result = m.describe_provider_registry(e)
        self.assertNotIn("super-secret-value", json.dumps(result))

    def test_54_request_renders_date_and_season(self):
        row = provider(
            url="https://feed.example.com/{date}",
            headers={"X-Season": "{season}"},
            query_params={"date": "{date}", "season": "{season}"},
        )
        rec = Recorder(FakeResponse({"offers": []}))
        m.collect_provider_feed("demo", env=env_for(row), requester=rec, date="2026-08-26", season=2026)
        url, kwargs = rec.calls[0]
        self.assertEqual(url, "https://feed.example.com/2026-08-26")
        self.assertEqual(kwargs["headers"]["X-Season"], "2026")
        self.assertEqual(kwargs["params"]["date"], "2026-08-26")

    def test_55_secret_values_enter_request_but_not_output(self):
        row = provider(
            secret_header_env={"Authorization": "FEED_TOKEN"},
            secret_query_env={"api_key": "FEED_KEY"},
        )
        e = env_for(row, secrets={"FEED_TOKEN": "Bearer secret", "FEED_KEY": "query-secret"})
        rec = Recorder(FakeResponse({"offers": []}))
        result = m.collect_provider_feed("demo", env=e, requester=rec, date="2026-08-26")
        _, kwargs = rec.calls[0]
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer secret")
        self.assertEqual(kwargs["params"]["api_key"], "query-secret")
        encoded = json.dumps(result)
        self.assertNotIn("Bearer secret", encoded)
        self.assertNotIn("query-secret", encoded)

    def test_56_default_accept_and_user_agent_added(self):
        rec = Recorder(FakeResponse({"offers": []}))
        m.collect_provider_feed("demo", env=env_for(provider()), requester=rec, date="2026-08-26")
        headers = rec.calls[0][1]["headers"]
        self.assertEqual(headers["Accept"], "application/json")
        self.assertEqual(headers["User-Agent"], m.USER_AGENT)

    def test_57_custom_nonsecret_accept_and_user_agent_preserved(self):
        row = provider(headers={"Accept": "application/vnd.test+json", "User-Agent": "Custom/1"})
        rec = Recorder(FakeResponse({"offers": []}))
        m.collect_provider_feed("demo", env=env_for(row), requester=rec, date="2026-08-26")
        headers = rec.calls[0][1]["headers"]
        self.assertEqual(headers["Accept"], "application/vnd.test+json")
        self.assertEqual(headers["User-Agent"], "Custom/1")

    def test_58_successful_dict_payload_preserved(self):
        payload = {"offers": [{"x": 1}]}
        result = m.collect_provider_feed("demo", env=env_for(provider()), requester=Recorder(FakeResponse(payload)), date="2026-08-26")
        self.assertEqual(result["raw_feed"], payload)

    def test_59_top_level_list_auto_wrapped_for_canonical(self):
        payload = [{"x": 1}]
        result = m.collect_provider_feed("demo", env=env_for(provider()), requester=Recorder(FakeResponse(payload)), date="2026-08-26")
        self.assertEqual(result["raw_feed"], {"offers": payload})

    def test_60_top_level_list_auto_wrapped_for_bookmaker_events(self):
        row = provider(feed_format="bookmaker_event_markets_v1")
        payload = [{"id": "event-1"}]
        result = m.collect_provider_feed("demo", env=env_for(row), requester=Recorder(FakeResponse(payload)), date="2026-08-26")
        self.assertEqual(result["raw_feed"], {"events": payload})

    def test_61_nested_response_path_selected(self):
        row = provider(response_json_path=["data", "payload"])
        payload = {"data": {"payload": [{"x": 1}]}}
        result = m.collect_provider_feed("demo", env=env_for(row), requester=Recorder(FakeResponse(payload)), date="2026-08-26")
        self.assertEqual(result["raw_feed"], {"offers": [{"x": 1}]})

    def test_62_missing_nested_key_is_upstream_error(self):
        row = provider(response_json_path=["data", "missing"])
        with self.assertRaises(m.WNBAPropFeedCollectorUpstreamError):
            m.collect_provider_feed("demo", env=env_for(row), requester=Recorder(FakeResponse({"data": {}})), date="2026-08-26")

    def test_63_scalar_selected_payload_is_upstream_error(self):
        row = provider(response_json_path=["data"])
        with self.assertRaises(m.WNBAPropFeedCollectorUpstreamError):
            m.collect_provider_feed("demo", env=env_for(row), requester=Recorder(FakeResponse({"data": 5})), date="2026-08-26")

    def test_64_redirect_fails_closed(self):
        with self.assertRaises(m.WNBAPropFeedCollectorUpstreamError):
            m.collect_provider_feed("demo", env=env_for(provider()), requester=Recorder(FakeResponse(status_code=302)), date="2026-08-26")

    def test_65_401_is_not_ready(self):
        with self.assertRaises(m.WNBAPropFeedCollectorNotReadyError):
            m.collect_provider_feed("demo", env=env_for(provider()), requester=Recorder(FakeResponse(status_code=401)), date="2026-08-26")

    def test_66_403_is_not_ready(self):
        with self.assertRaises(m.WNBAPropFeedCollectorNotReadyError):
            m.collect_provider_feed("demo", env=env_for(provider()), requester=Recorder(FakeResponse(status_code=403)), date="2026-08-26")

    def test_67_429_is_not_ready(self):
        with self.assertRaises(m.WNBAPropFeedCollectorNotReadyError):
            m.collect_provider_feed("demo", env=env_for(provider()), requester=Recorder(FakeResponse(status_code=429)), date="2026-08-26")

    def test_68_500_is_upstream_error(self):
        with self.assertRaises(m.WNBAPropFeedCollectorUpstreamError):
            m.collect_provider_feed("demo", env=env_for(provider()), requester=Recorder(FakeResponse(status_code=500)), date="2026-08-26")

    def test_69_zero_status_is_upstream_error(self):
        with self.assertRaises(m.WNBAPropFeedCollectorUpstreamError):
            m.collect_provider_feed("demo", env=env_for(provider()), requester=Recorder(FakeResponse(status_code=0)), date="2026-08-26")

    def test_70_oversized_response_rejected(self):
        row = provider(max_response_bytes=5)
        response = FakeResponse({"offers": []}, content=b"123456")
        with self.assertRaises(m.WNBAPropFeedCollectorUpstreamError):
            m.collect_provider_feed("demo", env=env_for(row), requester=Recorder(response), date="2026-08-26")

    def test_71_invalid_json_rejected(self):
        response = FakeResponse(content=b"not-json", json_error=ValueError("bad"))
        with self.assertRaises(m.WNBAPropFeedCollectorUpstreamError):
            m.collect_provider_feed("demo", env=env_for(provider()), requester=Recorder(response), date="2026-08-26")

    def test_72_timeout_is_sanitized_upstream_error(self):
        rec = Recorder(error=httpx.TimeoutException("https://secret.example/?api_key=secret"))
        with self.assertRaises(m.WNBAPropFeedCollectorUpstreamError) as ctx:
            m.collect_provider_feed("demo", env=env_for(provider()), requester=rec, date="2026-08-26")
        self.assertNotIn("api_key", str(ctx.exception))

    def test_73_http_error_is_sanitized(self):
        rec = Recorder(error=httpx.ConnectError("Bearer secret"))
        with self.assertRaises(m.WNBAPropFeedCollectorUpstreamError) as ctx:
            m.collect_provider_feed("demo", env=env_for(provider()), requester=rec, date="2026-08-26")
        self.assertNotIn("Bearer secret", str(ctx.exception))

    def test_74_generic_request_error_is_sanitized(self):
        rec = Recorder(error=RuntimeError("query-secret"))
        with self.assertRaises(m.WNBAPropFeedCollectorUpstreamError) as ctx:
            m.collect_provider_feed("demo", env=env_for(provider()), requester=rec, date="2026-08-26")
        self.assertNotIn("query-secret", str(ctx.exception))

    def test_75_transport_endpoint_strips_query(self):
        rec = Recorder(FakeResponse({"offers": []}))
        result = m.collect_provider_feed("demo", env=env_for(provider()), requester=rec, date="2026-08-26")
        self.assertNotIn("?", result["transport"]["endpoint"])

    def test_76_line_board_handoff_uses_collection_metadata(self):
        collection = {
            "collection_id": "c1",
            "collection_fingerprint_sha256": "a" * 64,
            "provider_id": "demo",
            "feed_source": "Demo Feed",
            "feed_format": "canonical_offers_v1",
            "odds_format": "american",
            "date": "2026-08-26",
            "season": 2026,
            "collected_at_utc": "2026-08-26T19:00:00+00:00",
            "transport": {"status_code": 200},
            "raw_feed_sha256": "b" * 64,
            "raw_feed": {"offers": [{"x": 1}]},
        }
        seen = {}
        def fake_collector(*args, **kwargs):
            return copy.deepcopy(collection)
        def fake_builder(raw_feed, **kwargs):
            seen["raw"] = raw_feed
            seen.update(kwargs)
            return {"line_board_fingerprint_sha256": "c" * 64}
        result = m.build_collected_prop_line_board(
            "demo", collector=fake_collector, line_board_builder=fake_builder
        )
        self.assertEqual(seen["raw"], collection["raw_feed"])
        self.assertEqual(seen["feed_captured_at_utc"], collection["collected_at_utc"])
        self.assertEqual(seen["feed_source"], "Demo Feed")
        self.assertEqual(result["collection_reference"]["provider_id"], "demo")

    def test_77_line_board_forwards_market_integrity_kwargs(self):
        collection = {
            "collection_id": "c1", "collection_fingerprint_sha256": "a" * 64,
            "provider_id": "demo", "feed_source": "Demo Feed",
            "feed_format": "canonical_offers_v1", "odds_format": "american",
            "date": "2026-08-26", "season": 2026,
            "collected_at_utc": "2026-08-26T19:00:00+00:00",
            "transport": {}, "raw_feed_sha256": "b" * 64, "raw_feed": {"offers": []},
        }
        seen = {}
        def fake_collector(*args, **kwargs): return copy.deepcopy(collection)
        def fake_builder(raw_feed, **kwargs):
            seen.update(kwargs)
            return {"line_board_fingerprint_sha256": "c" * 64}
        m.build_collected_prop_line_board(
            "demo", collector=fake_collector, line_board_builder=fake_builder,
            max_market_age_minutes=7, exclude_stale_quotes=False, max_side_pair_skew_seconds=45,
        )
        self.assertEqual(seen["max_market_age_minutes"], 7)
        self.assertFalse(seen["exclude_stale_quotes"])
        self.assertEqual(seen["max_side_pair_skew_seconds"], 45)

    def test_78_daily_handoff_uses_collection_metadata(self):
        collection = {
            "collection_id": "c1", "collection_fingerprint_sha256": "a" * 64,
            "provider_id": "demo", "feed_source": "Demo Feed",
            "feed_format": "canonical_offers_v1", "odds_format": "american",
            "date": "2026-08-26", "season": 2026,
            "collected_at_utc": "2026-08-26T19:00:00+00:00",
            "transport": {}, "raw_feed_sha256": "b" * 64, "raw_feed": {"offers": []},
        }
        seen = {}
        def fake_collector(*args, **kwargs): return copy.deepcopy(collection)
        def fake_daily(raw_feed, **kwargs):
            seen["raw"] = raw_feed
            seen.update(kwargs)
            return {
                "feed_pipeline_fingerprint_sha256": "d" * 64,
                "probability_board_count": 1,
                "value_board_count": 1,
                "probability_board": [{"rank": 1}],
                "value_board": [{"rank": 1}],
            }
        result = m.build_collected_daily_top_five(
            "demo", collector=fake_collector, daily_builder=fake_daily, top_n=3
        )
        self.assertEqual(seen["feed_captured_at_utc"], collection["collected_at_utc"])
        self.assertEqual(seen["top_n"], 3)
        self.assertEqual(result["probability_board_count"], 1)
        self.assertEqual(result["probability_board"][0]["rank"], 1)

    def test_79_collection_fingerprint_is_sha256(self):
        result = m.collect_provider_feed("demo", env=env_for(provider()), requester=Recorder(), date="2026-08-26")
        self.assertEqual(len(result["collection_fingerprint_sha256"]), 64)

    def test_80_collection_semantics_freeze_downstream_authority(self):
        result = m.collect_provider_feed("demo", env=env_for(provider()), requester=Recorder(), date="2026-08-26")
        self.assertTrue(result["collector_semantics"]["step_5m_remains_authoritative_for_market_integrity"])

    def test_81_api_config_error_maps_422(self):
        with self.assertRaises(HTTPException) as ctx:
            api._raise_api_error(m.WNBAPropFeedCollectorConfigError("bad"))
        self.assertEqual(ctx.exception.status_code, 422)

    def test_82_api_not_ready_maps_409(self):
        with self.assertRaises(HTTPException) as ctx:
            api._raise_api_error(m.WNBAPropFeedCollectorNotReadyError("not ready"))
        self.assertEqual(ctx.exception.status_code, 409)

    def test_83_api_upstream_maps_502(self):
        with self.assertRaises(HTTPException) as ctx:
            api._raise_api_error(m.WNBAPropFeedCollectorUpstreamError("upstream"))
        self.assertEqual(ctx.exception.status_code, 502)

    def test_84_main_registers_all_step_5n_routes(self):
        expected = {
            "/api/v1/wnba/markets/player-props/providers",
            "/api/v1/wnba/markets/player-props/collect",
            "/api/v1/wnba/markets/player-props/collect/line-board",
            "/api/v1/wnba/rankings/player-props/collect/daily-top-five",
        }
        router_paths = {getattr(route, "path", None) for route in api.router.routes}
        self.assertTrue(expected.issubset(router_paths))

        main_source = (Path(__file__).resolve().parents[1] / "main.py").read_text(encoding="utf-8")
        self.assertIn(
            "from sports_api.api.wnba_prop_feed_collector import router as wnba_prop_feed_collector_router",
            main_source,
        )
        self.assertIn("app.include_router(wnba_prop_feed_collector_router)", main_source)


if __name__ == "__main__":
    unittest.main()
