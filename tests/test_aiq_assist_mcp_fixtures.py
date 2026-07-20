from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, cast

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_aiq_assist_mcp_fixtures.py"
_SCRIPT_SPEC = importlib.util.spec_from_file_location("check_aiq_assist_mcp_fixtures", _SCRIPT_PATH)
assert _SCRIPT_SPEC is not None
assert _SCRIPT_SPEC.loader is not None
fixture_check = importlib.util.module_from_spec(_SCRIPT_SPEC)
sys.modules[_SCRIPT_SPEC.name] = fixture_check
_SCRIPT_SPEC.loader.exec_module(fixture_check)


def _fixture(case: str) -> dict[str, Any]:
    fixture_path = fixture_check.FIXTURE_DIR / f"{case}.json"
    return cast(dict[str, Any], json.loads(fixture_path.read_text(encoding="utf-8")))


def _write_fixture(tmp_path: Path, fixture: dict[str, Any]) -> Path:
    fixture_path = tmp_path / f"{fixture['case']}.json"
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")
    return fixture_path


def test_repo_aiq_assist_mcp_fixtures_pass_contract_gate() -> None:
    assert fixture_check.validate_fixture_set() == []


def test_fixture_case_matrix_covers_auth_success_and_failure() -> None:
    outcomes_by_auth_mode: dict[str, set[str]] = {}
    for auth_mode, outcome in fixture_check.EXPECTED_CASES.values():
        outcomes_by_auth_mode.setdefault(auth_mode, set()).add(outcome)

    assert outcomes_by_auth_mode["oauth"] >= {"success", "auth_failure"}
    assert outcomes_by_auth_mode["token"] >= {"success", "auth_failure"}


def test_fixture_case_matrix_covers_failure_and_redaction_cases() -> None:
    assert fixture_check.EXPECTED_CASES["malformed_response"] == (
        "token",
        "malformed_response",
    )
    assert fixture_check.EXPECTED_CASES["timeout_failure"] == ("oauth", "timeout")
    assert fixture_check.EXPECTED_CASES["provider_error_redaction"] == (
        "token",
        "provider_error",
    )

    fixture_path = fixture_check.FIXTURE_DIR / "provider_error_redaction.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

    error = fixture["response"]["body"]["error"]
    assert error["message"] == "Provider rejected Authorization: Bearer <redacted>"
    assert fixture["expected"] == {"outcome": "provider_error", "redacted": True}


def test_fixture_gate_rejects_unredacted_bearer_value(tmp_path: Path) -> None:
    fixture_path = tmp_path / "provider_error_redaction.json"
    fixture = {
        "case": "provider_error_redaction",
        "contract": fixture_check.CONTRACT_NAME,
        "contract_version": fixture_check.CONTRACT_VERSION,
        "endpoint_path": fixture_check.ENDPOINT_PATH,
        "live": False,
        "auth_mode": "token",
        "request": {
            "method": "POST",
            "path": fixture_check.ENDPOINT_PATH,
            "body": {
                "jsonrpc": "2.0",
                "id": "fixture-provider-error",
                "method": "tools/call",
                "params": {},
            },
        },
        "response": {
            "status_code": 502,
            "body": {
                "jsonrpc": "2.0",
                "id": "fixture-provider-error",
                "error": {
                    "message": "Provider rejected Authorization: Bearer live-secret-token"
                },
            },
        },
        "expected": {"outcome": "provider_error", "redacted": True},
    }
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

    errors = fixture_check.validate_fixture_file(fixture_path)

    assert any("unredacted bearer value" in error for error in errors)


def test_fixture_gate_requires_complete_case_set(tmp_path: Path) -> None:
    errors = fixture_check.validate_fixture_set(tmp_path)

    assert any("missing fixture case 'discovery_success'" in error for error in errors)


def test_fixture_gate_rejects_oversized_fixture(tmp_path: Path) -> None:
    fixture = _fixture("discovery_success")
    fixture["response"]["body"]["result"]["provider_extension"] = (
        "x" * fixture_check.MAX_FIXTURE_BYTES
    )

    errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

    assert errors == [
        f"{tmp_path / 'discovery_success.json'}: fixture must not exceed "
        f"{fixture_check.MAX_FIXTURE_BYTES} bytes"
    ]


