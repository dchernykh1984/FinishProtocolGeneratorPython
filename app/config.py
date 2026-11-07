"""Settings / configuration for one protocol-generation run."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.paths import app_path


def _same_file_key(path: str) -> str:
    """A comparable form of a configured path, so two settings naming one file match
    however each was typed.

    Resolved exactly the way the writers resolve it: through ``app_path``, so a
    relative path hangs off the program's own folder. Without that, the shipped
    ``data/start.txt`` and the absolute path a file picker hands back would look like
    two different files, which is the pair a referee is most likely to produce.

    No ``expanduser`` here on purpose: the writers do not expand ``~`` either, so
    expanding it would compare one file and write another.
    """
    text = path.strip()
    if not text:
        return ""
    try:
        return str(app_path(text).resolve())
    except OSError, ValueError, RuntimeError:
        # A path the system cannot even name -- a stray null byte, an unknown ~user.
        # No clash can be proved against it; writing to it fails later, and that is
        # reported where the writing is attempted.
        return ""


# The section of protocols every event has on the site: a protocol that names no section
# goes there, and so does everything a config saved before sections publishes.
FIRST_SECTION = 1
# The largest section number the site can hold (its column's range).
LAST_SECTION = 2_147_483_647

RACE_TYPE_MASS_SPLITTED = "Mass/Splitted"
#: No longer a race type: qualifying is an ordinary race, and the seeding export it
#: used to carry is now a setting of its own. Kept so an old config can be migrated.
LEGACY_RACE_TYPE_QUALIFICATION = "Eliminator Qualification"
RACE_TYPE_ELIMINATOR_FINALS = "Eliminator Finals"
RACE_TYPE_CUSTOM_START = "Custom Start"
RACE_TYPE_NUMBER_OF_TRIES = "Number of Tries"
RACE_TYPE_SPIRIDONOV = "Mass/Splitted (Spiridonov)"

ALL_RACE_TYPES = [
    RACE_TYPE_MASS_SPLITTED,
    RACE_TYPE_CUSTOM_START,
    RACE_TYPE_ELIMINATOR_FINALS,
    RACE_TYPE_NUMBER_OF_TRIES,
    RACE_TYPE_SPIRIDONOV,
]

# Where each input stream comes from: the local file as-is, or fetched from the cycling
# site (all devices merged) by competition token. Mirrors the FTP action dropdowns.
START_LIST_SOURCE_LOCAL = "Use local data"
START_LIST_SOURCE_SITE = "Get data from site"
START_LIST_SOURCES = (START_LIST_SOURCE_LOCAL, START_LIST_SOURCE_SITE)
# The group/finish/remote timing streams use the same two options.
TIMING_SOURCE_SITE = START_LIST_SOURCE_SITE
TIMING_SOURCES = START_LIST_SOURCES

# Per-protocol HTTP action performed after a protocol is generated: leave the site
# untouched, publish the freshly generated protocol, or remove it from the site.
HTTP_ACTION_NOTHING = "Nothing"
HTTP_ACTION_UPLOAD = "Upload"
HTTP_ACTION_DELETE = "Delete"
HTTP_ACTIONS = (HTTP_ACTION_NOTHING, HTTP_ACTION_UPLOAD, HTTP_ACTION_DELETE)


# How a protocol is sent to the site: the HTML as written, the structured document the
# site draws itself (app/protocol_document.py), or both from one run -- the site then
# shows the document and keeps the HTML as the original.
PROTOCOL_FORMAT_HTML = "HTML"
PROTOCOL_FORMAT_DATA = "Data"
PROTOCOL_FORMAT_BOTH = "HTML + Data"
PROTOCOL_FORMATS = (PROTOCOL_FORMAT_BOTH, PROTOCOL_FORMAT_HTML, PROTOCOL_FORMAT_DATA)


def normalize_protocol_format(value: str) -> str:
    """A saved format, or both when it is unknown (a typo in a hand-edited file)."""
    return value if value in PROTOCOL_FORMATS else PROTOCOL_FORMAT_BOTH


def normalize_http_action(value: str) -> str:
    """Coerce an HTTP action to a known value; anything unrecognised becomes Nothing.

    Actions come from user-edited config files, so a typo or corrupt value must fall
    back to the safe default rather than silently deleting a protocol from the site.
    """
    return value if value in HTTP_ACTIONS else HTTP_ACTION_NOTHING


def migrate_http_actions(groups_on: bool, absolute_on: bool) -> tuple[str, str]:
    """Map the legacy pair of upload booleans to the new per-protocol actions.

    Old semantics: with neither box checked nothing happened; otherwise the checked
    protocol was uploaded and the unchecked one deleted from the site.
    """
    if not groups_on and not absolute_on:
        return HTTP_ACTION_NOTHING, HTTP_ACTION_NOTHING
    return (
        HTTP_ACTION_UPLOAD if groups_on else HTTP_ACTION_DELETE,
        HTTP_ACTION_UPLOAD if absolute_on else HTTP_ACTION_DELETE,
    )


@dataclass
class HtmlStyles:
    table_style: str = ""
    top_line_style: str = "background-color: rgb(175, 175, 175)"
    even_line_style: str = "background-color: rgb(215, 215, 215)"
    odd_line_style: str = "background-color: rgb(175, 175, 175)"
    group_name_style: str = '<FONT SIZE="4" COLOR="#FF0066">'
    additional_text_top_style: str = '<FONT SIZE="2" COLOR="#339900">'
    additional_text_style: str = '<FONT SIZE="2" COLOR="#339900">'
    top_text_style: str = '<FONT SIZE="4" COLOR="">'
    additional_info_top_style: str = '<FONT COLOR="#339900">'
    additional_info_style: str = '<FONT COLOR="#339900">'
    common_style_text: str = ""


@dataclass
class RaceConfig:
    race_type: str = RACE_TYPE_MASS_SPLITTED
    attempt_rules_json: str = "[]"
    #: Write the finishing order as a start protocol seeded by place, for the ladder
    #: of an Eliminator Finals round to read. Independent of how the race is scored.
    write_seeding_protocol: bool = False
    #: Where that file goes. Empty keeps the old place, beside the group protocol.
    seeding_protocol_file: str = ""

    start_protocol_file: str = "start.txt"
    group_time_file: str = "groups.txt"
    finish_time_file: str = "results.txt"
    group_protocol_file: str = "gr.html"
    absolute_protocol_file: str = "abs.html"
    template_file: str = "template.html"

    race_name: str = ""
    race_date: str = ""
    race_place: str = ""
    weather: str = ""
    main_referee: str = ""
    additional_referee: str = ""
    organizer: str = ""
    track_conditions: str = ""
    sponsor: str = ""
    bottom_text: str = ""
    referee_label: str = "Referee"
    secretary_label: str = "Secretary"
    weather_label: str = "Weather"
    track_conditions_label: str = "Track"
    overall_results_label: str = "Overall results"
    organizer_label: str = "Organizer"

    n_signs_after_point: int = 1
    minimal_time_for_lap: int = 0
    time_limit: int = 0
    n_remote_points: int = 0
    remote_points_path: str = ""
    start_check_list_file: str = ""
    auto_refresh_interval: int = 0
    auto_refresh_enabled: bool = False
    start_registration_period: float = 0.0
    laps_difference_pct: int = 0

    lap_name: str = "Lap"
    lap_additional_info: str = "Lap finish time"

    show_place: bool = True
    show_id: bool = True
    show_name: bool = True
    show_age: bool = True
    show_team: bool = True
    show_city: bool = True
    show_group: bool = True
    show_lap_times: bool = True
    show_finish_time: bool = True
    finish_time_label: str = "Time"
    show_time_difference: bool = True
    time_difference_label: str = "(gap)"
    show_additional_info: bool = False
    show_time_shift: bool = False
    show_n_finished_laps: bool = False
    n_finished_laps_label: str = "(laps)"
    show_lap_finish: bool = False
    hide_empty_columns: bool = False
    stretch: bool = False
    use_buttons: bool = False
    use_buttons_label: str = "Show/Hide<BR>CP Splits<BR>By Lap"
    use_all_buttons: bool = False
    use_all_buttons_label: str = "Show/Hide<BR>Additional Statistics<BR>By Lap"
    lap_rank_label: str = ""
    lap_finish_rank_label: str = ""
    merge_by_id: bool = False
    upload_groups: bool = False
    upload_absolute: bool = False
    ftp_path: str = ""
    ftp_login: str = ""
    ftp_password: str = ""
    http_site_url: str = ""
    http_upload_token: str = ""
    http_is_live: bool = True
    http_stage_label: str = ""
    # The section of the event's protocols on the site to publish into: the first, the
    # event's own, unless the organizer added another there and gave its number.
    http_section: int = FIRST_SECTION
    # Language of the protocol's labels (e.g. "ru"), told to the site with the document.
    protocol_language: str = ""
    http_protocol_format: str = PROTOCOL_FORMAT_BOTH
    http_groups_action: str = HTTP_ACTION_NOTHING
    http_absolute_action: str = HTTP_ACTION_NOTHING
    # Push per-competitor live standings (for the Garmin field) on each regeneration.
    send_group_statistics: bool = False
    send_absolute_statistics: bool = False
    pack_gap_seconds: int = 10
    start_list_source: str = START_LIST_SOURCE_LOCAL
    group_times_source: str = START_LIST_SOURCE_LOCAL
    finish_times_source: str = START_LIST_SOURCE_LOCAL
    remote_points_source: str = START_LIST_SOURCE_LOCAL
    start_list_action: str = "None"
    group_times_action: str = "None"
    result_times_action: str = "None"
    remote_points_action: str = "None"
    use_start_check_list: bool = False
    start_check_list_action: str = "None"
    check_laps_difference: bool = False

    print_dnf: bool = True
    print_dns: bool = False
    print_dsq: bool = False
    disable_dnf: bool = False
    disable_dsq: bool = False

    use_interface_logger: bool = True
    use_file_logger: bool = False
    errors_warnings_only: bool = False

    place_label: str = "Place"
    id_label: str = "Number"
    name_label: str = "Name"
    age_label: str = "Year of birth"
    team_label: str = "Team"
    city_label: str = "City"
    group_label: str = "Group"
    time_shift_label: str = "Start time"
    additional_info_label: str = "Additional info"

    styles: HtmlStyles = field(default_factory=HtmlStyles)

    def is_eliminator_finals(self) -> bool:
        return self.race_type == RACE_TYPE_ELIMINATOR_FINALS

    def is_number_of_tries(self) -> bool:
        return self.race_type == RACE_TYPE_NUMBER_OF_TRIES

    def intermediate_point_count(self, remote_count: int) -> int:
        """Exclude the separate finish stream from attempt split columns."""
        return remote_count - (1 if self.is_number_of_tries() and remote_count else 0)

    def use_spiridonov_coefficients(self) -> bool:
        return self.race_type == RACE_TYPE_SPIRIDONOV

    def generate_text_protocol_effective(self) -> bool:
        """Whether this run writes a seeding protocol for the finals.

        A finals round has no places of its own to seed from, so the setting is
        ignored there however it was left.
        """
        return self.write_seeding_protocol and not self.is_eliminator_finals()

    def seeding_protocol_path(self, group_protocol_file: str) -> str:
        """Where the seeding protocol goes.

        Empty keeps where the C++ generator put it -- beside the group protocol with
        a .txt suffix -- so a setup that predates the path field is unaffected.
        """
        return self.seeding_protocol_file or group_protocol_file + ".txt"

    def seeding_protocol_conflict(self, group_protocol_file: str) -> str:
        """The setting whose file the seeding protocol would overwrite, or "".

        The field asks for a start protocol, so pointing it at the start protocol of
        the race being run is an easy slip -- and it would replace the start list
        with a finishing order in the middle of an event.
        """
        target = _same_file_key(self.seeding_protocol_path(group_protocol_file))
        if not target:
            return ""
        guarded = (
            ("start protocol", self.start_protocol_file),
            ("group times", self.group_time_file),
            ("finish times", self.finish_time_file),
            ("start check list", self.start_check_list_file),
            ("group protocol", group_protocol_file),
            ("absolute protocol", self.absolute_protocol_file),
            ("HTML styles template", self.template_file),
        )
        for label, other in guarded:
            if other and _same_file_key(other) == target:
                return label
        return ""

    def skip_first_lap_effective(self) -> bool:
        return self.is_number_of_tries() or self.race_type == RACE_TYPE_CUSTOM_START
