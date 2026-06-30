"""Settings / configuration for one protocol-generation run."""

from __future__ import annotations

from dataclasses import dataclass, field

RACE_TYPE_MASS_SPLITTED = "Mass/Splitted"
RACE_TYPE_ELIMINATOR_QUALIFICATION = "Eliminator Qualification"
RACE_TYPE_ELIMINATOR_FINALS = "Eliminator Finals"
RACE_TYPE_CUSTOM_START = "Custom Start"
RACE_TYPE_NUMBER_OF_TRIES = "Number of Tries"
RACE_TYPE_SPIRIDONOV = "Mass/Splitted (Spiridonov)"

ALL_RACE_TYPES = [
    RACE_TYPE_MASS_SPLITTED,
    RACE_TYPE_CUSTOM_START,
    RACE_TYPE_ELIMINATOR_QUALIFICATION,
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
    upload_http_groups: bool = False
    upload_http_absolute: bool = False
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

    def use_spiridonov_coefficients(self) -> bool:
        return self.race_type == RACE_TYPE_SPIRIDONOV

    def generate_text_protocol_effective(self) -> bool:
        return self.race_type == RACE_TYPE_ELIMINATOR_QUALIFICATION

    def skip_first_lap_effective(self) -> bool:
        return self.is_number_of_tries() or self.race_type == RACE_TYPE_CUSTOM_START
