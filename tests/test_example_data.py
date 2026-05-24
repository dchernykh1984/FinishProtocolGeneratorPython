"""Integration tests for the full pipeline against committed example data.

Data added in commits:
  f232d1a - data/ files + fpg_info.txt (start/groups/results)
  01de9b7 - configurable labels added to fpg_info.txt
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from app.calculator import calculate_protocol, generate_sorted_protocol
from app.config import RACE_TYPE_MASS_SPLITTED, HtmlStyles, RaceConfig
from app.file_io import (
    load_config_file,
    load_template,
    read_finish_times,
    read_group_times,
    read_start_protocol,
)
from app.html_writer import write_absolute_protocol, write_group_protocol
from app.models import INF

# ---------------------------------------------------------------------------
# constants (Cyrillic stored as unicode escapes to satisfy no-non-ascii hook)
# ---------------------------------------------------------------------------

_CONFIG_PATH = "fpg_info.txt"
_START_PATH = "data/start.txt"
_GROUPS_PATH = "data/groups.txt"
_RESULTS_PATH = "data/results.txt"
_GOLDEN_GRP = "data/grp_prot.html"
_GOLDEN_ABS = "data/abs_python.html"

_RACE_NAME = (
    "Test Race \u0422\u0435\u0441\u0442\u043e\u0432\u0430\u044f"
    " \u0413\u043e\u043d\u043a\u0430"
)
_WEATHER_LABEL = (
    "\u041f\u043e\u0433\u043e\u0434\u043d\u044b\u0435 "
    "\u0443\u0441\u043b\u043e\u0432\u0438\u044f"
)
_TRACK_LABEL = (
    "\u0421\u043e\u0441\u0442\u043e\u044f\u043d\u0438\u0435 "
    "\u0442\u0440\u0430\u0441\u0441\u044b"
)
_ORGANIZER_LABEL = (
    "\u041e\u0440\u0433\u0430\u043d\u0438\u0437\u0430\u0442\u043e\u0440"
    " \u0441\u043e\u0440\u0435\u0432\u043d\u043e\u0432\u0430\u043d\u0438\u0439"
)
_OVERALL_LABEL = (
    "\u0410\u0431\u0441\u043e\u043b\u044e\u0442\u043d\u044b\u0439"
    " \u043f\u0440\u043e\u0442\u043e\u043a\u043e\u043b"
)
_WINNER_NAME = (
    "\u041f\u0440\u043e\u0445\u043e\u0440\u043e\u0432 \u0411\u043e\u0440\u0438\u0441"
)
_WINNER_BIB = "26"

# Flags reset to False before C++ positional parsing (mirrors production loading).
_CPP_RESET_FLAGS = (
    "show_id",
    "show_name",
    "show_age",
    "show_team",
    "show_city",
    "show_lap_times",
    "show_lap_finish",
    "hide_empty_columns",
    "use_buttons",
    "use_all_buttons",
    "upload_groups",
    "upload_absolute",
    "show_finish_time",
    "show_time_difference",
    "show_n_finished_laps",
    "show_group",
    "show_place",
    "show_time_shift",
    "stretch",
    "print_dnf",
    "print_dns",
    "print_dsq",
    "disable_dnf",
    "disable_dsq",
    "use_file_logger",
    "use_interface_logger",
    "errors_warnings_only",
    "check_laps_difference",
    "use_start_check_list",
    "show_additional_info",
    "auto_refresh_enabled",
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _load_cfg() -> RaceConfig:
    """Load RaceConfig from fpg_info.txt, mirroring MainWindow production loading.

    C++ format: reset optional boolean flags to False first (absent tag = OFF),
    then apply dict, then load the HTML styles template.
    """
    d = load_config_file(_CONFIG_PATH)
    cfg = RaceConfig()

    for flag in _CPP_RESET_FLAGS:
        setattr(cfg, flag, False)
    cfg.auto_refresh_interval = 0

    for k, v in d.items():
        if not hasattr(cfg, k):
            continue
        field_type = type(getattr(cfg, k))
        if field_type is bool:
            setattr(cfg, k, v == "1")
        elif field_type is int:
            try:
                setattr(cfg, k, int(v))
            except ValueError:
                pass
        elif field_type is float:
            try:
                setattr(cfg, k, float(v))
            except ValueError:
                pass
        else:
            setattr(cfg, k, v)

    st = load_template(cfg.template_file) if cfg.template_file else None
    cfg.styles = st if st is not None else HtmlStyles()
    return cfg


def _run_pipeline(cfg: RaceConfig) -> tuple[list, list, list]:
    """Return (protocol, sorted_abs, groups) from example data files."""
    starts = read_start_protocol(
        cfg.start_protocol_file, skip_first_lap=cfg.skip_first_lap_effective()
    )
    groups = read_group_times(cfg.group_time_file)
    results = read_finish_times(cfg.finish_time_file)
    protocol = calculate_protocol(starts, groups, results, [], [], cfg, [])
    sorted_abs = generate_sorted_protocol(protocol, cfg, 0)
    return protocol, sorted_abs, groups


# ---------------------------------------------------------------------------
# config loading
# ---------------------------------------------------------------------------


class TestExampleConfig:
    def test_race_type(self) -> None:
        cfg = _load_cfg()
        assert cfg.race_type == RACE_TYPE_MASS_SPLITTED

    def test_race_name(self) -> None:
        cfg = _load_cfg()
        assert cfg.race_name == _RACE_NAME

    def test_file_paths(self) -> None:
        cfg = _load_cfg()
        assert cfg.start_protocol_file == _START_PATH
        assert cfg.group_time_file == _GROUPS_PATH
        assert cfg.finish_time_file == _RESULTS_PATH

    def test_custom_weather_label(self) -> None:
        cfg = _load_cfg()
        assert cfg.weather_label == _WEATHER_LABEL

    def test_custom_track_label(self) -> None:
        cfg = _load_cfg()
        assert cfg.track_conditions_label == _TRACK_LABEL

    def test_custom_organizer_label(self) -> None:
        cfg = _load_cfg()
        assert cfg.organizer_label == _ORGANIZER_LABEL

    def test_custom_overall_results_label(self) -> None:
        cfg = _load_cfg()
        assert cfg.overall_results_label == _OVERALL_LABEL

    def test_show_flags_on(self) -> None:
        # Flags present in fpg_info.txt must be True after reset-then-load.
        cfg = _load_cfg()
        assert cfg.show_id is True
        assert cfg.show_name is True
        assert cfg.show_lap_times is True
        assert cfg.show_finish_time is True
        assert cfg.show_time_difference is True
        assert cfg.show_group is True
        assert cfg.show_place is True
        assert cfg.print_dnf is True

    def test_show_flags_off_after_reset(self) -> None:
        # Flags absent from fpg_info.txt must stay False (reset semantics).
        cfg = _load_cfg()
        assert cfg.show_time_shift is False
        assert cfg.show_n_finished_laps is False
        assert cfg.disable_dnf is False
        assert cfg.use_file_logger is False

    def test_skip_first_lap_false_for_mass_splitted(self) -> None:
        cfg = _load_cfg()
        assert cfg.skip_first_lap_effective() is False

    def test_template_styles_loaded(self) -> None:
        # Template file must be loaded: table_style should be non-default.
        cfg = _load_cfg()
        assert cfg.styles.table_style != HtmlStyles().table_style


# ---------------------------------------------------------------------------
# data file loading
# ---------------------------------------------------------------------------


class TestExampleDataFiles:
    def test_start_protocol_count(self) -> None:
        starts = read_start_protocol(_START_PATH)
        assert len(starts) == 120

    def test_groups_count(self) -> None:
        groups = read_group_times(_GROUPS_PATH)
        assert len(groups) == 8

    def test_results_count(self) -> None:
        results = read_finish_times(_RESULTS_PATH)
        assert len(results) == 201

    def test_group_ids_non_empty(self) -> None:
        groups = read_group_times(_GROUPS_PATH)
        assert all(g.group_id for g in groups)

    def test_start_protocol_winner_present(self) -> None:
        # Winner bib 26 must be in the start protocol.
        starts = read_start_protocol(_START_PATH)
        assert any(s.competitor_id == _WINNER_BIB for s in starts)

    def test_start_txt_is_cp1251_not_utf8(self) -> None:
        # Verify the fixture file is genuinely cp1251-encoded (not UTF-8),
        # so that the encoding-fallback path in _read_lines is exercised.
        raw = Path(_START_PATH).read_bytes()
        try:
            raw.decode("utf-8")
            raise AssertionError("start.txt decoded as UTF-8; fixture encoding changed")
        except UnicodeDecodeError:
            pass  # expected: file is cp1251, not utf-8
        # Must still load correctly via the cp1251 fallback
        starts = read_start_protocol(_START_PATH)
        assert len(starts) == 120

    def test_start_protocol_encoding(self) -> None:
        # cp1251 data loads without error and winner name is present.
        starts = read_start_protocol(_START_PATH)
        names = [s.name for s in starts]
        assert any(_WINNER_NAME in n for n in names)


# ---------------------------------------------------------------------------
# pipeline
# ---------------------------------------------------------------------------


class TestExampleDataPipeline:
    def test_total_competitors(self) -> None:
        cfg = _load_cfg()
        protocol, _, _ = _run_pipeline(cfg)
        assert len(protocol) == 120

    def test_finished_count(self) -> None:
        cfg = _load_cfg()
        protocol, _, _ = _run_pipeline(cfg)
        finished = sum(
            1
            for c in protocol
            if c.finished and not c.disqualified and c.get_total_time() < INF
        )
        assert finished == 113

    def test_dnf_count(self) -> None:
        cfg = _load_cfg()
        protocol, _, _ = _run_pipeline(cfg)
        dnf = sum(1 for c in protocol if not c.finished and not c.disqualified)
        assert dnf == 7

    def test_dsq_count(self) -> None:
        cfg = _load_cfg()
        protocol, _, _ = _run_pipeline(cfg)
        assert sum(1 for c in protocol if c.disqualified) == 0

    def test_winner_bib(self) -> None:
        cfg = _load_cfg()
        _, sorted_abs, _ = _run_pipeline(cfg)
        assert sorted_abs[0].competitor_id == _WINNER_BIB

    def test_winner_name(self) -> None:
        cfg = _load_cfg()
        _, sorted_abs, _ = _run_pipeline(cfg)
        assert sorted_abs[0].name == _WINNER_NAME

    def test_sorted_absolute_count(self) -> None:
        cfg = _load_cfg()
        _, sorted_abs, _ = _run_pipeline(cfg)
        assert len(sorted_abs) == 120


# ---------------------------------------------------------------------------
# HTML generation - golden file comparison
# ---------------------------------------------------------------------------


class TestExampleDataHtml:
    @pytest.fixture()
    def html_outputs(self) -> tuple[str, str]:
        cfg = _load_cfg()
        _, sorted_abs, groups = _run_pipeline(cfg)
        with tempfile.TemporaryDirectory() as td:
            grp_path = str(Path(td) / "grp.html")
            abs_path = str(Path(td) / "abs.html")
            write_group_protocol(grp_path, sorted_abs, groups, cfg)
            write_absolute_protocol(abs_path, sorted_abs, groups, cfg)
            grp_html = Path(grp_path).read_text(encoding="utf-8")
            abs_html = Path(abs_path).read_text(encoding="utf-8")
        return grp_html, abs_html

    def test_group_protocol_matches_golden(self, html_outputs: tuple) -> None:
        grp_html, _ = html_outputs
        golden = Path(_GOLDEN_GRP).read_text(encoding="utf-8")
        assert grp_html == golden

    def test_absolute_protocol_matches_golden(self, html_outputs: tuple) -> None:
        _, abs_html = html_outputs
        golden = Path(_GOLDEN_ABS).read_text(encoding="utf-8")
        assert abs_html == golden

    def test_group_protocol_ends_with_newline(self, html_outputs: tuple) -> None:
        grp_html, _ = html_outputs
        assert grp_html.endswith("\n")

    def test_absolute_protocol_ends_with_newline(self, html_outputs: tuple) -> None:
        _, abs_html = html_outputs
        assert abs_html.endswith("\n")

    def test_race_name_in_group_protocol(self, html_outputs: tuple) -> None:
        grp_html, _ = html_outputs
        assert _RACE_NAME in grp_html

    def test_race_name_in_absolute_protocol(self, html_outputs: tuple) -> None:
        _, abs_html = html_outputs
        assert _RACE_NAME in abs_html

    def test_weather_label_in_group_protocol(self, html_outputs: tuple) -> None:
        grp_html, _ = html_outputs
        assert _WEATHER_LABEL in grp_html

    def test_organizer_label_in_group_protocol(self, html_outputs: tuple) -> None:
        grp_html, _ = html_outputs
        assert _ORGANIZER_LABEL in grp_html

    def test_track_label_in_group_protocol(self, html_outputs: tuple) -> None:
        grp_html, _ = html_outputs
        assert _TRACK_LABEL in grp_html

    def test_overall_results_label_in_absolute_protocol(
        self, html_outputs: tuple
    ) -> None:
        _, abs_html = html_outputs
        assert _OVERALL_LABEL in abs_html

    def test_all_groups_in_group_protocol(self, html_outputs: tuple) -> None:
        grp_html, _ = html_outputs
        groups = read_group_times(_GROUPS_PATH)
        for g in groups:
            assert g.group_id in grp_html, f"group {g.group_id!r} missing"

    def test_all_groups_in_absolute_protocol(self, html_outputs: tuple) -> None:
        _, abs_html = html_outputs
        groups = read_group_times(_GROUPS_PATH)
        for g in groups:
            assert g.group_id in abs_html, f"group {g.group_id!r} missing"

    def test_winner_in_absolute_protocol(self, html_outputs: tuple) -> None:
        _, abs_html = html_outputs
        assert _WINNER_NAME in abs_html
