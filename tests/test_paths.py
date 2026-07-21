"""Tests for app.paths base-dir resolution."""

from __future__ import annotations

from pathlib import Path

from app import paths


def test_base_dir_in_development_is_project_root() -> None:
    # app/paths.py -> app -> project root
    assert paths.base_dir() == Path(paths.__file__).resolve().parents[1]


def test_app_path_joins_under_base_dir(monkeypatch) -> None:
    monkeypatch.setattr(paths, "base_dir", lambda: Path("/opt/app"))
    assert paths.app_path("fpg_info.txt") == Path("/opt/app/fpg_info.txt")
    assert paths.app_path("temp") == Path("/opt/app/temp")


def test_base_dir_frozen_uses_executable_folder(monkeypatch) -> None:
    monkeypatch.setattr(paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(
        paths.sys, "executable", "/downloads/FinishProtocolGenerator", raising=False
    )
    assert paths.base_dir() == Path("/downloads")


def test_base_dir_frozen_macos_app_uses_bundle_parent(monkeypatch) -> None:
    monkeypatch.setattr(paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(
        paths.sys,
        "executable",
        "/Applications/FinishProtocolGenerator.app/Contents/MacOS/FinishProtocolGenerator",
        raising=False,
    )
    assert paths.base_dir() == Path("/Applications")