def test_fixture_gate_rejects_duplicate_json_object_names(tmp_path: Path) -> None:
    fixture_json = json.dumps(_fixture("discovery_success"))
    duplicate_documents = {
        "top-level.json": fixture_json.replace(
            "{", '{"case": "shadowed-case", ', 1
        ),
        "nested.json": fixture_json.replace(
            '"result": {"tools":',
            '"result": {"provider_extension": 1, "provider_extension": 2, "tools":',
            1,
        ),
    }

    for filename, document in duplicate_documents.items():
        fixture_path = tmp_path / filename
        fixture_path.write_text(document, encoding="utf-8")

        assert fixture_check.validate_fixture_file(fixture_path) == [
            f"{fixture_path}: fixture must not contain duplicate JSON object names"
        ]


def test_fixture_gate_rejects_non_finite_json_numbers(tmp_path: Path) -> None:
    fixture_json = json.dumps(_fixture("discovery_success"))

    for index, constant in enumerate(("NaN", "Infinity", "-Infinity")):
        fixture_path = tmp_path / f"non-finite-{index}.json"
        document = fixture_json.replace(
            '"result": {"tools":',
            f'"result": {{"provider_extension": {constant}, "tools":',
            1,
        )
        fixture_path.write_text(document, encoding="utf-8")

        assert fixture_check.validate_fixture_file(fixture_path) == [
            f"{fixture_path}: fixture must not contain non-finite JSON numbers"
        ]


def test_fixture_gate_rejects_overflowing_json_floats(tmp_path: Path) -> None:
    fixture_json = json.dumps(_fixture("discovery_success"))

    for index, number in enumerate(("1e999", "-1e999")):
        fixture_path = tmp_path / f"overflowing-float-{index}.json"
        document = fixture_json.replace(
            '"result": {"tools":',
            f'"result": {{"provider_extension": {number}, "tools":',
            1,
        )
        fixture_path.write_text(document, encoding="utf-8")

        assert fixture_check.validate_fixture_file(fixture_path) == [
            f"{fixture_path}: fixture must not contain non-finite JSON numbers"
        ]


def test_fixture_gate_rejects_success_without_result(tmp_path: Path) -> None:
    fixture = _fixture("discovery_success")
    fixture["response"]["body"].pop("result")

    errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

    assert any("success fixture must contain result and no error" in error for error in errors)


def test_fixture_gate_rejects_case_request_method_drift(tmp_path: Path) -> None:
    fixture = _fixture("discovery_success")
    fixture["request"]["body"]["method"] = "tools/call"

    errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

    assert any("request.body.method must be 'tools/list'" in error for error in errors)


def test_fixture_gate_rejects_response_id_mismatch(tmp_path: Path) -> None:
    fixture = _fixture("tool_invocation_success")
    fixture["response"]["body"]["id"] = "different-request-id"

    errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

    assert any("response.body.id must match request.body.id" in error for error in errors)


def test_fixture_gate_rejects_auth_failure_with_success_status(tmp_path: Path) -> None:
    fixture = _fixture("oauth_auth_failure")
    fixture["response"]["status_code"] = 200

    errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

    assert any("auth_failure fixture status must be 401 or 403" in error for error in errors)


def test_fixture_gate_requires_bounded_http_status(tmp_path: Path) -> None:
    invalid_values: tuple[Any, ...] = (None, True, "200", 99, 600)
    for status_code in invalid_values:
        fixture = _fixture("malformed_response")
        fixture["response"]["status_code"] = status_code

        errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

        assert any(
            "status_code must be an integer from 100 through 599" in error for error in errors
        )


def test_fixture_gate_bounds_provider_error_status(tmp_path: Path) -> None:
    for status_code in (399, 600):
        fixture = _fixture("provider_error_redaction")
        fixture["response"]["status_code"] = status_code

        errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

        assert any(
            "provider_error fixture status must be from 400 through 599" in error
            for error in errors
        )


def test_fixture_gate_allows_upper_provider_error_status_boundary(tmp_path: Path) -> None:
    fixture = _fixture("provider_error_redaction")
    fixture["response"]["status_code"] = 599

    assert fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture)) == []


def test_fixture_gate_requires_auth_failure_integer_error_code(tmp_path: Path) -> None:
    invalid_values: tuple[Any, ...] = (None, True, "401")
    for code in invalid_values:
        fixture = _fixture("oauth_auth_failure")
        fixture["response"]["body"]["error"]["code"] = code

        errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

        assert any("auth_failure fixture response.body.error.code" in error for error in errors)


