"""The protocol document says all the HTML protocol says, in the site's schema."""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path

import jsonschema
import pytest
from protocol_scenarios import SCENARIOS, Race

from app.html_writer import write_absolute_protocol, write_group_protocol
from app.protocol_document import build_absolute_document, build_group_document

SCHEMA = json.loads(
    (Path(__file__).parent / "fixtures" / "protocol-document-v1.json").read_text()
)
HEADER_STYLE = "header-row-marker"
_MAX_CELLS = 100_000


def check_document_rules(document: dict) -> None:
    """What the site checks beyond the JSON Schema: ids, references and the budget."""
    groups = [g["id"] for g in document.get("groups", [])]
    toggles = [t["id"] for t in document.get("toggles", [])]
    assert len(groups) == len(set(groups)), "group ids are unique"
    assert len(toggles) == len(set(toggles)), "toggle ids are unique"
    assert "" not in groups
    cells = 0
    for section in document["sections"]:
        ids = [c["id"] for c in section["columns"]]
        assert len(ids) == len(set(ids)), "column ids are unique"
        for column in section["columns"]:
            assert column.get("toggle") in (None, *toggles)
        assert section.get("group") in (None, *groups)
        for row in section["rows"]:
            assert set(row["cells"]) <= set(ids)
            assert row.get("group") in (None, *groups)
        cells += len(ids) * len(section["rows"])
        cells += sum(1 for row in section["rows"] if row.get("note"))
    assert cells <= _MAX_CELLS


def _documents(race: Race) -> dict[str, dict]:
    return {
        "group": build_group_document(
            race.protocol, race.groups, race.cfg, race.n_points
        ),
        "absolute": build_absolute_document(
            race.protocol, race.groups, race.cfg, race.n_points
        ),
    }


