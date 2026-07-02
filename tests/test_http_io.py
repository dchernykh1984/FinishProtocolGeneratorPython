"""Tests for http_io upload utility - urllib calls are mocked, no real network."""

from __future__ import annotations

import http.client
import json
import tempfile
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from app.http_io import (
    delete_protocol,
    fetch_finish_times,
    fetch_group_times,
    fetch_remote_points,
    fetch_start_list,
    upload_protocol,
)


def _mock_json_response(data: object) -> MagicMock:
    resp = MagicMock()
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    resp.read.return_value = json.dumps(data).encode("utf-8")
    return resp


class TestFetchTimingStreams:
    def test_group_times_merges_devices(self) -> None:
        payload = {"devices": [{"items": ["G1#0 0:0:1#"]}, {"items": ["G2#0 0:0:2#"]}]}
        with patch("urllib.request.urlopen", return_value=_mock_json_response(payload)):
            assert fetch_group_times("https://x", "tok") == [
                "G1#0 0:0:1#",
                "G2#0 0:0:2#",
            ]

    def test_finish_times_endpoint_and_merge(self) -> None:
        captured: dict = {}

        def fake(url, timeout=10):
            captured["url"] = url
            return _mock_json_response({"devices": [{"items": ["1#0 0:0:9#"]}]})

        with patch("urllib.request.urlopen", side_effect=fake):
            assert fetch_finish_times("https://x", "tok") == ["1#0 0:0:9#"]
        assert "/api/v1/finish-times/" in captured["url"]

    def test_remote_points_returns_point_to_lines_map(self) -> None:
        payload = {
            "points": [
                {"point_number": 1, "items": ["1#0 0:1:0#", "2#0 0:1:5#"]},
                {"point_number": 2, "items": ["1#0 0:2:0#"]},
            ]
        }
        with patch("urllib.request.urlopen", return_value=_mock_json_response(payload)):
            got = fetch_remote_points("https://x", "tok")
        assert got == {1: ["1#0 0:1:0#", "2#0 0:1:5#"], 2: ["1#0 0:2:0#"]}

    def test_remote_points_empty(self) -> None:
        with patch(
            "urllib.request.urlopen", return_value=_mock_json_response({"points": []})
        ):
            assert fetch_remote_points("https://x", "tok") == {}

    def test_group_times_http_error_raises(self) -> None:
        exc = urllib.error.HTTPError(
            "u", 401, "Unauthorized", http.client.HTTPMessage(), None
        )
        with (
            patch("urllib.request.urlopen", side_effect=exc),
            pytest.raises(ValueError, match="401"),
        ):
            fetch_group_times("https://x", "bad")

    def test_remote_points_connection_error_raises(self) -> None:
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
            with pytest.raises(ValueError, match="Connection error"):
                fetch_remote_points("https://x", "tok")


class TestFetchStartList:
    def test_merges_devices_in_order(self) -> None:
        payload = {
            "devices": [
                {"device_id": "a", "items": ["1#A##1#", "2#A2##1#"]},
                {"device_id": "b", "items": ["10#B##1#"]},
            ],
            "items": ["ignored-convenience-field"],
        }
        with patch("urllib.request.urlopen", return_value=_mock_json_response(payload)):
            lines = fetch_start_list("https://example.com", "tok")
        assert lines == ["1#A##1#", "2#A2##1#", "10#B##1#"]

    def test_empty_devices_returns_empty(self) -> None:
        with patch(
            "urllib.request.urlopen",
            return_value=_mock_json_response({"devices": [], "items": []}),
        ):
            assert fetch_start_list("https://example.com", "tok") == []

    def test_url_includes_token_and_endpoint(self) -> None:
        captured: list[str] = []

        def fake(url, timeout=None):
            captured.append(url)
            return _mock_json_response({"devices": []})

        with patch("urllib.request.urlopen", side_effect=fake):
            fetch_start_list("https://site.com/", "my-token")
        assert captured[0].startswith("https://site.com/api/v1/start-list/")
        assert "competition_token=my-token" in captured[0]

    def test_http_error_raises(self) -> None:
        exc = urllib.error.HTTPError(
            "u", 401, "Unauthorized", http.client.HTTPMessage(), None
        )
        with patch("urllib.request.urlopen", side_effect=exc):
            with pytest.raises(ValueError, match="HTTP 401"):
                fetch_start_list("https://example.com", "bad")

    def test_connection_error_raises(self) -> None:
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("down")):
            with pytest.raises(ValueError, match="Connection error"):
                fetch_start_list("https://example.com", "tok")

    def test_invalid_json_raises(self) -> None:
        resp = MagicMock()
        resp.__enter__ = MagicMock(return_value=resp)
        resp.__exit__ = MagicMock(return_value=False)
        resp.read.return_value = b"not json"
        with patch("urllib.request.urlopen", return_value=resp):
            with pytest.raises(ValueError):
                fetch_start_list("https://example.com", "tok")