def test_fixture_gate_requires_auth_failure_non_empty_error_message(tmp_path: Path) -> None:
    invalid_values: tuple[Any, ...] = (None, "", "  ", 401)
    for message in invalid_values:
        fixture = _fixture("oauth_auth_failure")
        fixture["response"]["body"]["error"]["message"] = message

        errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

        assert any("auth_failure fixture response.body.error.message" in error for error in errors)


def test_fixture_gate_requires_provider_error_integer_error_code(tmp_path: Path) -> None:
    invalid_values: tuple[Any, ...] = (None, True, "502")
    for code in invalid_values:
        fixture = _fixture("provider_error_redaction")
        fixture["response"]["body"]["error"]["code"] = code

        errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

        assert any("provider_error fixture response.body.error.code" in error for error in errors)


def test_fixture_gate_requires_provider_error_non_empty_error_message(tmp_path: Path) -> None:
    invalid_values: tuple[Any, ...] = (None, "", "  ", 502)
    for message in invalid_values:
        fixture = _fixture("provider_error_redaction")
        fixture["response"]["body"]["error"]["message"] = message

        errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

        assert any(
            "provider_error fixture response.body.error.message" in error for error in errors
        )


def test_fixture_gate_rejects_timeout_with_response(tmp_path: Path) -> None:
    fixture = _fixture("timeout_failure")
    fixture["response"] = {"status_code": 504, "body": {}}

    errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

    assert any("timeout fixture must not contain a response" in error for error in errors)


def test_fixture_gate_rejects_valid_envelope_for_malformed_case(tmp_path: Path) -> None:
    fixture = _fixture("malformed_response")
    fixture["response"]["body"] = {
        "jsonrpc": "2.0",
        "id": fixture["request"]["body"]["id"],
        "result": {},
    }

    errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

    assert any("must not contain a valid JSON-RPC envelope" in error for error in errors)


def test_fixture_gate_requires_explicit_redaction_expectation(tmp_path: Path) -> None:
    fixture = _fixture("tool_invocation_success")
    fixture["expected"]["redacted"] = False

    errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

    assert any("expected.redacted must be true" in error for error in errors)


def test_fixture_gate_rejects_unexpected_top_level_field(tmp_path: Path) -> None:
    fixture = _fixture("discovery_success")
    fixture["captured_at"] = "synthetic-time"

    errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

    assert any("fixture must contain exactly" in error for error in errors)


def test_fixture_gate_rejects_unexpected_expectation_field(tmp_path: Path) -> None:
    fixture = _fixture("discovery_success")
    fixture["expected"]["notes"] = "synthetic-note"

    errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

    assert any("expected must contain exactly outcome, redacted" in error for error in errors)


def test_fixture_gate_rejects_unexpected_request_field(tmp_path: Path) -> None:
    fixture = _fixture("discovery_success")
    fixture["request"]["timeout_seconds"] = 10

    errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

    assert any("request must contain exactly" in error for error in errors)


def test_fixture_gate_rejects_unexpected_request_body_field(tmp_path: Path) -> None:
    fixture = _fixture("discovery_success")
    fixture["request"]["body"]["context"] = {}

    errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

    assert any("request.body must contain exactly" in error for error in errors)


def test_fixture_gate_rejects_unexpected_response_field(tmp_path: Path) -> None:
    fixture = _fixture("discovery_success")
    fixture["response"]["elapsed_ms"] = 1

    errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

    assert any("response must contain exactly body, status_code" in error for error in errors)


def test_fixture_gate_rejects_unexpected_timeout_error_field(tmp_path: Path) -> None:
    fixture = _fixture("timeout_failure")
    fixture["error"]["retryable"] = False

    errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

    assert any("error must contain exactly message, type" in error for error in errors)


def test_fixture_gate_allows_provider_response_extensions(tmp_path: Path) -> None:
    success_fixture = _fixture("discovery_success")
    success_body = success_fixture["response"]["body"]
    success_body["provider_extension"] = {"synthetic": True}
    success_body["result"]["provider_extension"] = {"synthetic": True}

    error_fixture = _fixture("provider_error_redaction")
    error_body = error_fixture["response"]["body"]
    error_body["provider_extension"] = {"synthetic": True}
    error_body["error"]["provider_extension"] = {"synthetic": True}

    assert fixture_check.validate_fixture_file(_write_fixture(tmp_path, success_fixture)) == []
    assert fixture_check.validate_fixture_file(_write_fixture(tmp_path, error_fixture)) == []


def test_fixture_gate_rejects_sensitive_value_with_redacted_suffix(tmp_path: Path) -> None:
    fixture = _fixture("discovery_success")
    fixture["request"]["headers"]["Authorization"] = "live-secret-token <redacted>"

    errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

    assert any("must contain only a redacted placeholder" in error for error in errors)