class _Tables(HTMLParser):
    """The text of every data cell of every table, split where the HTML breaks lines."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[str]] = []
        self._header = False
        self._cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.tables.append([])
        elif tag == "tr":
            self._header = dict(attrs).get("style") == HEADER_STYLE
        elif tag == "td" and not self._header:
            self._cell = [""]
        elif tag == "br" and self._cell is not None:
            self._cell.append("")

    def handle_endtag(self, tag):
        if tag == "td" and self._cell is not None:
            self.tables[-1].extend(part for part in self._cell if part.strip())
            self._cell = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell[-1] += data


def _tokens(texts: list[str]) -> list[str]:
    """Words and numbers, ignoring how the parts of a cell are glued or bracketed."""
    out: list[str] = []
    for text in texts:
        out.extend(re.findall(r"[^\s()]+", text.replace("\xa0", " ")))
    return sorted(out)


def _document_texts(section: dict) -> list[str]:
    texts = []
    for row in section["rows"]:
        for cell in row["cells"].values():
            if isinstance(cell, str):
                texts.append(cell)
            else:
                texts.append(cell["text"])
                texts.extend(cell.get("sub", []))
        if row.get("note"):
            texts.extend(row["note"].split("\n"))
    return texts


def _html_tables(race: Race, kind: str, tmp_path: Path) -> tuple[list[list[str]], str]:
    race.cfg.styles.top_line_style = HEADER_STYLE
    path = tmp_path / f"{kind}.html"
    writer = write_group_protocol if kind == "group" else write_absolute_protocol
    writer(str(path), race.protocol, race.groups, race.cfg, race.n_points)
    text = path.read_text(encoding="utf-8")
    parser = _Tables()
    parser.feed(text)
    return parser.tables, text


@pytest.mark.parametrize("name", sorted(SCENARIOS))
@pytest.mark.parametrize("kind", ["group", "absolute"])
def test_document_matches_the_schema_and_the_sites_rules(name, kind):
    document = _documents(SCENARIOS[name]())[kind]
    jsonschema.validate(document, SCHEMA)
    check_document_rules(document)


@pytest.mark.parametrize("name", sorted(SCENARIOS))
@pytest.mark.parametrize("kind", ["group", "absolute"])
def test_document_holds_every_value_the_html_shows(name, kind, tmp_path):
    race = SCENARIOS[name]()
    tables, _ = _html_tables(race, kind, tmp_path)
    document = _documents(SCENARIOS[name]())[kind]
    assert len(tables) == len(document["sections"])
    for html_cells, section in zip(tables, document["sections"], strict=True):
        assert _tokens(html_cells) == _tokens(_document_texts(section)), section.get(
            "title"
        )


@pytest.mark.parametrize("name", sorted(SCENARIOS))
@pytest.mark.parametrize("kind", ["group", "absolute"])
def test_switches_exist_exactly_where_the_html_has_buttons(name, kind, tmp_path):
    race = SCENARIOS[name]()
    _, text = _html_tables(race, kind, tmp_path)
    toggles = {t["id"]: t for t in _documents(SCENARIOS[name]())[kind]["toggles"]}
    assert ("splits" in toggles) == ("'Lap " in text)
    assert ("lap_stats" in toggles) == ("'Additional " in text)
    assert all(t["default"] is True for t in toggles.values())


def test_splits_without_buttons_have_no_switch_and_stay_visible():
    document = _documents(SCENARIOS["mass_points_no_buttons"]())["group"]
    splits = [c for c in document["sections"][0]["columns"] if "_s" in c["id"]]
    assert splits
    assert all("toggle" not in c for c in splits)
    assert document["toggles"] == []


def test_lap_statistics_carry_both_pairs_with_show_lap_finish():
    document = _documents(SCENARIOS["mass_lap_stats"]())["group"]
    ids = [c["id"] for c in document["sections"][0]["columns"]]
    assert "lap1_rank" in ids and "lap1_finish_rank" in ids
    without = _documents(SCENARIOS["mass_lap_stats_no_finish"]())["group"]
    assert "lap1_finish_rank" not in [
        c["id"] for c in without["sections"][0]["columns"]
    ]


def test_tries_mark_counted_attempts_and_list_their_penalties():
    document = _documents(SCENARIOS["tries_asc"]())["group"]
    rows = [r for s in document["sections"] for r in s["rows"]]
    boris = next(r for r in rows if r["cells"].get("name") == "Boris Tries")
    attempt2 = boris["cells"]["lap2"]
    assert attempt2["sub"] == ["Gate <7> & flag:5sec"]
    strong = [
        k for k, v in boris["cells"].items() if isinstance(v, dict) and v.get("strong")
    ]
    assert len(strong) == 1


def test_tries_closed_attempt_without_finish_says_dnf():
    document = _documents(SCENARIOS["tries_asc"]())["group"]
    rows = [r for s in document["sections"] for r in s["rows"]]
    vera = next(r for r in rows if r["cells"].get("name") == "Vera Tries")
    assert vera["cells"]["lap2"] == "DNF"


def test_disqualification_reasons_become_a_note():
    document = _documents(SCENARIOS["mass_print_all"]())["absolute"]
    gleb = next(
        r for r in document["sections"][0]["rows"] if r["cells"]["name"] == "Gleb Orlov"
    )
    assert gleb["status"] == "dsq"
    assert gleb["cells"]["place"] == "DSQ"
    assert "cut the course" in gleb["note"]
    assert "result" not in gleb["cells"]


def test_custom_start_shows_the_first_crossing_or_not_started():
    document = _documents(SCENARIOS["custom_basic"]())["group"]
    rows = {r["cells"]["name"]: r for s in document["sections"] for r in s["rows"]}
    assert rows["Vera Never"]["cells"]["start"] == "NOT STARTED"
    assert rows["Vera Never"]["status"] == "dns"
    assert rows["Anna Custom"]["cells"]["start"].startswith("1970-01-04 ")


def test_relay_number_lists_every_member():
    document = _documents(SCENARIOS["mass_relay"]())["group"]
    bib = document["sections"][0]["rows"][0]["cells"]["bib"]
    assert bib["sub"] and bib["text"] in ("10", "20")


def test_absolute_rows_carry_their_group_even_without_a_group_column():
    race = SCENARIOS["mass_basic"]()
    race.cfg.show_group = False
    document = _documents(race)["absolute"]
    assert [g["id"] for g in document["groups"]] == ["W30", "M40"]
    assert "group" not in [c["id"] for c in document["sections"][0]["columns"]]
    assert {r["group"] for r in document["sections"][0]["rows"]} == {"W30", "M40"}


def test_header_and_footer_carry_the_race_info():
    document = _documents(SCENARIOS["mass_basic"]())["group"]
    keys = [i.get("key") for i in document["header"]]
    assert keys == [None, None, "track", "weather"]
    assert document["header"][0] == {
        "type": "html",
        "html": '<a href="https://example.com/sponsor">Sponsor</a>',
    }
    assert [i.get("key") for i in document["footer"]] == [
        "organizer",
        "referee",
        "secretary",
        None,
    ]
    assert document["title"] == "Scenario race"
    assert document["generator"]["name"] == "FinishProtocolGenerator"


def test_label_markup_becomes_plain_text():
    race = SCENARIOS["mass_points_buttons"]()
    document = _documents(race)["group"]
    assert document["toggles"][0]["label"] == "Show/Hide CP Splits By Lap"


def test_language_is_sent_only_when_set():
    race = SCENARIOS["mass_basic"]()
    assert "lang" not in _documents(race)["group"]
    race.cfg.protocol_language = "ru"
    assert _documents(race)["group"]["lang"] == "ru"


def test_building_the_document_leaves_the_html_unchanged(tmp_path):
    race = SCENARIOS["example_race"]()
    path = tmp_path / "abs.html"
    _documents(race)
    write_absolute_protocol(
        str(path), race.protocol, race.groups, race.cfg, race.n_points
    )
    golden = (
        Path(__file__).parent / "fixtures" / "golden" / "example_race.absolute.html"
    )
    assert path.read_text(encoding="utf-8") == golden.read_text(encoding="utf-8")


def test_a_lap_is_grouped_only_when_it_has_several_columns():
    plain = _documents(SCENARIOS["mass_basic"]())["group"]["sections"][0]["columns"]
    assert all("group" not in c for c in plain)
    split = _documents(SCENARIOS["mass_points_buttons"]())["group"]["sections"][0]
    lap1 = [c for c in split["columns"] if c["id"].startswith("lap1")]
    assert len(lap1) > 1 and {c["group"] for c in lap1} == {"Lap 1"}


def _race_with_groups(*group_names: str) -> Race:
    from protocol_scenarios import _cfg, _mark, _run

    cfg = _cfg()
    starts = [
        f"{i}#Rider {i}#{name}#1#1#1990####" for i, name in enumerate(group_names, 1)
    ]
    groups = [(name, 100) for name in dict.fromkeys(group_names)]
    finishes = [_mark(i, 200 + i * 10) for i in range(1, len(group_names) + 1)]
    return _run(cfg, starts, groups, finishes)


@pytest.mark.parametrize("kind", ["group", "absolute"])
def test_a_rider_without_a_group_gives_a_valid_document(kind):
    document = _documents(_race_with_groups("", "M30"))[kind]
    jsonschema.validate(document, SCHEMA)
    check_document_rules(document)
    rows = [r for s in document["sections"] for r in s["rows"]]
    no_group = next(r for r in rows if r["cells"]["name"] == "Rider 1")
    assert "group" not in no_group


@pytest.mark.parametrize("kind", ["group", "absolute"])
def test_long_group_names_with_one_beginning_stay_two_groups(kind):
    first, second = "A" * 100 + "1", "A" * 100 + "2"
    document = _documents(_race_with_groups(first, second))[kind]
    jsonschema.validate(document, SCHEMA)
    check_document_rules(document)
    ids = [g["id"] for g in document["groups"]]
    assert len(ids) == len(set(ids)) == 2
    assert all(len(i) <= 100 for i in ids)
    assert [g["label"] for g in document["groups"]] == [first, second]
    rows = [r for s in document["sections"] for r in s["rows"]]
    if kind == "absolute":
        assert {r["group"] for r in rows} == set(ids)
    else:
        assert [s["group"] for s in document["sections"]] == ids


def test_group_ids_stay_the_same_from_run_to_run():
    long_name = "B" * 150
    once = _documents(_race_with_groups(long_name))["group"]["groups"]
    again = _documents(_race_with_groups(long_name))["group"]["groups"]
    assert once == again


def test_lap_ranks_are_not_computed_when_they_are_not_shown(monkeypatch):
    import app.protocol_document as builder

    calls = []
    real = builder.lap_ranks
    monkeypatch.setattr(builder, "lap_ranks", lambda *a: calls.append(1) or real(*a))
    _documents(SCENARIOS["mass_basic"]())
    assert calls == []
    _documents(SCENARIOS["mass_lap_stats"]())
    assert calls
