"""PySide6 main window for Finish Protocol Generator."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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
from app.config import ALL_RACE_TYPES, RaceConfig
from app.file_io import (
    load_config_file,
    read_finish_times,
    read_group_times,
    read_start_protocol,
)
from app.ftp_io import DOWNLOAD_ACTIONS, download_file, upload_file
from app.html_writer import write_absolute_protocol, write_group_protocol


class _FTPWorker(QThread):
    log_message = Signal(str)
    finished_ok = Signal()
    error = Signal(str)

    def __init__(self, cfg: RaceConfig) -> None:
        super().__init__()
        self._cfg = cfg

    def run(self) -> None:
        cfg = self._cfg
        failed = False

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
                    local = cfg.remote_points_path + f"results_{i}.txt"
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
            self.error.emit("Some downloads failed - see log for details.")
        else:
            self.finished_ok.emit()


class _GenerateWorker(QThread):
    log_message = Signal(str)
    finished_ok = Signal()
    error = Signal(str)

    def __init__(self, cfg: RaceConfig) -> None:
        super().__init__()
        self._cfg = cfg

    def run(self) -> None:
        cfg = self._cfg
        log: list[str] = []
        try:
            self.log_message.emit("Reading start protocol...")
            start_list = read_start_protocol(
                cfg.start_protocol_file, cfg.skip_first_lap_effective()
            )
            self.log_message.emit(f"  {len(start_list)} competitors loaded")

            self.log_message.emit("Reading group times...")
            group_list = read_group_times(cfg.group_time_file)
            self.log_message.emit(f"  {len(group_list)} groups loaded")

            self.log_message.emit("Reading finish times...")
            finish_list = read_finish_times(cfg.finish_time_file)
            self.log_message.emit(f"  {len(finish_list)} finish records loaded")

            remote_points: list[list] = []
            if cfg.n_remote_points > 0 and cfg.remote_points_path:
                self.log_message.emit("Reading remote control points...")
                for i in range(1, cfg.n_remote_points + 1):
                    pts = read_finish_times(cfg.remote_points_path + f"results_{i}.txt")
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

            if cfg.upload_groups:
                self.log_message.emit("Uploading group protocol...")
                if (
                    upload_file(
                        cfg.ftp_path,
                        cfg.ftp_login,
                        cfg.ftp_password,
                        cfg.group_protocol_file,
                    )
                    == -1
                ):
                    self.log_message.emit("  ERROR: upload group protocol")
                else:
                    self.log_message.emit("  Group protocol: uploaded")

            if cfg.upload_absolute and not cfg.is_eliminator_finals():
                self.log_message.emit("Uploading absolute protocol...")
                if (
                    upload_file(
                        cfg.ftp_path,
                        cfg.ftp_login,
                        cfg.ftp_password,
                        cfg.absolute_protocol_file,
                    )
                    == -1
                ):
                    self.log_message.emit("  ERROR: upload absolute protocol")
                else:
                    self.log_message.emit("  Absolute protocol: uploaded")

            self.log_message.emit("Checking protocol...")
            check_start_protocol(
                protocol, finish_list, start_list, remote_points, cfg, log
            )

            for msg in log:
                self.log_message.emit(msg)
            self.log_message.emit("Done.")
            self.finished_ok.emit()
        except Exception as exc:
            self.error.emit(str(exc))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Finish Protocol Generator (pulse-sports.ru)")
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
        self._setup_ui()

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
                e.setText(p + "/")

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
        self._chk_use_scl.toggled.connect(
            lambda v: setattr(self._cfg, "use_start_check_list", v)
        )
        row_scl.addWidget(self._chk_use_scl)
        self._combo_scl_action = QComboBox()
        self._combo_scl_action.setObjectName("start_check_list_action")
        self._combo_scl_action.addItems(DOWNLOAD_ACTIONS)
        self._combo_scl_action.setCurrentText(self._cfg.start_check_list_action)
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
            ("Weather:", "weather"),
            ("Main referee:", "main_referee"),
            ("Additional referee:", "additional_referee"),
            ("Organizer:", "organizer"),
            ("Track conditions:", "track_conditions"),
            ("Sponsor:", "sponsor"),
            ("Lap name:", "lap_name"),
            ("Lap additional info:", "lap_additional_info"),
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
        checks = [
            ("Show place", "show_place"),
            ("Show number (ID)", "show_id"),
            ("Show name", "show_name"),
            ("Show year of birth", "show_age"),
            ("Show team", "show_team"),
            ("Show city", "show_city"),
            ("Show group (absolute protocol)", "show_group"),
            ("Show lap times", "show_lap_times"),
            ("Show finish time", "show_finish_time"),
            ("Show time difference", "show_time_difference"),
            ("Show additional info", "show_additional_info"),
            ("Show start time / time shift", "show_time_shift"),
            ("Show number of finished laps", "show_n_finished_laps"),
            ("Show lap finish cumulative time", "show_lap_finish"),
            ("Hide empty lap columns", "hide_empty_columns"),
            ("Stretch table to page width", "stretch"),
        ]
        for label, attr in checks:
            cb = QCheckBox(label)
            cb.setObjectName(attr)
            cb.setChecked(bool(getattr(self._cfg, attr)))
            cb.toggled.connect(lambda v, a=attr: setattr(self._cfg, a, v))
            ly.addWidget(cb)
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
            ("Start list:", "start_list_action", "_combo_start_action"),
            ("Group times:", "group_times_action", "_combo_group_action"),
            ("Finish times:", "result_times_action", "_combo_result_action"),
            ("Remote points:", "remote_points_action", "_combo_rp_action"),
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
        self._log_list.clear()
        self._set_buttons_enabled(False)
        if self._ftp_configured():
            self._ftp_worker = _FTPWorker(self._cfg)
            self._ftp_worker.log_message.connect(self._append_log)
            self._ftp_worker.finished_ok.connect(self._start_generate_worker)
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
        self._set_buttons_enabled(False)
        self._ftp_worker = _FTPWorker(self._cfg)
        self._ftp_worker.log_message.connect(self._append_log)
        self._ftp_worker.finished_ok.connect(self._on_ftp_download_done)
        self._ftp_worker.error.connect(self._on_error)
        self._ftp_worker.start()

    def _on_ftp_download_done(self) -> None:
        self._append_log("Download complete.")
        self._set_buttons_enabled(True)

    def _on_error(self, msg: str) -> None:
        self._set_buttons_enabled(True)
        QMessageBox.critical(self, "Error", msg)

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

    def _on_save_race_info(self) -> None:  # noqa: C901
        path, _ = QFileDialog.getSaveFileName(
            self, "Save race info", "fpg_info.txt", "Text files (*.txt)"
        )
        if not path:
            return
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
                str(int(cfg.start_registration_period)),
            ]

        # always: bottom text (last field)
        lines.append(cfg.bottom_text)

        try:
            with Path(path).open("w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")

        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to save: {exc}")

    def _on_load_race_info(self) -> None:  # noqa: C901
        path, _ = QFileDialog.getOpenFileName(
            self, "Load race info", "", "Text files (*.txt)"
        )
        if not path:
            return

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
            cfg.show_time_difference = _bool(
                "ShowTimeDifference", cfg.show_time_difference
            )
            cfg.show_additional_info = _bool(
                "ShowAdditionalInfo", cfg.show_additional_info
            )
            cfg.show_time_shift = _bool("ShowTimeShift", cfg.show_time_shift)
            cfg.show_n_finished_laps = _bool(
                "ShowNFinishedLaps", cfg.show_n_finished_laps
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
        else:
            # Original C++ positional format (load_config_file handles encoding)
            d = load_config_file(path)

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
            cfg.show_time_difference = _db(
                "show_time_difference", cfg.show_time_difference
            )
            cfg.show_n_finished_laps = _db(
                "show_n_finished_laps", cfg.show_n_finished_laps
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

        self._sync_ui_from_cfg()

    def _sync_ui_from_cfg(self) -> None:
        cfg = self._cfg
        for w in self.findChildren(QLineEdit):
            name = w.objectName()
            if name and hasattr(cfg, name):
                w.blockSignals(True)
                w.setText(str(getattr(cfg, name) or ""))
                w.blockSignals(False)
        for w in self.findChildren(QSpinBox):
            name = w.objectName()
            if name and hasattr(cfg, name):
                w.blockSignals(True)
                w.setValue(int(getattr(cfg, name) or 0))
                w.blockSignals(False)
        for w in self.findChildren(QCheckBox):
            name = w.objectName()
            if name and hasattr(cfg, name):
                w.blockSignals(True)
                w.setChecked(bool(getattr(cfg, name)))
                w.blockSignals(False)
        if hasattr(self, "_combo_race_type"):
            self._combo_race_type.blockSignals(True)
            self._combo_race_type.setCurrentText(cfg.race_type)
            self._combo_race_type.blockSignals(False)
        if hasattr(self, "_spin_refresh"):
            self._spin_refresh.blockSignals(True)
            self._spin_refresh.setValue(cfg.auto_refresh_interval or 30)
            self._spin_refresh.blockSignals(False)
        if hasattr(self, "_chk_refresh"):
            self._chk_refresh.setChecked(cfg.auto_refresh_enabled)
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