def test_fixture_gate_rejects_deceptive_example_hostname(tmp_path: Path) -> None:
    fixture = _fixture("discovery_success")
    fixture["response"]["body"]["result"]["reference"] = "https://example.com.evil/path"

    errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

    assert any("contains a disallowed URL" in error for error in errors)


def test_fixture_gate_allows_exact_example_hostname(tmp_path: Path) -> None:
    fixture = _fixture("discovery_success")
    fixture["response"]["body"]["result"]["reference"] = "https://example.com/path"

    assert fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture)) == []


def test_fixture_gate_rejects_non_https_url_schemes(tmp_path: Path) -> None:
    for reference in (
        "http://example.com/path",
        "ftp://example.com/path",
        "file:///tmp/synthetic",
    ):
        fixture = _fixture("discovery_success")
        fixture["response"]["body"]["result"]["reference"] = reference

        errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

        assert any("contains a disallowed URL" in error for error in errors)


def test_fixture_gate_rejects_invalid_https_port(tmp_path: Path) -> None:
    fixture = _fixture("discovery_success")
    fixture["response"]["body"]["result"]["reference"] = (
        "https://example.com:99999/path"
    )

    errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

    assert any("contains a disallowed URL" in error for error in errors)


def test_fixture_gate_rejects_url_credentials_on_example_host(tmp_path: Path) -> None:
    fixture = _fixture("discovery_success")
    fixture["response"]["body"]["result"]["reference"] = (
        "https://user:password@example.com/path"
    )

    errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

    assert any("contains a disallowed URL" in error for error in errors)


def test_fixture_gate_rejects_raw_transcript_key(tmp_path: Path) -> None:
    fixture = _fixture("discovery_success")
    fixture["raw_transcript"] = "synthetic transcript"

    errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

    assert any("must not store raw MCP transcripts" in error for error in errors)


def test_fixture_gate_rejects_dotted_sensitive_key(tmp_path: Path) -> None:
    fixture = _fixture("discovery_success")
    fixture["response"]["body"]["result"]["token.value"] = "live-secret-token"

    errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

    assert any("must contain only a redacted placeholder" in error for error in errors)


def test_fixture_gate_rejects_auth_mode_words_in_sensitive_fields(tmp_path: Path) -> None:
    for key, value in (("access_token", "token"), ("password", "oauth")):
        fixture = _fixture("discovery_success")
        fixture["response"]["body"]["result"][key] = value

        errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

        assert any("must contain only a redacted placeholder" in error for error in errors)


def test_fixture_gate_rejects_dotted_raw_transcript_key(tmp_path: Path) -> None:
    fixture = _fixture("discovery_success")
    fixture["response"]["body"]["result"]["raw_transcript.value"] = (
        "synthetic transcript"
    )

    errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

    assert any("must not store raw MCP transcripts" in error for error in errors)


def test_fixture_set_rejects_unexpected_non_json_artifact(tmp_path: Path) -> None:
    artifact_path = tmp_path / "raw_transcript.txt"
    artifact_path.write_text("synthetic transcript", encoding="utf-8")

    errors = fixture_check.validate_fixture_set(tmp_path)

    assert any("unexpected artifact in closed fixture inventory" in error for error in errors)


def test_fixture_set_binds_filename_to_declared_case(tmp_path: Path) -> None:
    fixture = _fixture("discovery_success")
    fixture["case"] = "token_discovery_success"
    fixture_path = tmp_path / "discovery_success.json"
    fixture_path.write_text(json.dumps(fixture), encoding="utf-8")

    errors = fixture_check.validate_fixture_set(tmp_path)

    assert any("filename requires case 'discovery_success'" in error for error in errors)


def test_fixture_set_rejects_symbolic_links(tmp_path: Path) -> None:
    fixture = _fixture("discovery_success")
    fixture_target = tmp_path / "fixture-target.json"
    fixture_target.write_text(json.dumps(fixture), encoding="utf-8")
    fixture_root = tmp_path / "fixtures"
    fixture_root.mkdir()
    (fixture_root / "discovery_success.json").symlink_to(fixture_target)

    errors = fixture_check.validate_fixture_set(fixture_root)

    assert any("fixture inventory must not contain symbolic links" in error for error in errors)


