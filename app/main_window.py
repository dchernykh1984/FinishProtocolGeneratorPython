"""PySide6 main window for Finish Protocol Generator."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.calculator import (
    calculate_protocol,
    check_start_protocol,
    generate_sorted_protocol,
)
from app.config import (
    ALL_RACE_TYPES,
    START_LIST_SOURCE_SITE,
    START_LIST_SOURCES,
    TIMING_SOURCE_SITE,
    TIMING_SOURCES,
    HtmlStyles,
    RaceConfig,
)
from app.file_io import (
    load_config_file,
    load_template,
    read_finish_times,
    read_group_times,
    read_start_protocol,
)
from app.ftp_io import DOWNLOAD_ACTIONS, download_file, upload_file
from app.html_writer import write_absolute_protocol, write_group_protocol
from app.http_io import (
    fetch_finish_times,
    fetch_group_times,
    fetch_remote_points,
    fetch_start_list,
)
from app.http_io import upload_protocol as http_upload_protocol
from app.models import GroupStartElement


class _FTPWorker(QThread):
    log_message = Signal(str)
    finished_ok = Signal()
    finished_with_errors = Signal()
    error = Signal(str)

    def __init__(self, cfg: RaceConfig) -> None:
        super().__init__()
        self._cfg = cfg

    def run(self) -> None:
        cfg = self._cfg
        failed = self._fetch_sources_from_site(cfg)

        scl_action = cfg.start_check_list_action if cfg.use_start_check_list else "None"
        tasks = [
            ("Remote points", cfg.remote_points_action, False),
            ("Start list", cfg.start_list_action, cfg.merge_by_id),
            ("Group times", cfg.group_times_action, False),
            ("Finish times", cfg.result_times_action, False),
            ("Start check list", scl_action, False),
        ]

        for label, action, by_id in tasks:
            if action not in ("Download", "Merge", "Merge+Remove"):
                continue
            merge = action in ("Merge", "Merge+Remove")
            remove = action == "Merge+Remove"

            if label == "Remote points":
                if not cfg.n_remote_points or not cfg.remote_points_path:
                    continue
                for i in range(1, cfg.n_remote_points + 1):
                    local = str(Path(cfg.remote_points_path) / f"results_{i}.txt")
                    self.log_message.emit(f"Downloading remote point {i}...")
                    if (
                        download_file(
                            cfg.ftp_path,
                            cfg.ftp_login,
                            cfg.ftp_password,
                            local,
                            merge,
                            remove,
                            by_id,
                        )
                        == -1
                    ):
                        self.log_message.emit(f"  ERROR: remote point {i}")
                        failed = True
                    else:
                        self.log_message.emit(f"  Remote point {i}: OK")
            else:
                local_map = {
                    "Start list": cfg.start_protocol_file,
                    "Group times": cfg.group_time_file,
                    "Finish times": cfg.finish_time_file,
                    "Start check list": cfg.start_check_list_file,
                }
                local = local_map[label]
                self.log_message.emit(f"Downloading {label}...")
                if (
                    download_file(
                        cfg.ftp_path,
                        cfg.ftp_login,
                        cfg.ftp_password,
                        local,
                        merge,
                        remove,
                        by_id,
                    )
                    == -1
                ):
                    self.log_message.emit(f"  ERROR: {label}")
                    failed = True
                else:
                    self.log_message.emit(f"  {label}: OK")

        if failed:
            self.log_message.emit(
                "WARNING: some downloads failed; continuing with local files."
            )
            self.finished_with_errors.emit()
        else:
            self.finished_ok.emit()

    def _fetch_sources_from_site(self, cfg: RaceConfig) -> bool:
        """Fetch each site-sourced stream (start list, group, finish, remote points).

        Returns True if any fetch failed (generation still proceeds with on-disk data).
        """
        failed = False
        if cfg.start_list_source == START_LIST_SOURCE_SITE:
            failed = not self._fetch_start_list_from_site(cfg)
        if cfg.group_times_source == TIMING_SOURCE_SITE:
            failed = (not self._fetch_group_times_from_site(cfg)) or failed
        if cfg.finish_times_source == TIMING_SOURCE_SITE:
            failed = (not self._fetch_finish_times_from_site(cfg)) or failed
        if cfg.remote_points_source == TIMING_SOURCE_SITE:
            failed = (not self._fetch_remote_points_from_site(cfg)) or failed
        return failed

    def _fetch_start_list_from_site(self, cfg: RaceConfig) -> bool:
        """Fetch the merged start list from the site and write it to the start file.

        On any error the local start file is left untouched (not overwritten) and False
        is returned, so generation continues with whatever is already on disk.
        """
        self.log_message.emit("Fetching start list from site...")
        if not cfg.http_site_url or not cfg.http_upload_token:
            self.log_message.emit("  ERROR: site URL and upload token must be set")
            return False
        try:
            lines = fetch_start_list(cfg.http_site_url, cfg.http_upload_token)
        except ValueError as exc:
            self.log_message.emit(f"  ERROR: {exc}")
            return False
        try:
            path = Path(cfg.start_protocol_file)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8"
            )
        except OSError as exc:
            self.log_message.emit(f"  ERROR: cannot write start list: {exc}")
            return False
        self.log_message.emit(f"  Start list: {len(lines)} competitor(s) from site")
        return True

    def _write_lines(self, path: str, lines: list[str], label: str) -> bool:
        """Overwrite *path* with *lines*; on error leave it and return False."""
        try:
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
        except OSError as exc:
            self.log_message.emit(f"  ERROR: cannot write {label}: {exc}")
            return False
        return True

    def _fetch_group_times_from_site(self, cfg: RaceConfig) -> bool:
        self.log_message.emit("Fetching group times from site...")
        if not cfg.http_site_url or not cfg.http_upload_token:
            self.log_message.emit("  ERROR: site URL and upload token must be set")
            return False
        try:
            lines = fetch_group_times(cfg.http_site_url, cfg.http_upload_token)
        except ValueError as exc:
            self.log_message.emit(f"  ERROR: {exc}")
            return False
        if not self._write_lines(cfg.group_time_file, lines, "group times"):
            return False
        self.log_message.emit(f"  Group times: {len(lines)} line(s) from site")
        return True

    def _fetch_finish_times_from_site(self, cfg: RaceConfig) -> bool:
        self.log_message.emit("Fetching finish times from site...")
        if not cfg.http_site_url or not cfg.http_upload_token:
            self.log_message.emit("  ERROR: site URL and upload token must be set")
            return False
        try:
            lines = fetch_finish_times(cfg.http_site_url, cfg.http_upload_token)
        except ValueError as exc:
            self.log_message.emit(f"  ERROR: {exc}")
            return False
        if not self._write_lines(cfg.finish_time_file, lines, "finish times"):
            return False
        self.log_message.emit(f"  Finish times: {len(lines)} line(s) from site")
        return True

    def _fetch_remote_points_from_site(self, cfg: RaceConfig) -> bool:
        """Fetch each remote point to ``<remote_points_path>/results_<n>.txt``."""
        self.log_message.emit("Fetching remote points from site...")
        if not cfg.http_site_url or not cfg.http_upload_token:
            self.log_message.emit("  ERROR: site URL and upload token must be set")
            return False
        if not cfg.n_remote_points or not cfg.remote_points_path:
            self.log_message.emit("  (skipped: control points count / path not set)")
            return True
        try:
            points = fetch_remote_points(cfg.http_site_url, cfg.http_upload_token)
        except ValueError as exc:
            self.log_message.emit(f"  ERROR: {exc}")
            return False
        ok = True
        for i in range(1, cfg.n_remote_points + 1):
            lines = points.get(i, [])
            local = str(Path(cfg.remote_points_path) / f"results_{i}.txt")
            if self._write_lines(local, lines, f"remote point {i}"):
                self.log_message.emit(
                    f"  Remote point {i}: {len(lines)} line(s) from site"
                )
            else:
                ok = False
        return ok


class _GenerateWorker(QThread):
    log_message = Signal(str)
    finished_ok = Signal()
    error = Signal(str)

    def __init__(self, cfg: RaceConfig) -> None:
        super().__init__()
        self._cfg = cfg

    def _do_uploads(self, cfg: RaceConfig) -> tuple[bool, list[str]]:
        """Attempt configured FTP and HTTP uploads.

        Returns (any_failed, error_messages).
        """
        failed = False
        errors: list[str] = []

        # FTP uploads
        if cfg.upload_groups:
            self.log_message.emit("Uploading group protocol via FTP...")
            if (
                upload_file(
                    cfg.ftp_path,
                    cfg.ftp_login,
                    cfg.ftp_password,
                    cfg.group_protocol_file,
                    errors,
                )
                == -1
            ):
                failed = True
            else:
                self.log_message.emit("  Group protocol: uploaded")
        if cfg.upload_absolute and not cfg.is_eliminator_finals():
            self.log_message.emit("Uploading absolute protocol via FTP...")
            if (
                upload_file(
                    cfg.ftp_path,
                    cfg.ftp_login,
                    cfg.ftp_password,
                    cfg.absolute_protocol_file,
                    errors,
                )
                == -1
            ):
                failed = True
            else:
                self.log_message.emit("  Absolute protocol: uploaded")

        # HTTP uploads
        if cfg.http_site_url:
            if cfg.upload_http_groups:
                self.log_message.emit("Uploading group protocol via HTTP...")
                if (
                    http_upload_protocol(
                        cfg.http_site_url,
                        cfg.http_upload_token,
                        "group",
                        cfg.group_protocol_file,
                        is_live=cfg.http_is_live,
                        stage_label=cfg.http_stage_label,
                        errors_out=errors,
                    )
                    == -1
                ):
                    failed = True
                else:
                    self.log_message.emit("  Group protocol: uploaded via HTTP")
            if cfg.upload_http_absolute and not cfg.is_eliminator_finals():
                self.log_message.emit("Uploading absolute protocol via HTTP...")
                if (
                    http_upload_protocol(
                        cfg.http_site_url,
                        cfg.http_upload_token,
                        "absolute",
                        cfg.absolute_protocol_file,
                        is_live=cfg.http_is_live,
                        stage_label=cfg.http_stage_label,
                        errors_out=errors,
                    )
                    == -1
                ):
                    failed = True
                else:
                    self.log_message.emit("  Absolute protocol: uploaded via HTTP")

        return failed, errors

    def _emit_upload_result(
        self, upload_failed: bool, upload_errors: list[str]
    ) -> None:
        if upload_failed:
            for err in upload_errors:
                self.log_message.emit(f"  ERROR: {err}")
        else:
            self.log_message.emit("Done.")

    def run(self) -> None:
        cfg = self._cfg
        if cfg.is_eliminator_finals():
            self.error.emit(
                "Eliminator Finals mode is not implemented in this version."
            )
            return
        log: list[str] = []
        try:
            self.log_message.emit("Reading start protocol...")
            start_list = read_start_protocol(
                cfg.start_protocol_file, cfg.skip_first_lap_effective()
            )
            self.log_message.emit(f"  {len(start_list)} competitors loaded")

            self.log_message.emit("Reading group times...")
            group_list = read_group_times(cfg.group_time_file)
            known_group_ids = {gs.group_id for gs in group_list}
            seen_extra: set[str] = set()
            for s in start_list:
                if s.group_id not in known_group_ids and s.group_id not in seen_extra:
                    seen_extra.add(s.group_id)
                    group_list.append(
                        GroupStartElement(group_id=s.group_id, seconds=0.0)
                    )
            self.log_message.emit(f"  {len(group_list)} groups loaded")

            self.log_message.emit("Reading finish times...")
            finish_list = read_finish_times(cfg.finish_time_file)
            self.log_message.emit(f"  {len(finish_list)} finish records loaded")

            remote_points: list[list] = []
            if cfg.n_remote_points > 0 and cfg.remote_points_path:
                self.log_message.emit("Reading remote control points...")
                for i in range(1, cfg.n_remote_points + 1):
                    pts = read_finish_times(
                        str(Path(cfg.remote_points_path) / f"results_{i}.txt")
                    )
                    remote_points.append(pts)
                    self.log_message.emit(f"  Point {i}: {len(pts)} records")

            start_check_list: list = []
            if cfg.use_start_check_list and cfg.start_check_list_file:
                self.log_message.emit("Reading start check list...")
                start_check_list = read_finish_times(cfg.start_check_list_file)
                self.log_message.emit(f"  {len(start_check_list)} check records")

            self.log_message.emit("Calculating protocol...")
            protocol = calculate_protocol(
                start_list,
                group_list,
                finish_list,
                remote_points,
                start_check_list,
                cfg,
                log,
            )
            n_points = len(remote_points)
            self.log_message.emit("Sorting protocol...")
            sorted_proto = generate_sorted_protocol(protocol, cfg, n_points)

            self.log_message.emit("Writing group protocol...")
            write_group_protocol(
                cfg.group_protocol_file, sorted_proto, group_list, cfg, n_points
            )
            self.log_message.emit("Writing absolute protocol...")
            write_absolute_protocol(
                cfg.absolute_protocol_file, sorted_proto, group_list, cfg, n_points
            )

            self.log_message.emit("Checking protocol...")
            check_start_protocol(
                protocol, finish_list, start_list, remote_points, cfg, log
            )

            for msg in log:
                self.log_message.emit(msg)

            upload_failed, upload_errors = self._do_uploads(cfg)
            self._emit_upload_result(upload_failed, upload_errors)
            self.finished_ok.emit()
        except Exception as exc:
            self.error.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Finish Protocol Generator")
        self.setWindowIcon(QIcon(str(Path(__file__).parent / "app.ico")))
        self._cfg = RaceConfig()
        self._worker: _GenerateWorker | None = None
        self._ftp_worker: _FTPWorker | None = None
        self._timer: QTimer | None = None
        self._chk_refresh: QCheckBox
        self._spin_refresh: QSpinBox
        self._chk_use_scl: QCheckBox
        self._combo_start_action: QComboBox
        self._combo_group_action: QComboBox
        self._combo_result_action: QComboBox
        self._combo_rp_action: QComboBox
        self._btn_ftp_download: QPushButton
        self._combo_scl_action: QComboBox
        self._spin_srp: QDoubleSpinBox
        self._log_file_path: str | None = None
        self._setup_ui()
        self._try_auto_load()

    def closeEvent(self, event) -> None:  # type: ignore[override]  # noqa: N802
        reply = QMessageBox.question(
            self,
            "Exit",
            "Are you sure to exit?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._save_race_info_to_path("fpg_info.txt")
            event.accept()
        else:
            event.ignore()

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)

        tabs = QTabWidget()
        root.addWidget(tabs)

        tabs.addTab(self._make_main_tab(), "Main")
        tabs.addTab(self._make_race_info_tab(), "Race Info")
        tabs.addTab(self._make_columns_tab(), "Columns")
        tabs.addTab(self._make_options_tab(), "Options")
        tabs.addTab(self._make_ftp_tab(), "FTP")
        tabs.addTab(self._make_http_tab(), "HTTP")
        tabs.addTab(self._make_logger_tab(), "Log")

    def _make_main_tab(self) -> QWidget:
        w = QWidget()
        ly = QVBoxLayout(w)

        def _file_row(label: str, attr: str, is_save: bool = False) -> QHBoxLayout:
            row = QHBoxLayout()
            row.addWidget(QLabel(label))
            edit = QLineEdit(getattr(self._cfg, attr))
            edit.setObjectName(attr)
            edit.textChanged.connect(lambda t, a=attr: setattr(self._cfg, a, t))
            row.addWidget(edit)
            btn = QPushButton("..." if is_save else "Open")
            btn.setFixedWidth(60)

            def _pick(_, e=edit, s=is_save) -> None:
                if s:
                    p, _ = QFileDialog.getSaveFileName(self, "Select file")
                else:
                    p, _ = QFileDialog.getOpenFileName(self, "Select file")
                if p:
                    e.setText(p)

            btn.clicked.connect(_pick)
            row.addWidget(btn)
            return row

        ly.addLayout(_file_row("Start protocol:", "start_protocol_file"))
        ly.addLayout(_file_row("Group times:", "group_time_file"))
        ly.addLayout(_file_row("Finish times:", "finish_time_file"))
        ly.addLayout(_file_row("Group protocol (output):", "group_protocol_file", True))
        ly.addLayout(
            _file_row("Absolute protocol (output):", "absolute_protocol_file", True)
        )
        ly.addLayout(_file_row("HTML styles template:", "template_file"))

        # remote control points
        row_rp = QHBoxLayout()
        row_rp.addWidget(QLabel("Control points (0=off):"))
        spin_rp = QSpinBox()
        spin_rp.setRange(0, 99)
        spin_rp.setObjectName("n_remote_points")
        spin_rp.setValue(self._cfg.n_remote_points)
        spin_rp.setFixedWidth(60)
        spin_rp.valueChanged.connect(lambda v: setattr(self._cfg, "n_remote_points", v))
        row_rp.addWidget(spin_rp)
        row_rp.addWidget(QLabel("Path prefix:"))
        edit_rp = QLineEdit(self._cfg.remote_points_path)
        edit_rp.setObjectName("remote_points_path")
        edit_rp.textChanged.connect(
            lambda t: setattr(self._cfg, "remote_points_path", t)
        )
        row_rp.addWidget(edit_rp)

        def _pick_rp(_checked: bool, e: QLineEdit = edit_rp) -> None:
            p = QFileDialog.getExistingDirectory(
                self, "Select directory for remote points"
            )
            if p:
                e.setText(str(Path(p)))

        btn_rp = QPushButton("Open")
        btn_rp.setFixedWidth(60)
        btn_rp.clicked.connect(_pick_rp)
        row_rp.addWidget(btn_rp)
        ly.addLayout(row_rp)

        # start check list
        row_scl = QHBoxLayout()
        self._chk_use_scl = QCheckBox("Use start check list:")
        self._chk_use_scl.setObjectName("use_start_check_list")
        self._chk_use_scl.setChecked(self._cfg.use_start_check_list)
        self._chk_use_scl.toggled.connect(self._on_scl_toggled)
        row_scl.addWidget(self._chk_use_scl)
        self._combo_scl_action = QComboBox()
        self._combo_scl_action.setObjectName("start_check_list_action")
        self._combo_scl_action.addItems(DOWNLOAD_ACTIONS)
        self._combo_scl_action.setCurrentText(self._cfg.start_check_list_action)
        self._combo_scl_action.setEnabled(self._cfg.use_start_check_list)
        self._combo_scl_action.currentTextChanged.connect(
            lambda t: setattr(self._cfg, "start_check_list_action", t)
        )
        row_scl.addWidget(self._combo_scl_action)
        edit_scl = QLineEdit(self._cfg.start_check_list_file)
        edit_scl.setObjectName("start_check_list_file")
        edit_scl.textChanged.connect(
            lambda t: setattr(self._cfg, "start_check_list_file", t)
        )
        row_scl.addWidget(edit_scl)

        def _pick_scl(_checked: bool, e: QLineEdit = edit_scl) -> None:
            p, _ = QFileDialog.getOpenFileName(self, "Select start check list file")
            if p:
                e.setText(p)

        btn_scl = QPushButton("Open")
        btn_scl.setFixedWidth(60)
        btn_scl.clicked.connect(_pick_scl)
        row_scl.addWidget(btn_scl)
        ly.addLayout(row_scl)

        # start registration period (used with start check list)
        row_srp = QHBoxLayout()
        row_srp.addWidget(QLabel("  Registration period (sec):"))
        self._spin_srp = QDoubleSpinBox()
        self._spin_srp.setObjectName("start_registration_period")
        self._spin_srp.setRange(0.0, 9999.0)
        self._spin_srp.setDecimals(3)
        self._spin_srp.setValue(self._cfg.start_registration_period)
        self._spin_srp.setEnabled(self._cfg.use_start_check_list)
        self._spin_srp.valueChanged.connect(
            lambda v: setattr(self._cfg, "start_registration_period", v)
        )
        row_srp.addWidget(self._spin_srp)
        row_srp.addStretch()
        ly.addLayout(row_srp)

        # race type
        row = QHBoxLayout()
        row.addWidget(QLabel("Race type:"))
        self._combo_race_type = QComboBox()
        self._combo_race_type.addItems(ALL_RACE_TYPES)
        self._combo_race_type.setCurrentText(self._cfg.race_type)
        self._combo_race_type.currentTextChanged.connect(
            lambda t: setattr(self._cfg, "race_type", t)
        )
        row.addWidget(self._combo_race_type)
        row.addStretch()
        ly.addLayout(row)

        # generate button
        self._btn_generate = QPushButton("Generate Protocol")
        self._btn_generate.setFixedHeight(40)
        self._btn_generate.clicked.connect(self._on_generate)
        ly.addWidget(self._btn_generate)
        ly.addStretch()
        return w

    def _make_race_info_tab(self) -> QWidget:
        w = QWidget()
        ly = QVBoxLayout(w)
        fields = [
            ("Race name:", "race_name"),
            ("Date:", "race_date"),
            ("Place:", "race_place"),
            ("Weather label:", "weather_label"),
            ("Weather:", "weather"),
            ("Main referee:", "main_referee"),
            ("Additional referee:", "additional_referee"),
            ("Referee column header:", "referee_label"),
            ("Secretary column header:", "secretary_label"),
            ("Organizer label:", "organizer_label"),
            ("Organizer:", "organizer"),
            ("Track conditions label:", "track_conditions_label"),
            ("Track conditions:", "track_conditions"),
            ("Sponsor:", "sponsor"),
            ("Bottom text:", "bottom_text"),
        ]
        for label, attr in fields:
            row = QHBoxLayout()
            row.addWidget(QLabel(label), 1)
            edit = QLineEdit(getattr(self._cfg, attr))
            edit.setObjectName(attr)
            edit.textChanged.connect(lambda t, a=attr: setattr(self._cfg, a, t))
            row.addWidget(edit, 3)
            ly.addLayout(row)

        # n_signs_after_point
        row = QHBoxLayout()
        row.addWidget(QLabel("Digits after decimal:"), 1)
        spin = QSpinBox()
        spin.setRange(0, 4)
        spin.setObjectName("n_signs_after_point")
        spin.setValue(self._cfg.n_signs_after_point)
        spin.valueChanged.connect(
            lambda v: setattr(self._cfg, "n_signs_after_point", v)
        )
        row.addWidget(spin)
        row.addStretch(3)
        ly.addLayout(row)

        btn_row = QHBoxLayout()
        btn_save_info = QPushButton("Save Race Info to file...")
        btn_save_info.clicked.connect(self._on_save_race_info)
        btn_row.addWidget(btn_save_info)
        btn_load_info = QPushButton("Load Race Info from file...")
        btn_load_info.clicked.connect(self._on_load_race_info)
        btn_row.addWidget(btn_load_info)
        ly.addLayout(btn_row)

        ly.addStretch()
        return w

    def _make_columns_tab(self) -> QWidget:
        w = QWidget()
        ly = QVBoxLayout(w)

        def _check_label_row(
            chk_text: str, chk_attr: str, lbl_attr: str | None = None
        ) -> QHBoxLayout:
            row = QHBoxLayout()
            cb = QCheckBox(chk_text)
            cb.setObjectName(chk_attr)
            cb.setChecked(bool(getattr(self._cfg, chk_attr)))
            cb.toggled.connect(lambda v, a=chk_attr: setattr(self._cfg, a, v))
            row.addWidget(cb, 1)
            if lbl_attr:
                edit = QLineEdit(getattr(self._cfg, lbl_attr))
                edit.setObjectName(lbl_attr)
                edit.textChanged.connect(lambda t, a=lbl_attr: setattr(self._cfg, a, t))
                row.addWidget(edit, 2)
            return row

        ly.addLayout(_check_label_row("Show place", "show_place", "place_label"))
        ly.addLayout(_check_label_row("Show number (ID)", "show_id", "id_label"))
        ly.addLayout(_check_label_row("Show name", "show_name", "name_label"))
        ly.addLayout(_check_label_row("Show year of birth", "show_age", "age_label"))
        ly.addLayout(_check_label_row("Show team", "show_team", "team_label"))
        ly.addLayout(_check_label_row("Show city", "show_city", "city_label"))
        ly.addLayout(
            _check_label_row(
                "Show group (absolute protocol)", "show_group", "group_label"
            )
        )
        row_orl = QHBoxLayout()
        row_orl.addWidget(QLabel("Absolute protocol title:"), 1)
        edit_orl = QLineEdit(self._cfg.overall_results_label)
        edit_orl.setObjectName("overall_results_label")
        edit_orl.textChanged.connect(
            lambda t: setattr(self._cfg, "overall_results_label", t)
        )
        row_orl.addWidget(edit_orl, 2)
        ly.addLayout(row_orl)
        ly.addLayout(
            _check_label_row(
                "Show additional info", "show_additional_info", "additional_info_label"
            )
        )
        ly.addLayout(
            _check_label_row(
                "Show start time / time shift", "show_time_shift", "time_shift_label"
            )
        )

        ly.addLayout(
            _check_label_row(
                "Show finish time", "show_finish_time", "finish_time_label"
            )
        )
        ly.addLayout(
            _check_label_row(
                "Show time difference", "show_time_difference", "time_difference_label"
            )
        )

        ly.addLayout(_check_label_row("Show lap times", "show_lap_times", "lap_name"))
        row_lai = QHBoxLayout()
        row_lai.addWidget(QLabel("Lap additional info label:"), 1)
        edit_lai = QLineEdit(self._cfg.lap_additional_info)
        edit_lai.setObjectName("lap_additional_info")
        edit_lai.textChanged.connect(
            lambda t: setattr(self._cfg, "lap_additional_info", t)
        )
        row_lai.addWidget(edit_lai, 2)
        ly.addLayout(row_lai)

        ly.addLayout(
            _check_label_row(
                "Show number of finished laps",
                "show_n_finished_laps",
                "n_finished_laps_label",
            )
        )
        for chk_text, attr in [
            ("Show lap finish cumulative time", "show_lap_finish"),
            ("Hide empty lap columns", "hide_empty_columns"),
            ("Stretch table to page width", "stretch"),
        ]:
            cb = QCheckBox(chk_text)
            cb.setObjectName(attr)
            cb.setChecked(bool(getattr(self._cfg, attr)))
            cb.toggled.connect(lambda v, a=attr: setattr(self._cfg, a, v))
            ly.addWidget(cb)
        ly.addLayout(
            _check_label_row(
                "Show intermediate splits button",
                "use_buttons",
                "use_buttons_label",
            )
        )
        ly.addLayout(
            _check_label_row(
                "Show lap stats button",
                "use_all_buttons",
                "use_all_buttons_label",
            )
        )

        ly.addStretch()
        return w

    def _make_options_tab(self) -> QWidget:
        w = QWidget()
        ly = QVBoxLayout(w)
        checks = [
            ("Print DNF", "print_dnf"),
            ("Print DNS", "print_dns"),
            ("Print DSQ", "print_dsq"),
            ("Disable DNF (everyone counts as finished)", "disable_dnf"),
            ("Disable DSQ", "disable_dsq"),
        ]
        for label, attr in checks:
            cb = QCheckBox(label)
            cb.setObjectName(attr)
            cb.setChecked(bool(getattr(self._cfg, attr)))
            cb.toggled.connect(lambda v, a=attr: setattr(self._cfg, a, v))
            ly.addWidget(cb)

        row = QHBoxLayout()
        row.addWidget(QLabel("Minimal lap time (sec):"), 1)
        spin = QSpinBox()
        spin.setRange(0, 99999)
        spin.setObjectName("minimal_time_for_lap")
        spin.setValue(self._cfg.minimal_time_for_lap)
        spin.valueChanged.connect(
            lambda v: setattr(self._cfg, "minimal_time_for_lap", v)
        )
        row.addWidget(spin)
        row.addStretch(3)
        ly.addLayout(row)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Time limit (sec, 0=off):"), 1)
        spin2 = QSpinBox()
        spin2.setRange(0, 999999)
        spin2.setObjectName("time_limit")
        spin2.setValue(self._cfg.time_limit)
        spin2.valueChanged.connect(lambda v: setattr(self._cfg, "time_limit", v))
        row2.addWidget(spin2)
        row2.addStretch(3)
        ly.addLayout(row2)

        # auto-refresh
        row_ar = QHBoxLayout()
        self._chk_refresh = QCheckBox("Auto-refresh protocol")
        self._chk_refresh.setChecked(False)
        row_ar.addWidget(self._chk_refresh)
        row_ar.addWidget(QLabel("Interval (sec):"))
        self._spin_refresh = QSpinBox()
        self._spin_refresh.setRange(1, 3600)
        self._spin_refresh.valueChanged.connect(
            lambda v: setattr(self._cfg, "auto_refresh_interval", v)
        )
        self._spin_refresh.setValue(self._cfg.auto_refresh_interval or 30)
        row_ar.addWidget(self._spin_refresh)
        row_ar.addStretch()
        self._chk_refresh.toggled.connect(self._on_refresh_toggled)
        ly.addLayout(row_ar)

        # laps difference check
        row_ld = QHBoxLayout()
        chk_ld = QCheckBox("Check laps difference")
        chk_ld.setObjectName("check_laps_difference")
        chk_ld.setChecked(self._cfg.check_laps_difference)
        chk_ld.toggled.connect(lambda v: setattr(self._cfg, "check_laps_difference", v))
        row_ld.addWidget(chk_ld)
        row_ld.addWidget(QLabel("Max deviation (%):"))
        spin_ld = QSpinBox()
        spin_ld.setObjectName("laps_difference_pct")
        spin_ld.setRange(0, 100)
        spin_ld.setValue(self._cfg.laps_difference_pct)
        spin_ld.valueChanged.connect(
            lambda v: setattr(self._cfg, "laps_difference_pct", v)
        )
        row_ld.addWidget(spin_ld)
        row_ld.addStretch()
        ly.addLayout(row_ld)

        ly.addStretch()
        return w

    def _make_ftp_tab(self) -> QWidget:
        w = QWidget()
        ly = QVBoxLayout(w)

        def _ftp_row(label: str, attr: str, masked: bool = False) -> QHBoxLayout:
            row = QHBoxLayout()
            row.addWidget(QLabel(label), 1)
            edit = QLineEdit(getattr(self._cfg, attr))
            edit.setObjectName(attr)
            if masked:
                edit.setEchoMode(QLineEdit.EchoMode.Password)
            edit.textChanged.connect(lambda t, a=attr: setattr(self._cfg, a, t))
            row.addWidget(edit, 3)
            return row

        ly.addLayout(_ftp_row("FTP address:", "ftp_path"))
        ly.addLayout(_ftp_row("Login:", "ftp_login"))
        ly.addLayout(_ftp_row("Password:", "ftp_password", masked=True))

        actions_data = [
            ("Start list source:", "start_list_action", "_combo_start_action"),
            ("Group times source:", "group_times_action", "_combo_group_action"),
            ("Finish times source:", "result_times_action", "_combo_result_action"),
            ("Remote points source:", "remote_points_action", "_combo_rp_action"),
        ]
        for label, attr, ivar in actions_data:
            row = QHBoxLayout()
            row.addWidget(QLabel(label), 1)
            combo = QComboBox()
            combo.addItems(DOWNLOAD_ACTIONS)
            combo.setCurrentText(getattr(self._cfg, attr))
            combo.currentTextChanged.connect(lambda t, a=attr: setattr(self._cfg, a, t))
            setattr(self, ivar, combo)
            row.addWidget(combo, 3)
            ly.addLayout(row)

        chk = QCheckBox("Merge by competitor number (ID) only")
        chk.setObjectName("merge_by_id")
        chk.setChecked(self._cfg.merge_by_id)
        chk.toggled.connect(lambda v: setattr(self._cfg, "merge_by_id", v))
        ly.addWidget(chk)

        chk_ug = QCheckBox("Upload Groups Protocol after generate")
        chk_ug.setObjectName("upload_groups")
        chk_ug.setChecked(self._cfg.upload_groups)
        chk_ug.toggled.connect(lambda v: setattr(self._cfg, "upload_groups", v))
        ly.addWidget(chk_ug)

        chk_ua = QCheckBox("Upload Absolute Protocol after generate")
        chk_ua.setObjectName("upload_absolute")
        chk_ua.setChecked(self._cfg.upload_absolute)
        chk_ua.toggled.connect(lambda v: setattr(self._cfg, "upload_absolute", v))
        ly.addWidget(chk_ua)

        self._btn_ftp_download = QPushButton("Download")
        self._btn_ftp_download.clicked.connect(self._on_ftp_download)
        ly.addWidget(self._btn_ftp_download)
        ly.addStretch()
        return w

    def _make_http_tab(self) -> QWidget:
        w = QWidget()
        ly = QVBoxLayout(w)

        def _http_row(label: str, attr: str, masked: bool = False) -> QHBoxLayout:
            row = QHBoxLayout()
            row.addWidget(QLabel(label), 1)
            edit = QLineEdit(getattr(self._cfg, attr))
            edit.setObjectName(attr)
            if masked:
                edit.setEchoMode(QLineEdit.EchoMode.Password)
            edit.textChanged.connect(lambda t, a=attr: setattr(self._cfg, a, t))
            row.addWidget(edit, 3)
            return row

        ly.addLayout(_http_row("Site URL:", "http_site_url"))
        ly.addLayout(_http_row("Upload token:", "http_upload_token", masked=True))

        row_src = QHBoxLayout()
        row_src.addWidget(QLabel("Start list source:"), 1)
        self._combo_start_source = QComboBox()
        self._combo_start_source.addItems(START_LIST_SOURCES)
        self._combo_start_source.setCurrentText(self._cfg.start_list_source)
        self._combo_start_source.currentTextChanged.connect(
            lambda t: setattr(self._cfg, "start_list_source", t)
        )
        row_src.addWidget(self._combo_start_source, 3)
        ly.addLayout(row_src)

        for label, attr, ivar in (
            ("Group times source:", "group_times_source", "_combo_group_source"),
            ("Finish times source:", "finish_times_source", "_combo_finish_source"),
            ("Remote points source:", "remote_points_source", "_combo_rp_source"),
        ):
            row = QHBoxLayout()
            row.addWidget(QLabel(label), 1)
            combo = QComboBox()
            combo.addItems(TIMING_SOURCES)
            combo.setCurrentText(getattr(self._cfg, attr))
            combo.currentTextChanged.connect(lambda t, a=attr: setattr(self._cfg, a, t))
            setattr(self, ivar, combo)
            row.addWidget(combo, 3)
            ly.addLayout(row)

        chk_il = QCheckBox("Upload as live (polling active on site)")
        chk_il.setObjectName("http_is_live")
        chk_il.setChecked(self._cfg.http_is_live)
        chk_il.toggled.connect(lambda v: setattr(self._cfg, "http_is_live", v))
        ly.addWidget(chk_il)

        ly.addLayout(_http_row("Stage label (optional):", "http_stage_label"))

        chk_hg = QCheckBox("Upload Groups Protocol via HTTP after generate")
        chk_hg.setObjectName("upload_http_groups")
        chk_hg.setChecked(self._cfg.upload_http_groups)
        chk_hg.toggled.connect(lambda v: setattr(self._cfg, "upload_http_groups", v))
        ly.addWidget(chk_hg)

        chk_ha = QCheckBox("Upload Absolute Protocol via HTTP after generate")
        chk_ha.setObjectName("upload_http_absolute")
        chk_ha.setChecked(self._cfg.upload_http_absolute)
        chk_ha.toggled.connect(lambda v: setattr(self._cfg, "upload_http_absolute", v))
        ly.addWidget(chk_ha)

        ly.addStretch()
        return w

    def _make_logger_tab(self) -> QWidget:
        w = QWidget()
        ly = QVBoxLayout(w)
        self._log_list = QListWidget()
        ly.addWidget(self._log_list)
        row = QHBoxLayout()
        self._log_search = QLineEdit()
        self._log_search.setPlaceholderText("Search log...")
        self._log_search.returnPressed.connect(self._search_log)
        row.addWidget(self._log_search)
        btn = QPushButton("Search")
        btn.clicked.connect(self._search_log)
        row.addWidget(btn)
        ly.addLayout(row)

        for chk_text, attr in [
            ("Show log in window", "use_interface_logger"),
            ("Write log to file", "use_file_logger"),
            ("Errors and warnings only", "errors_warnings_only"),
        ]:
            cb = QCheckBox(chk_text)
            cb.setObjectName(attr)
            cb.setChecked(bool(getattr(self._cfg, attr)))
            cb.toggled.connect(lambda v, a=attr: setattr(self._cfg, a, v))
            ly.addWidget(cb)

        return w

    # ------------------------------------------------------------------
    # slots
    # ------------------------------------------------------------------

    def _ftp_actions_set(self) -> bool:
        cfg = self._cfg
        actions = [
            cfg.start_list_action,
            cfg.group_times_action,
            cfg.result_times_action,
            cfg.remote_points_action,
        ]
        if cfg.use_start_check_list:
            actions.append(cfg.start_check_list_action)
        return any(a in ("Download", "Merge", "Merge+Remove") for a in actions)

    def _ftp_configured(self) -> bool:
        return bool(self._cfg.ftp_path) and self._ftp_actions_set()

    def _set_buttons_enabled(self, enabled: bool) -> None:
        self._btn_generate.setEnabled(enabled)
        if hasattr(self, "_btn_ftp_download"):
            self._btn_ftp_download.setEnabled(enabled)

    def _on_generate(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        if self._ftp_worker and self._ftp_worker.isRunning():
            return
        if self._ftp_actions_set() and not self._cfg.ftp_path:
            QMessageBox.critical(
                self,
                "FTP not configured",
                "Download actions are set but FTP address is empty.",
            )
            return
        self._apply_template()
        self._log_list.clear()
        self._log_file_path = (
            self._init_log_file() if self._cfg.use_file_logger else None
        )
        self._set_buttons_enabled(False)
        need_predownload = (
            self._ftp_configured()
            or self._cfg.start_list_source == START_LIST_SOURCE_SITE
            or self._cfg.group_times_source == TIMING_SOURCE_SITE
            or self._cfg.finish_times_source == TIMING_SOURCE_SITE
            or self._cfg.remote_points_source == TIMING_SOURCE_SITE
        )
        if need_predownload:
            self._ftp_worker = _FTPWorker(self._cfg)
            self._ftp_worker.log_message.connect(self._append_log)
            self._ftp_worker.finished_ok.connect(self._start_generate_worker)
            self._ftp_worker.finished_with_errors.connect(self._start_generate_worker)
            self._ftp_worker.error.connect(self._on_error)
            self._ftp_worker.start()
        else:
            self._start_generate_worker()

    def _start_generate_worker(self) -> None:
        self._worker = _GenerateWorker(self._cfg)
        self._worker.log_message.connect(self._append_log)
        self._worker.finished_ok.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _append_log(self, msg: str) -> None:
        is_err_wrn = "ERROR" in msg.upper() or "WARNING" in msg.upper()
        if self._cfg.use_file_logger and self._log_file_path:
            if not self._cfg.errors_warnings_only or is_err_wrn:
                try:
                    with Path(self._log_file_path).open("a", encoding="utf-8") as f:
                        f.write(msg + "\n")
                except OSError:
                    pass
        if not self._cfg.use_interface_logger:
            return
        if self._cfg.errors_warnings_only and not is_err_wrn:
            return
        self._log_list.addItem(msg)
        self._log_list.scrollToBottom()

    def _on_done(self) -> None:
        self._set_buttons_enabled(True)

    def _on_ftp_download(self) -> None:
        if self._ftp_worker and self._ftp_worker.isRunning():
            return
        if self._worker and self._worker.isRunning():
            return
        if not self._ftp_actions_set():
            QMessageBox.warning(
                self, "Nothing to download", "No download actions are configured."
            )
            return
        if not self._cfg.ftp_path:
            QMessageBox.critical(
                self,
                "FTP not configured",
                "Download actions are set but FTP address is empty.",
            )
            return
        self._log_list.clear()
        self._log_file_path = (
            self._init_log_file() if self._cfg.use_file_logger else None
        )
        self._set_buttons_enabled(False)
        self._ftp_worker = _FTPWorker(self._cfg)
        self._ftp_worker.log_message.connect(self._append_log)
        self._ftp_worker.finished_ok.connect(self._on_ftp_download_done)
        self._ftp_worker.finished_with_errors.connect(self._on_ftp_download_partial)
        self._ftp_worker.error.connect(self._on_error)
        self._ftp_worker.start()

    def _on_ftp_download_done(self) -> None:
        self._append_log("Download complete.")
        self._set_buttons_enabled(True)

    def _on_ftp_download_partial(self) -> None:
        self._append_log("Download finished with errors (see warnings above).")
        self._set_buttons_enabled(True)

    def _on_error(self, msg: str) -> None:
        self._append_log(f"ERROR: {msg}")
        self._set_buttons_enabled(True)
        QMessageBox.critical(self, "Error", msg)

    def _init_log_file(self) -> str:
        log_dir = Path("temp")
        log_dir.mkdir(exist_ok=True)
        n = 1
        while (log_dir / f"fpg{n}.txt").exists():
            n += 1
        return str(log_dir / f"fpg{n}.txt")

    def _on_scl_toggled(self, checked: bool) -> None:
        self._cfg.use_start_check_list = checked
        self._combo_scl_action.setEnabled(checked)
        self._spin_srp.setEnabled(checked)

    def _on_refresh_toggled(self, checked: bool) -> None:
        self._cfg.auto_refresh_enabled = checked
        if checked:
            interval_ms = self._spin_refresh.value() * 1000
            if self._timer is None:
                self._timer = QTimer(self)
                self._timer.timeout.connect(self._on_generate)
            self._timer.start(interval_ms)
        else:
            if self._timer is not None:
                self._timer.stop()

    def _save_race_info_to_path(self, path: str) -> None:  # noqa: C901
        cfg = self._cfg
        lines: list[str] = []

        # 13 fixed positional fields (C++ sequential format)
        lines += [
            cfg.sponsor,
            cfg.race_name,
            cfg.race_date,
            cfg.race_place,
            cfg.weather,
            cfg.main_referee,
            cfg.additional_referee,
            cfg.organizer,
            cfg.track_conditions,
            str(cfg.minimal_time_for_lap),
            str(cfg.time_limit),
            str(cfg.n_signs_after_point),
            cfg.race_type,
        ]

        if cfg.show_additional_info:
            lines += ["Info", cfg.additional_info_label]
        if cfg.auto_refresh_enabled and cfg.auto_refresh_interval > 0:
            # C++ stores Timer.Interval in ms; multiply seconds by 1000.
            lines += ["RefreshProtocol", str(cfg.auto_refresh_interval * 1000)]

        # always: referee/secretary labels
        lines += [cfg.referee_label, cfg.secretary_label]

        # optional column tags
        if cfg.show_id:
            lines += ["ID", cfg.id_label]
        if cfg.show_name:
            lines += ["Name", cfg.name_label]
        if cfg.show_age:
            lines += ["Age", cfg.age_label]
        if cfg.show_team:
            lines += ["Team", cfg.team_label]
        if cfg.show_city:
            lines += ["City", cfg.city_label]

        if cfg.show_lap_times:
            lines += [
                "Laps",
                "Lap Name",
                cfg.lap_name,
                "Lap Finish Info",
                cfg.lap_additional_info,
            ]
            if cfg.show_lap_finish:
                lines.append("Lap Finish")
            if cfg.hide_empty_columns:
                lines.append("Hide Empty Columns")

        if cfg.use_buttons:
            lines.append("Buttons")
        if cfg.use_all_buttons:
            lines.append("All Buttons")
        if cfg.upload_groups:
            lines.append("UploadGroups")
        if cfg.upload_absolute:
            lines.append("UploadAbsolute")

        # always: 4 action values and 3 FTP credentials
        lines += [
            cfg.start_list_action,
            cfg.group_times_action,
            cfg.result_times_action,
            cfg.remote_points_action,
        ]
        lines += [cfg.ftp_path, cfg.ftp_login, cfg.ftp_password]

        if cfg.show_finish_time:
            lines.append("Finish")
            if cfg.show_time_difference:
                lines.append("Time Difference")
            if cfg.show_n_finished_laps:
                lines.append("Number Of Laps Finished")

        if cfg.show_group:
            lines += ["Group", cfg.group_label]
        if cfg.show_place:
            lines += ["Place", cfg.place_label]
        if cfg.show_time_shift:
            lines += ["TimeShift", cfg.time_shift_label]

        # "Stratch" is the preserved C++ typo for "Stretch"
        if cfg.stretch:
            lines.append("Stratch")
        if cfg.print_dnf:
            lines.append("Print DNF")
        if cfg.print_dns:
            lines.append("Print DNS")
        if cfg.print_dsq:
            lines.append("Print DSQ")

        # always: 5 file paths
        lines += [
            cfg.start_protocol_file,
            cfg.group_time_file,
            cfg.finish_time_file,
            cfg.group_protocol_file,
            cfg.absolute_protocol_file,
        ]

        # always: remote points
        lines += [cfg.remote_points_path, str(cfg.n_remote_points)]

        if cfg.disable_dnf:
            lines.append("Disable DNF")
        if cfg.disable_dsq:
            lines.append("Disable DSQ")
        if cfg.use_file_logger:
            lines.append("Use File Logger")
        if cfg.use_interface_logger:
            lines.append("Use Interface Logger")
        if cfg.errors_warnings_only:
            lines.append("Err and Wrn only")
        if cfg.check_laps_difference:
            lines += ["Laps Difference Erroros", str(cfg.laps_difference_pct)]
        if cfg.use_start_check_list:
            lines += [
                "UseStartCheckList",
                cfg.start_check_list_action,
                f"{cfg.start_registration_period:g}",
            ]

        # always: bottom text (last C++ field)
        lines.append(cfg.bottom_text)

        # Python-only label extensions (after bottom_text so C++ ignores them)
        if cfg.show_finish_time:
            lines += ["FinishTimeLabel", cfg.finish_time_label]
            if cfg.show_time_difference:
                lines += ["TimeDifferenceLabel", cfg.time_difference_label]
        if cfg.show_n_finished_laps:
            lines += ["NFinishedLapsLabel", cfg.n_finished_laps_label]
        lines += ["TemplateFile", cfg.template_file]
        if cfg.use_buttons:
            lines += ["ButtonsLabel", cfg.use_buttons_label]
        if cfg.use_all_buttons:
            lines += ["AllButtonsLabel", cfg.use_all_buttons_label]
        lines += ["WeatherLabel", cfg.weather_label]
        lines += ["TrackLabel", cfg.track_conditions_label]
        lines += ["OrganizerLabel", cfg.organizer_label]
        lines += ["OverallResultsLabel", cfg.overall_results_label]
        lines += ["HttpSiteUrl", cfg.http_site_url]
        lines += ["HttpUploadToken", cfg.http_upload_token]
        lines += ["StartListSource", cfg.start_list_source]
        lines += ["GroupTimesSource", cfg.group_times_source]
        lines += ["FinishTimesSource", cfg.finish_times_source]
        lines += ["RemotePointsSource", cfg.remote_points_source]
        lines += ["HttpIsLive", "1" if cfg.http_is_live else "0"]
        lines += ["HttpStageLabel", cfg.http_stage_label]
        lines += ["UploadHttpGroups", "1" if cfg.upload_http_groups else "0"]
        lines += ["UploadHttpAbsolute", "1" if cfg.upload_http_absolute else "0"]

        try:
            with Path(path).open("w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to save: {exc}")

    def _on_save_race_info(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save race info", "fpg_info.txt", "Text files (*.txt)"
        )
        if not path:
            return
        self._save_race_info_to_path(path)

    def _load_race_info_from_path(self, path: str) -> None:  # noqa: C901
        # Auto-detect encoding and peek at first line to identify format
        text: str | None = None
        for enc in ("utf-8", "cp1251", "latin-1"):
            try:
                text = Path(path).read_text(encoding=enc)
                break
            except UnicodeDecodeError, OSError:
                continue
        if text is None:
            QMessageBox.critical(
                self, "Error", "Failed to read file (unknown encoding)"
            )
            return

        first_line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
        cfg = self._cfg

        if first_line == "# FPG Race Info":
            # New key=value format written by this application
            kv: dict[str, str] = {}
            for raw_line in text.splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or line == "End":
                    continue
                if "=" in line:
                    key, _, val = line.partition("=")
                    kv[key.strip()] = val.replace("\\n", "\n")

            def _str(k: str, default: str = "") -> str:
                return kv.get(k, default)

            def _int(k: str, default: int = 0) -> int:
                try:
                    return int(kv[k])
                except KeyError, ValueError:
                    return default

            def _float(k: str, default: float = 0.0) -> float:
                try:
                    return float(kv[k])
                except KeyError, ValueError:
                    return default

            def _bool(k: str, default: bool = False) -> bool:
                return bool(_int(k, int(default)))

            cfg.sponsor = _str("Sponsor", cfg.sponsor)
            cfg.race_name = _str("RaceName", cfg.race_name)
            cfg.race_date = _str("RaceDate", cfg.race_date)
            cfg.race_place = _str("RacePlace", cfg.race_place)
            cfg.weather = _str("Weather", cfg.weather)
            cfg.main_referee = _str("MainReferee", cfg.main_referee)
            cfg.additional_referee = _str("AdditionalReferee", cfg.additional_referee)
            cfg.organizer = _str("Organizer", cfg.organizer)
            cfg.track_conditions = _str("TrackConditions", cfg.track_conditions)
            cfg.referee_label = _str("RefereeLabel", cfg.referee_label)
            cfg.secretary_label = _str("SecretaryLabel", cfg.secretary_label)
            cfg.minimal_time_for_lap = _int(
                "MinimalTimeForLap", cfg.minimal_time_for_lap
            )
            cfg.time_limit = _int("TimeLimit", cfg.time_limit)
            cfg.n_signs_after_point = _int("NSignsAfterPoint", cfg.n_signs_after_point)
            cfg.race_type = _str("RaceType", cfg.race_type)
            cfg.start_protocol_file = _str("StartProtocol", cfg.start_protocol_file)
            cfg.group_time_file = _str("GroupTime", cfg.group_time_file)
            cfg.finish_time_file = _str("FinishTime", cfg.finish_time_file)
            cfg.group_protocol_file = _str("GroupProtocol", cfg.group_protocol_file)
            cfg.absolute_protocol_file = _str(
                "AbsoluteProtocol", cfg.absolute_protocol_file
            )
            cfg.n_remote_points = _int("NRemotePoints", cfg.n_remote_points)
            cfg.remote_points_path = _str("RemotePointsPath", cfg.remote_points_path)
            cfg.start_check_list_file = _str(
                "StartCheckListFile", cfg.start_check_list_file
            )
            cfg.use_start_check_list = _bool(
                "UseStartCheckList", cfg.use_start_check_list
            )
            cfg.start_check_list_action = _str(
                "StartCheckListAction", cfg.start_check_list_action
            )
            cfg.start_registration_period = _float(
                "StartRegistrationPeriod", cfg.start_registration_period
            )
            cfg.auto_refresh_interval = _int(
                "AutoRefreshInterval", cfg.auto_refresh_interval
            )
            # backward compat: old format had no explicit enabled flag
            cfg.auto_refresh_enabled = _bool(
                "AutoRefreshEnabled", cfg.auto_refresh_interval > 0
            )
            cfg.show_place = _bool("ShowPlace", cfg.show_place)
            cfg.show_id = _bool("ShowId", cfg.show_id)
            cfg.show_name = _bool("ShowName", cfg.show_name)
            cfg.show_age = _bool("ShowAge", cfg.show_age)
            cfg.show_team = _bool("ShowTeam", cfg.show_team)
            cfg.show_city = _bool("ShowCity", cfg.show_city)
            cfg.show_group = _bool("ShowGroup", cfg.show_group)
            cfg.show_lap_times = _bool("ShowLapTimes", cfg.show_lap_times)
            cfg.show_finish_time = _bool("ShowFinishTime", cfg.show_finish_time)
            cfg.finish_time_label = _str("FinishTimeLabel", cfg.finish_time_label)
            cfg.show_time_difference = _bool(
                "ShowTimeDifference", cfg.show_time_difference
            )
            cfg.time_difference_label = _str(
                "TimeDifferenceLabel", cfg.time_difference_label
            )
            cfg.show_additional_info = _bool(
                "ShowAdditionalInfo", cfg.show_additional_info
            )
            cfg.show_time_shift = _bool("ShowTimeShift", cfg.show_time_shift)
            cfg.show_n_finished_laps = _bool(
                "ShowNFinishedLaps", cfg.show_n_finished_laps
            )
            cfg.n_finished_laps_label = _str(
                "NFinishedLapsLabel", cfg.n_finished_laps_label
            )
            cfg.show_lap_finish = _bool("ShowLapFinish", cfg.show_lap_finish)
            cfg.hide_empty_columns = _bool("HideEmptyColumns", cfg.hide_empty_columns)
            cfg.stretch = _bool("Stretch", cfg.stretch)
            cfg.use_buttons = _bool("UseButtons", cfg.use_buttons)
            cfg.use_all_buttons = _bool("UseAllButtons", cfg.use_all_buttons)
            cfg.upload_groups = _bool("UploadGroups", cfg.upload_groups)
            cfg.upload_absolute = _bool("UploadAbsolute", cfg.upload_absolute)
            cfg.print_dnf = _bool("PrintDNF", cfg.print_dnf)
            cfg.print_dns = _bool("PrintDNS", cfg.print_dns)
            cfg.print_dsq = _bool("PrintDSQ", cfg.print_dsq)
            cfg.disable_dnf = _bool("DisableDNF", cfg.disable_dnf)
            cfg.disable_dsq = _bool("DisableDSQ", cfg.disable_dsq)
            cfg.lap_name = _str("LapName", cfg.lap_name)
            cfg.lap_additional_info = _str("LapAdditionalInfo", cfg.lap_additional_info)
            cfg.bottom_text = _str("BottomText", cfg.bottom_text)
            cfg.template_file = _str("TemplateFile", cfg.template_file)
            cfg.use_buttons_label = _str("ButtonsLabel", cfg.use_buttons_label)
            cfg.use_all_buttons_label = _str(
                "AllButtonsLabel", cfg.use_all_buttons_label
            )
            cfg.weather_label = _str("WeatherLabel", cfg.weather_label)
            cfg.track_conditions_label = _str("TrackLabel", cfg.track_conditions_label)
            cfg.organizer_label = _str("OrganizerLabel", cfg.organizer_label)
            cfg.overall_results_label = _str(
                "OverallResultsLabel", cfg.overall_results_label
            )
            cfg.http_site_url = _str("HttpSiteUrl", cfg.http_site_url)
            cfg.http_upload_token = _str("HttpUploadToken", cfg.http_upload_token)
            cfg.start_list_source = _str("StartListSource", cfg.start_list_source)
            cfg.group_times_source = _str("GroupTimesSource", cfg.group_times_source)
            cfg.finish_times_source = _str("FinishTimesSource", cfg.finish_times_source)
            cfg.remote_points_source = _str(
                "RemotePointsSource", cfg.remote_points_source
            )
            cfg.http_is_live = _bool("HttpIsLive", cfg.http_is_live)
            cfg.http_stage_label = _str("HttpStageLabel", cfg.http_stage_label)
            cfg.upload_http_groups = _bool("UploadHttpGroups", cfg.upload_http_groups)
            cfg.upload_http_absolute = _bool(
                "UploadHttpAbsolute", cfg.upload_http_absolute
            )
        else:
            # Original C++ positional format (load_config_file handles encoding)
            d = load_config_file(path)

            # Reset all optional flags -- C++ clears all controls before parsing,
            # so absent tags mean the feature is OFF, regardless of RaceConfig defaults.
            cfg.show_additional_info = False
            cfg.auto_refresh_interval = 0
            cfg.auto_refresh_enabled = False
            cfg.show_id = False
            cfg.show_name = False
            cfg.show_age = False
            cfg.show_team = False
            cfg.show_city = False
            cfg.show_lap_times = False
            cfg.show_lap_finish = False
            cfg.hide_empty_columns = False
            cfg.use_buttons = False
            cfg.use_all_buttons = False
            cfg.upload_groups = False
            cfg.upload_absolute = False
            cfg.show_finish_time = False
            cfg.show_time_difference = False
            cfg.show_n_finished_laps = False
            cfg.show_group = False
            cfg.show_place = False
            cfg.show_time_shift = False
            cfg.stretch = False
            cfg.print_dnf = False
            cfg.print_dns = False
            cfg.print_dsq = False
            cfg.disable_dnf = False
            cfg.disable_dsq = False
            cfg.use_file_logger = False
            cfg.use_interface_logger = False
            cfg.errors_warnings_only = False
            cfg.check_laps_difference = False
            cfg.use_start_check_list = False
            cfg.id_label = ""
            cfg.name_label = ""
            cfg.age_label = ""
            cfg.team_label = ""
            cfg.city_label = ""
            cfg.group_label = ""
            cfg.place_label = ""
            cfg.time_shift_label = ""
            cfg.additional_info_label = ""
            cfg.finish_time_label = "Time"
            cfg.time_difference_label = "(gap)"
            cfg.n_finished_laps_label = "(laps)"
            cfg.use_buttons_label = RaceConfig().use_buttons_label
            cfg.use_all_buttons_label = RaceConfig().use_all_buttons_label
            cfg.weather_label = RaceConfig().weather_label
            cfg.track_conditions_label = RaceConfig().track_conditions_label
            cfg.organizer_label = RaceConfig().organizer_label
            cfg.overall_results_label = RaceConfig().overall_results_label

            def _ds(k: str, default: str = "") -> str:
                return d.get(k, default)

            def _di(k: str, default: int = 0) -> int:
                try:
                    return int(d[k])
                except KeyError, ValueError:
                    return default

            def _df(k: str, default: float = 0.0) -> float:
                try:
                    return float(d[k])
                except KeyError, ValueError:
                    return default

            def _db(k: str, default: bool = False) -> bool:
                return bool(_di(k, int(default)))

            cfg.sponsor = _ds("sponsor", cfg.sponsor)
            cfg.race_name = _ds("race_name", cfg.race_name)
            cfg.race_date = _ds("race_date", cfg.race_date)
            cfg.race_place = _ds("race_place", cfg.race_place)
            cfg.weather = _ds("weather", cfg.weather)
            cfg.main_referee = _ds("main_referee", cfg.main_referee)
            cfg.additional_referee = _ds("additional_referee", cfg.additional_referee)
            cfg.organizer = _ds("organizer", cfg.organizer)
            cfg.track_conditions = _ds("track_conditions", cfg.track_conditions)
            cfg.minimal_time_for_lap = _di(
                "minimal_time_for_lap", cfg.minimal_time_for_lap
            )
            cfg.time_limit = _di("time_limit", cfg.time_limit)
            cfg.n_signs_after_point = _di(
                "n_signs_after_point", cfg.n_signs_after_point
            )
            cfg.race_type = _ds("race_type", cfg.race_type)
            cfg.show_additional_info = _db(
                "show_additional_info", cfg.show_additional_info
            )
            if "additional_info_label" in d:
                cfg.additional_info_label = d["additional_info_label"]
            cfg.auto_refresh_interval = _di(
                "auto_refresh_interval", cfg.auto_refresh_interval
            )
            cfg.auto_refresh_enabled = _db(
                "auto_refresh_enabled", cfg.auto_refresh_enabled
            )
            cfg.referee_label = _ds("referee_label", cfg.referee_label)
            cfg.secretary_label = _ds("secretary_label", cfg.secretary_label)
            cfg.show_id = _db("show_id", cfg.show_id)
            cfg.id_label = _ds("id_label", cfg.id_label)
            cfg.show_name = _db("show_name", cfg.show_name)
            cfg.name_label = _ds("name_label", cfg.name_label)
            cfg.show_age = _db("show_age", cfg.show_age)
            cfg.age_label = _ds("age_label", cfg.age_label)
            cfg.show_team = _db("show_team", cfg.show_team)
            cfg.team_label = _ds("team_label", cfg.team_label)
            cfg.show_city = _db("show_city", cfg.show_city)
            cfg.city_label = _ds("city_label", cfg.city_label)
            cfg.show_lap_times = _db("show_lap_times", cfg.show_lap_times)
            cfg.lap_name = _ds("lap_name", cfg.lap_name)
            cfg.lap_additional_info = _ds(
                "lap_additional_info", cfg.lap_additional_info
            )
            cfg.show_lap_finish = _db("show_lap_finish", cfg.show_lap_finish)
            cfg.hide_empty_columns = _db("hide_empty_columns", cfg.hide_empty_columns)
            cfg.use_buttons = _db("use_buttons", cfg.use_buttons)
            cfg.use_all_buttons = _db("use_all_buttons", cfg.use_all_buttons)
            cfg.upload_groups = _db("upload_groups", cfg.upload_groups)
            cfg.upload_absolute = _db("upload_absolute", cfg.upload_absolute)
            cfg.show_finish_time = _db("show_finish_time", cfg.show_finish_time)
            cfg.finish_time_label = _ds("finish_time_label", cfg.finish_time_label)
            cfg.show_time_difference = _db(
                "show_time_difference", cfg.show_time_difference
            )
            cfg.time_difference_label = _ds(
                "time_difference_label", cfg.time_difference_label
            )
            cfg.show_n_finished_laps = _db(
                "show_n_finished_laps", cfg.show_n_finished_laps
            )
            cfg.n_finished_laps_label = _ds(
                "n_finished_laps_label", cfg.n_finished_laps_label
            )
            cfg.show_group = _db("show_group", cfg.show_group)
            cfg.group_label = _ds("group_label", cfg.group_label)
            cfg.show_place = _db("show_place", cfg.show_place)
            cfg.place_label = _ds("place_label", cfg.place_label)
            cfg.show_time_shift = _db("show_time_shift", cfg.show_time_shift)
            cfg.time_shift_label = _ds("time_shift_label", cfg.time_shift_label)
            cfg.stretch = _db("stretch", cfg.stretch)
            cfg.print_dnf = _db("print_dnf", cfg.print_dnf)
            cfg.print_dns = _db("print_dns", cfg.print_dns)
            cfg.print_dsq = _db("print_dsq", cfg.print_dsq)
            cfg.start_protocol_file = _ds(
                "start_protocol_file", cfg.start_protocol_file
            )
            cfg.group_time_file = _ds("group_time_file", cfg.group_time_file)
            cfg.finish_time_file = _ds("finish_time_file", cfg.finish_time_file)
            cfg.group_protocol_file = _ds(
                "group_protocol_file", cfg.group_protocol_file
            )
            cfg.absolute_protocol_file = _ds(
                "absolute_protocol_file", cfg.absolute_protocol_file
            )
            cfg.remote_points_path = _ds("remote_points_path", cfg.remote_points_path)
            cfg.n_remote_points = _di("n_remote_points", cfg.n_remote_points)
            cfg.start_list_action = _ds("start_list_action", cfg.start_list_action)
            cfg.group_times_action = _ds("group_times_action", cfg.group_times_action)
            cfg.result_times_action = _ds(
                "result_times_action", cfg.result_times_action
            )
            cfg.remote_points_action = _ds(
                "remote_points_action", cfg.remote_points_action
            )
            cfg.ftp_path = _ds("ftp_path", cfg.ftp_path)
            cfg.ftp_login = _ds("ftp_login", cfg.ftp_login)
            cfg.ftp_password = _ds("ftp_password", cfg.ftp_password)
            cfg.disable_dnf = _db("disable_dnf", cfg.disable_dnf)
            cfg.disable_dsq = _db("disable_dsq", cfg.disable_dsq)
            cfg.use_file_logger = _db("use_file_logger", cfg.use_file_logger)
            cfg.use_interface_logger = _db(
                "use_interface_logger", cfg.use_interface_logger
            )
            cfg.errors_warnings_only = _db(
                "errors_warnings_only", cfg.errors_warnings_only
            )
            cfg.check_laps_difference = _db(
                "check_laps_difference", cfg.check_laps_difference
            )
            cfg.laps_difference_pct = _di(
                "laps_difference_pct", cfg.laps_difference_pct
            )
            cfg.use_start_check_list = _db(
                "use_start_check_list", cfg.use_start_check_list
            )
            cfg.start_check_list_action = _ds(
                "start_check_list_action", cfg.start_check_list_action
            )
            cfg.start_check_list_file = _ds(
                "start_check_list_file", cfg.start_check_list_file
            )
            cfg.start_registration_period = _df(
                "start_registration_period", cfg.start_registration_period
            )
            cfg.bottom_text = _ds("bottom_text", cfg.bottom_text)
            cfg.template_file = _ds("template_file", cfg.template_file)
            cfg.use_buttons_label = _ds("use_buttons_label", cfg.use_buttons_label)
            cfg.use_all_buttons_label = _ds(
                "use_all_buttons_label", cfg.use_all_buttons_label
            )
            cfg.weather_label = _ds("weather_label", cfg.weather_label)
            cfg.track_conditions_label = _ds(
                "track_conditions_label", cfg.track_conditions_label
            )
            cfg.organizer_label = _ds("organizer_label", cfg.organizer_label)
            cfg.overall_results_label = _ds(
                "overall_results_label", cfg.overall_results_label
            )
            cfg.http_site_url = _ds("http_site_url", cfg.http_site_url)
            cfg.http_upload_token = _ds("http_upload_token", cfg.http_upload_token)
            cfg.start_list_source = _ds("start_list_source", cfg.start_list_source)
            cfg.group_times_source = _ds("group_times_source", cfg.group_times_source)
            cfg.finish_times_source = _ds(
                "finish_times_source", cfg.finish_times_source
            )
            cfg.remote_points_source = _ds(
                "remote_points_source", cfg.remote_points_source
            )
            cfg.http_is_live = _db("http_is_live", cfg.http_is_live)
            cfg.http_stage_label = _ds("http_stage_label", cfg.http_stage_label)
            cfg.upload_http_groups = _db("upload_http_groups", cfg.upload_http_groups)
            cfg.upload_http_absolute = _db(
                "upload_http_absolute", cfg.upload_http_absolute
            )

        self._apply_template()
        self._sync_ui_from_cfg()
        self._on_refresh_toggled(self._cfg.auto_refresh_enabled)

    def _on_load_race_info(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load race info", "", "Text files (*.txt)"
        )
        if not path:
            return
        self._load_race_info_from_path(path)

    def _try_auto_load(self) -> None:
        auto_path = Path("fpg_info.txt")
        if auto_path.exists():
            self._load_race_info_from_path(str(auto_path))
        else:
            self._apply_template()

    def _sync_named_widgets(self, cfg: RaceConfig) -> None:
        for w_le in self.findChildren(QLineEdit):
            name = w_le.objectName()
            if name and hasattr(cfg, name):
                w_le.blockSignals(True)
                w_le.setText(str(getattr(cfg, name) or ""))
                w_le.blockSignals(False)
        for w_sb in self.findChildren(QSpinBox):
            name = w_sb.objectName()
            if name and hasattr(cfg, name):
                w_sb.blockSignals(True)
                w_sb.setValue(int(getattr(cfg, name) or 0))
                w_sb.blockSignals(False)
        for w_dsb in self.findChildren(QDoubleSpinBox):
            name = w_dsb.objectName()
            if name and hasattr(cfg, name):
                w_dsb.blockSignals(True)
                w_dsb.setValue(float(getattr(cfg, name) or 0.0))
                w_dsb.blockSignals(False)
        for w_cb in self.findChildren(QCheckBox):
            name = w_cb.objectName()
            if name and hasattr(cfg, name):
                w_cb.blockSignals(True)
                w_cb.setChecked(bool(getattr(cfg, name)))
                w_cb.blockSignals(False)

    def _sync_ui_from_cfg(self) -> None:
        cfg = self._cfg
        self._sync_named_widgets(cfg)
        if hasattr(self, "_combo_race_type"):
            self._combo_race_type.blockSignals(True)
            self._combo_race_type.setCurrentText(cfg.race_type)
            self._combo_race_type.blockSignals(False)
        if hasattr(self, "_combo_start_source"):
            self._combo_start_source.blockSignals(True)
            self._combo_start_source.setCurrentText(cfg.start_list_source)
            self._combo_start_source.blockSignals(False)
        for ivar, attr in (
            ("_combo_group_source", "group_times_source"),
            ("_combo_finish_source", "finish_times_source"),
            ("_combo_rp_source", "remote_points_source"),
        ):
            combo = getattr(self, ivar, None)
            if combo is not None:
                combo.blockSignals(True)
                combo.setCurrentText(getattr(cfg, attr))
                combo.blockSignals(False)
        if hasattr(self, "_spin_refresh"):
            self._spin_refresh.blockSignals(True)
            self._spin_refresh.setValue(cfg.auto_refresh_interval or 30)
            self._spin_refresh.blockSignals(False)
        if hasattr(self, "_chk_refresh"):
            self._chk_refresh.blockSignals(True)
            self._chk_refresh.setChecked(cfg.auto_refresh_enabled)
            self._chk_refresh.blockSignals(False)
        if hasattr(self, "_combo_scl_action"):
            self._combo_scl_action.setEnabled(cfg.use_start_check_list)
        if hasattr(self, "_spin_srp"):
            self._spin_srp.setEnabled(cfg.use_start_check_list)
        self._sync_ftp_combos_from_cfg(cfg)

    def _sync_ftp_combos_from_cfg(self, cfg: RaceConfig) -> None:
        for ivar, attr in (
            ("_combo_start_action", "start_list_action"),
            ("_combo_group_action", "group_times_action"),
            ("_combo_result_action", "result_times_action"),
            ("_combo_rp_action", "remote_points_action"),
            ("_combo_scl_action", "start_check_list_action"),
        ):
            if hasattr(self, ivar):
                combo = getattr(self, ivar)
                combo.blockSignals(True)
                combo.setCurrentText(getattr(cfg, attr))
                combo.blockSignals(False)

    def _apply_template(self) -> None:
        st = load_template(self._cfg.template_file) if self._cfg.template_file else None
        self._cfg.styles = st if st is not None else HtmlStyles()

    def _search_log(self) -> None:
        term = self._log_search.text().lower()
        if not term:
            return
        count = self._log_list.count()
        start = (
            self._log_list.currentRow() + 1 if self._log_list.currentRow() >= 0 else 0
        )
        for offset in range(count):
            idx = (start + offset) % count
            item = self._log_list.item(idx)
            if item and term in item.text().lower():
                self._log_list.setCurrentRow(idx)
                return
        QMessageBox.information(self, "Search", "No matches found.")