def _local(content: bytes = b"<html><body>Test</body></html>") -> str:
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as f:
        f.write(content)
        return f.name


def _mock_ok_response() -> MagicMock:
    resp = MagicMock()
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    resp.status = 200
    return resp


class TestUploadProtocol:
    def test_returns_minus1_when_site_url_empty(self) -> None:
        assert upload_protocol("", "token", "absolute", _local()) == -1

    def test_returns_minus1_when_local_path_empty(self) -> None:
        assert upload_protocol("http://example.com", "token", "absolute", "") == -1

    def test_returns_minus1_when_file_not_found(self) -> None:
        result = upload_protocol(
            "http://example.com", "t", "absolute", "/nonexistent/file.html"
        )
        assert result == -1

    def test_returns_0_on_success(self) -> None:
        local = _local()
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value = _mock_ok_response()
            result = upload_protocol("http://example.com", "token", "absolute", local)
        assert result == 0

    def test_returns_0_on_http_201(self) -> None:
        local = _local()
        resp_201 = _mock_ok_response()
        resp_201.status = 201
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value = resp_201
            result = upload_protocol("http://example.com", "token", "absolute", local)
        assert result == 0

    def test_returns_minus1_on_http_401(self) -> None:
        local = _local()
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.side_effect = urllib.error.HTTPError(
                "http://example.com/api/v1/protocols/upload/",
                401,
                "Unauthorized",
                http.client.HTTPMessage(),
                None,
            )
            result = upload_protocol(
                "http://example.com", "bad-token", "absolute", local
            )
        assert result == -1

    def test_returns_minus1_on_connection_error(self) -> None:
        local = _local()
        with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
            result = upload_protocol("http://example.com", "t", "absolute", local)
        assert result == -1

    def test_errors_out_populated_on_os_error(self) -> None:
        local = _local()
        errors: list[str] = []
        with patch("urllib.request.urlopen", side_effect=OSError("refused")):
            upload_protocol(
                "http://example.com", "t", "absolute", local, errors_out=errors
            )
        assert len(errors) == 1
        assert "example.com" in errors[0]

    def test_errors_out_populated_on_http_error(self) -> None:
        local = _local()
        errors: list[str] = []
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.side_effect = urllib.error.HTTPError(
                "http://example.com/api/v1/protocols/upload/",
                403,
                "Forbidden",
                http.client.HTTPMessage(),
                None,
            )
            upload_protocol(
                "http://example.com", "t", "absolute", local, errors_out=errors
            )
        assert len(errors) == 1
        assert "403" in errors[0]

    def test_errors_out_empty_on_success(self) -> None:
        local = _local()
        errors: list[str] = []
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value = _mock_ok_response()
            upload_protocol(
                "http://example.com", "token", "absolute", local, errors_out=errors
            )
        assert errors == []

    def test_errors_out_empty_site_url_message(self) -> None:
        errors: list[str] = []
        upload_protocol("", "token", "absolute", _local(), errors_out=errors)
        assert len(errors) == 1
        assert "empty" in errors[0].lower()

    def test_errors_out_file_not_found_message(self) -> None:
        errors: list[str] = []
        upload_protocol(
            "http://example.com",
            "t",
            "absolute",
            "/nope/file.html",
            errors_out=errors,
        )
        assert len(errors) == 1
        assert "file.html" in errors[0]

    def test_url_constructed_with_trailing_slash(self) -> None:
        local = _local()
        captured: list[str] = []

        def fake_urlopen(req, timeout=None):
            captured.append(req.full_url)
            return _mock_ok_response()

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            upload_protocol("http://example.com/", "t", "absolute", local)
        assert captured[0] == "http://example.com/api/v1/protocols/upload/"

    def test_url_constructed_without_trailing_slash(self) -> None:
        local = _local()
        captured: list[str] = []

        def fake_urlopen(req, timeout=None):
            captured.append(req.full_url)
            return _mock_ok_response()

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            upload_protocol("http://example.com", "t", "absolute", local)
        assert captured[0] == "http://example.com/api/v1/protocols/upload/"

    def test_is_live_false_in_body(self) -> None:
        local = _local()
        captured: list[bytes] = []

        def fake_urlopen(req, timeout=None):
            captured.append(req.data)
            return _mock_ok_response()

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            upload_protocol("http://example.com", "t", "absolute", local, is_live=False)
        assert b"false" in captured[0]

    def test_stage_label_in_body(self) -> None:
        local = _local()
        captured: list[bytes] = []

        def fake_urlopen(req, timeout=None):
            captured.append(req.data)
            return _mock_ok_response()

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            upload_protocol(
                "http://example.com", "t", "absolute", local, stage_label="Lap 3"
            )
        assert b"Lap 3" in captured[0]

    def test_multipart_content_type_header(self) -> None:
        local = _local()
        captured: list[str] = []

        def fake_urlopen(req, timeout=None):
            captured.append(req.get_header("Content-type"))
            return _mock_ok_response()

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            upload_protocol("http://example.com", "t", "absolute", local)
        assert captured[0].startswith("multipart/form-data; boundary=")

    def test_file_content_included_in_body(self) -> None:
        content = b"<html><body>My Race Results</body></html>"
        local = _local(content)
        captured: list[bytes] = []

        def fake_urlopen(req, timeout=None):
            captured.append(req.data)
            return _mock_ok_response()

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            upload_protocol("http://example.com", "t", "absolute", local)
        assert b"My Race Results" in captured[0]

    def test_competition_token_field_name_in_body(self) -> None:
        local = _local()
        captured: list[bytes] = []

        def fake_urlopen(req, timeout=None):
            captured.append(req.data)
            return _mock_ok_response()

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            upload_protocol("http://example.com", "my-token", "absolute", local)
        assert b'name="competition_token"' in captured[0]
        assert b"my-token" in captured[0]

    def test_protocol_type_field_in_body(self) -> None:
        local = _local()
        captured: list[bytes] = []

        def fake_urlopen(req, timeout=None):
            captured.append(req.data)
            return _mock_ok_response()

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            upload_protocol("http://example.com", "t", "group", local)
        assert b'name="protocol_type"' in captured[0]
        assert b"group" in captured[0]


class TestDeleteProtocol:
    def test_returns_minus1_when_site_url_empty(self) -> None:
        errors: list[str] = []
        assert delete_protocol("", "tok", "group", errors) == -1
        assert errors

    def test_returns_0_on_success_and_posts_type(self) -> None:
        captured: dict = {}

        def fake(req, timeout=30):
            captured["url"] = req.full_url
            captured["body"] = req.data.decode()
            return _mock_ok_response()

        with patch("urllib.request.urlopen", side_effect=fake):
            assert delete_protocol("https://s/", "tok", "group") == 0
        assert captured["url"] == "https://s/api/v1/protocols/delete/"
        assert "protocol_type=group" in captured["body"]
        assert "competition_token=tok" in captured["body"]

    def test_returns_minus1_on_http_error(self) -> None:
        exc = urllib.error.HTTPError("u", 500, "err", http.client.HTTPMessage(), None)
        errors: list[str] = []
        with patch("urllib.request.urlopen", side_effect=exc):
            assert delete_protocol("https://s", "tok", "group", errors) == -1
        assert errors

    def test_returns_minus1_on_connection_error(self) -> None:
        with patch("urllib.request.urlopen", side_effect=OSError("refused")):
            assert delete_protocol("https://s", "tok", "group") == -1
