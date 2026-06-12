"""Tests for http_io upload utility - urllib calls are mocked, no real network."""

from __future__ import annotations

import http.client
import tempfile
import urllib.error
from unittest.mock import MagicMock, patch

from app.http_io import upload_protocol


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