def test_fixture_set_rejects_subdirectories(tmp_path: Path) -> None:
    (tmp_path / "raw_transcripts").mkdir()

    errors = fixture_check.validate_fixture_set(tmp_path)

    assert any("fixture inventory must contain only regular files" in error for error in errors)


def test_fixture_set_requires_regular_directory_root(tmp_path: Path) -> None:
    fixture_root = tmp_path / "fixtures"
    fixture_root.write_text("not a directory", encoding="utf-8")

    errors = fixture_check.validate_fixture_set(fixture_root)

    assert errors == [f"{fixture_root}: fixture root must be a regular directory"]


def test_fixture_gate_requires_request_headers_object(tmp_path: Path) -> None:
    fixture = _fixture("discovery_success")
    fixture["request"].pop("headers")

    errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

    assert any("request.headers must be an object" in error for error in errors)


def test_fixture_gate_requires_minimal_request_header_set(tmp_path: Path) -> None:
    fixture = _fixture("discovery_success")
    fixture["request"]["headers"].pop("Authorization")

    errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

    assert any("must contain exactly Authorization and Content-Type" in error for error in errors)


def test_fixture_gate_rejects_cookie_header_source(tmp_path: Path) -> None:
    fixture = _fixture("discovery_success")
    fixture["request"]["headers"]["Cookie"] = "<redacted>"

    errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

    assert any("must contain exactly Authorization and Content-Type" in error for error in errors)


def test_fixture_gate_rejects_duplicate_case_insensitive_header(tmp_path: Path) -> None:
    fixture = _fixture("discovery_success")
    fixture["request"]["headers"]["authorization"] = "<redacted>"

    errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

    assert any("contains duplicate header 'authorization'" in error for error in errors)


def test_fixture_gate_rejects_non_json_content_type(tmp_path: Path) -> None:
    for content_type in ("text/plain", None):
        fixture = _fixture("discovery_success")
        fixture["request"]["headers"]["Content-Type"] = content_type

        errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

        assert any(
            "request.headers.Content-Type must be 'application/json'" in error for error in errors
        )


def test_fixture_gate_accepts_case_insensitive_required_headers(tmp_path: Path) -> None:
    fixture = _fixture("discovery_success")
    fixture["request"]["headers"] = {
        "authorization": "Bearer <redacted>",
        "content-type": "application/json",
    }

    assert fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture)) == []


def test_fixture_gate_requires_empty_discovery_params(tmp_path: Path) -> None:
    fixture = _fixture("discovery_success")
    fixture["request"]["body"]["params"] = {"name": "synthetic.tool"}

    errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

    assert any("tools/list request.body.params must be empty" in error for error in errors)


def test_fixture_gate_requires_tool_call_param_keys(tmp_path: Path) -> None:
    fixture = _fixture("tool_invocation_success")
    fixture["request"]["body"]["params"].pop("name")

    errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

    assert any("must contain exactly name and arguments" in error for error in errors)


def test_fixture_gate_rejects_blank_tool_call_name(tmp_path: Path) -> None:
    fixture = _fixture("tool_invocation_success")
    fixture["request"]["body"]["params"]["name"] = "  "

    errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

    assert any("params.name must be a non-empty string" in error for error in errors)


def test_fixture_gate_requires_tool_call_arguments_object(tmp_path: Path) -> None:
    fixture = _fixture("tool_invocation_success")
    fixture["request"]["body"]["params"]["arguments"] = []

    errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

    assert any("params.arguments must be an object" in error for error in errors)


def test_fixture_gate_rejects_extra_tool_call_params(tmp_path: Path) -> None:
    fixture = _fixture("tool_invocation_success")
    fixture["request"]["body"]["params"]["context"] = {}

    errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

    assert any("must contain exactly name and arguments" in error for error in errors)


def test_fixture_gate_requires_non_empty_discovery_tools(tmp_path: Path) -> None:
    invalid_values: tuple[Any, ...] = (None, [], {})
    for tools in invalid_values:
        fixture = _fixture("discovery_success")
        fixture["response"]["body"]["result"]["tools"] = tools

        errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

        assert any("result.tools must be a non-empty list" in error for error in errors)


def test_fixture_gate_requires_non_empty_tool_call_content(tmp_path: Path) -> None:
    invalid_values: tuple[Any, ...] = (None, [], {})
    for content in invalid_values:
        fixture = _fixture("tool_invocation_success")
        fixture["response"]["body"]["result"]["content"] = content

        errors = fixture_check.validate_fixture_file(_write_fixture(tmp_path, fixture))

        assert any("result.content must be a non-empty list" in error for error in errors)
