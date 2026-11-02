"""Right-hand panel: preset picker and every encoding option."""

from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from clipshrinker.config import OVERWRITE_MODES
from clipshrinker.encode import (
    AUDIO_CODECS,
    AUDIO_TRACKS,
    CODECS,
    CONTAINERS,
    CRF_RANGE,
    DEFAULT_CRF,
    ENCODERS,
    HARDWARE,
    MODE_BITRATE,
    MODE_QUALITY,
    MODE_SIZE,
    RES_AUTO,
    RES_KEEP,
    SPEEDS,
    EncodeSettings,
    validate,
)
from clipshrinker.presets import Preset

RESOLUTIONS = [(RES_AUTO, "Auto (fit the size)"), (RES_KEEP, "Original")] + [
    (h, f"{h}p") for h in (2160, 1440, 1080, 720, 540, 480, 360)
]
FRAMERATES = [(0, "Original")] + [(f, f"{f:g} fps") for f in (120, 60, 50, 30, 25, 24, 15)]
AUDIO_BITRATES = [32, 48, 64, 96, 128, 160, 192, 256, 320]
CHANNELS = [(0, "Original"), (2, "Stereo"), (1, "Mono")]
SIZE_CHIPS = [("10 MB", 9.5), ("20 MB", 19), ("50 MB", 48), ("100 MB", 96), ("500 MB", 480)]


def make_combo(items) -> QComboBox:
    combo = QComboBox()
    pairs = items.items() if isinstance(items, dict) else items
    for data, label in pairs:
        combo.addItem(label, data)
    return combo


def set_combo(combo: QComboBox, value) -> None:
    idx = combo.findData(value)
    if idx < 0 and isinstance(value, (int, float)):
        # Values that aren't in the list (hand-edited config) get added on the fly.
        combo.addItem(str(value), value)
        idx = combo.count() - 1
    combo.setCurrentIndex(max(0, idx))


def section(title: str) -> QLabel:
    label = QLabel(title.upper())
    label.setObjectName("SectionTitle")
    return label


def field_label(text: str) -> QLabel:
    # Same width in every section so the fields line up down the whole panel.
    label = QLabel(text)
    label.setFixedWidth(78)
    return label


def hint(text: str = "", name: str = "Hint") -> QLabel:
    label = QLabel(text)
    label.setObjectName(name)
    label.setWordWrap(True)
    return label


class SettingsPanel(QWidget):
    changed = Signal()
    apply_to_selected = Signal()
    save_preset_requested = Signal()
    delete_preset_requested = Signal()
    preferences_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Panel")
        self.setMinimumWidth(340)
        self._presets: List[Preset] = []
        self._loading = False
        self._hw_available: Dict[str, bool] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget()
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        lay = QVBoxLayout(body)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(10)

        # ---- preset ----------------------------------------------------------
        lay.addWidget(section("Preset"))
        card = QFrame()
        card.setObjectName("Card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(12, 12, 12, 12)
        cl.setSpacing(8)
        self.preset_combo = QComboBox()
        self.preset_combo.setMaxVisibleItems(24)
        cl.addWidget(self.preset_combo)
        self.preset_desc = hint()
        cl.addWidget(self.preset_desc)
        row = QHBoxLayout()
        self.modified_label = hint("● Modified", "Warning")
        self.modified_label.setVisible(False)
        row.addWidget(self.modified_label)
        row.addStretch()
        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setObjectName("Flat")
        self.reset_btn.setToolTip("Restore the preset's settings")
        self.save_btn = QPushButton("Save as…")
        self.save_btn.setObjectName("Flat")
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setObjectName("Flat")
        for b in (self.reset_btn, self.save_btn, self.delete_btn):
            row.addWidget(b)
        cl.addLayout(row)
        lay.addWidget(card)

        # ---- size / quality --------------------------------------------------
        lay.addWidget(section("Compression"))
        seg = QHBoxLayout()
        seg.setSpacing(0)
        self.mode_group = QButtonGroup(self)
        for i, (mode, label) in enumerate(
            ((MODE_SIZE, "Target size"), (MODE_QUALITY, "Quality"), (MODE_BITRATE, "Bitrate"))
        ):
            b = QPushButton(label)
            b.setCheckable(True)
            b.setObjectName("SegmentFirst" if i == 0 else "SegmentLast" if i == 2 else "Segment")
            b.setProperty("mode", mode)
            self.mode_group.addButton(b, i)
            seg.addWidget(b)
        lay.addLayout(seg)

        self.mode_stack = QStackedWidget()
        # size page
        size_page = QWidget()
        sl = QVBoxLayout(size_page)
        sl.setContentsMargins(0, 4, 0, 0)
        r = QHBoxLayout()
        self.size_spin = QDoubleSpinBox()
        self.size_spin.setRange(0.5, 100000)
        self.size_spin.setDecimals(1)
        self.size_spin.setSuffix(" MB")
        self.size_spin.setSingleStep(0.5)
        r.addWidget(QLabel("Max file size"))
        r.addStretch()
        r.addWidget(self.size_spin)
        sl.addLayout(r)
        chips = QHBoxLayout()
        chips.setSpacing(6)
        for label, value in SIZE_CHIPS:
            b = QPushButton(label)
            b.setObjectName("Chip")
            b.clicked.connect(lambda _=False, v=value: self.size_spin.setValue(v))
            chips.addWidget(b)
        chips.addStretch()
        sl.addLayout(chips)
        sl.addWidget(hint("The bitrate is calculated from each clip's length, so every file lands "
                          "just under this size."))
        self.mode_stack.addWidget(size_page)
        # quality page
        q_page = QWidget()
        ql = QVBoxLayout(q_page)
        ql.setContentsMargins(0, 4, 0, 0)
        r = QHBoxLayout()
        self.crf_slider = QSlider(Qt.Horizontal)
        self.crf_spin = QSpinBox()
        self.crf_spin.setFixedWidth(60)
        self.crf_slider.valueChanged.connect(self.crf_spin.setValue)
        self.crf_spin.valueChanged.connect(self.crf_slider.setValue)
        r.addWidget(self.crf_slider, 1)
        r.addWidget(self.crf_spin)
        ql.addLayout(r)
        legend = QHBoxLayout()
        legend.addWidget(hint("Better quality"))
        legend.addStretch()
        legend.addWidget(hint("Smaller file"))
        ql.addLayout(legend)
        self.crf_hint = hint()
        ql.addWidget(self.crf_hint)
        self.mode_stack.addWidget(q_page)
        # bitrate page
        b_page = QWidget()
        bl = QVBoxLayout(b_page)
        bl.setContentsMargins(0, 4, 0, 0)
        r = QHBoxLayout()
        self.bitrate_spin = QSpinBox()
        self.bitrate_spin.setRange(50, 200000)
        self.bitrate_spin.setSingleStep(250)
        self.bitrate_spin.setSuffix(" kbps")
        r.addWidget(QLabel("Video bitrate"))
        r.addStretch()
        r.addWidget(self.bitrate_spin)
        bl.addLayout(r)
        bl.addWidget(hint("Average video bitrate. 1000 kbps ≈ 7.5 MB per minute."))
        self.mode_stack.addWidget(b_page)
        lay.addWidget(self.mode_stack)

        # ---- video -----------------------------------------------------------
        lay.addWidget(section("Video"))
        form = self._form()
        self.codec_combo = make_combo(CODECS)
        self.hw_combo = make_combo(HARDWARE)
        speed_row = QHBoxLayout()
        self.speed_slider = QSlider(Qt.Horizontal)
        self.speed_slider.setRange(0, len(SPEEDS) - 1)
        self.speed_slider.setPageStep(1)
        self.speed_label = QLabel()
        self.speed_label.setMinimumWidth(62)
        speed_row.addWidget(self.speed_slider, 1)
        speed_row.addWidget(self.speed_label)
        self.res_combo = make_combo(RESOLUTIONS)
        self.fps_combo = make_combo(FRAMERATES)
        self.two_pass_check = QCheckBox("Two-pass encoding (more accurate size)")
        form.addRow(field_label("Codec"), self.codec_combo)
        form.addRow(field_label("Encoder"), self.hw_combo)
        form.addRow(field_label("Speed"), speed_row)
        form.addRow(field_label("Resolution"), self.res_combo)
        form.addRow(field_label("Frame rate"), self.fps_combo)
        lay.addLayout(form)
        lay.addWidget(self.two_pass_check)
        self.video_hint = hint(name="Warning")
        self.video_hint.setVisible(False)
        lay.addWidget(self.video_hint)

        # ---- audio -----------------------------------------------------------
        lay.addWidget(section("Audio"))
        form = self._form()
        self.audio_combo = make_combo(AUDIO_CODECS)
        self.abitrate_combo = make_combo([(b, f"{b} kbps") for b in AUDIO_BITRATES])
        self.channels_combo = make_combo(CHANNELS)
        self.tracks_combo = make_combo(AUDIO_TRACKS)
        self.tracks_combo.setToolTip("Recordings from OBS and similar apps often have several audio "
                                     "tracks (game, mic, …). Mixing keeps all of them.")
        form.addRow(field_label("Codec"), self.audio_combo)
        form.addRow(field_label("Bitrate"), self.abitrate_combo)
        form.addRow(field_label("Channels"), self.channels_combo)
        form.addRow(field_label("Tracks"), self.tracks_combo)
        lay.addLayout(form)

        # ---- output ----------------------------------------------------------
        lay.addWidget(section("Output"))
        form = self._form()
        self.container_combo = make_combo(CONTAINERS)
        folder_row = QHBoxLayout()
        self.folder_edit = QLineEdit()
        self.folder_edit.setPlaceholderText("Same folder as the clip")
        self.folder_edit.setClearButtonEnabled(True)
        browse = QPushButton("…")
        browse.setFixedWidth(36)
        browse.clicked.connect(self._browse_folder)
        folder_row.addWidget(self.folder_edit, 1)
        folder_row.addWidget(browse)
        self.template_edit = QLineEdit()
        self.template_edit.setToolTip("{name} = original file name, {codec} = video codec")
        self.overwrite_combo = make_combo(OVERWRITE_MODES)
        form.addRow(field_label("Format"), self.container_combo)
        form.addRow(field_label("Folder"), folder_row)
        form.addRow(field_label("File name"), self.template_edit)
        form.addRow(field_label("If exists"), self.overwrite_combo)
        lay.addLayout(form)
        self.metadata_check = QCheckBox("Strip metadata")
        lay.addWidget(self.metadata_check)
        self.extra_edit = QLineEdit()
        self.extra_edit.setPlaceholderText("Extra FFmpeg arguments (advanced)")
        lay.addWidget(self.extra_edit)

        lay.addStretch()

        # ---- footer ----------------------------------------------------------
        footer = QWidget()
        footer.setObjectName("BottomBar")
        fl = QVBoxLayout(footer)
        fl.setContentsMargins(18, 12, 18, 12)
        fl.setSpacing(8)
        self.estimate_label = hint()
        fl.addWidget(self.estimate_label)
        self.error_label = hint(name="Warning")
        self.error_label.setVisible(False)
        fl.addWidget(self.error_label)
        self.apply_btn = QPushButton("Apply to selected clips")
        self.apply_btn.setToolTip("New clips always use these settings. Use this to update clips "
                                  "already in the queue.")
        fl.addWidget(self.apply_btn)
        outer.addWidget(footer)

        # ---- signals ---------------------------------------------------------
        self.preset_combo.currentIndexChanged.connect(self._on_preset_selected)
        self.reset_btn.clicked.connect(lambda: self._on_preset_selected(self.preset_combo.currentIndex()))
        self.save_btn.clicked.connect(self.save_preset_requested)
        self.delete_btn.clicked.connect(self.delete_preset_requested)
        self.apply_btn.clicked.connect(self.apply_to_selected)
        self.mode_group.idClicked.connect(self._on_mode_clicked)
        self.codec_combo.currentIndexChanged.connect(self._on_codec_changed)
        self.speed_slider.valueChanged.connect(self._update_speed_label)
        for w in (self.size_spin, self.crf_spin, self.bitrate_spin):
            w.valueChanged.connect(self._emit_changed)
        for w in (self.hw_combo, self.res_combo, self.fps_combo, self.audio_combo, self.abitrate_combo,
                  self.channels_combo, self.tracks_combo, self.container_combo, self.overwrite_combo):
            w.currentIndexChanged.connect(self._emit_changed)
        for w in (self.two_pass_check, self.metadata_check):
            w.toggled.connect(self._emit_changed)
        self.speed_slider.valueChanged.connect(self._emit_changed)
        for w in (self.folder_edit, self.template_edit, self.extra_edit):
            w.textChanged.connect(self._emit_changed)

    @staticmethod
    def _form() -> QFormLayout:
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(8)
        return form

    # ---- presets ---------------------------------------------------------------
    def set_presets(self, presets: List[Preset], selected: str) -> None:
        self._loading = True
        self._presets = presets
        self.preset_combo.clear()
        last_cat = None
        for preset in presets:
            cat = preset.category if preset.builtin else "My presets"
            if cat != last_cat and self.preset_combo.count():
                self.preset_combo.insertSeparator(self.preset_combo.count())
            last_cat = cat
            self.preset_combo.addItem(preset.name, preset.name)
        idx = self.preset_combo.findData(selected)
        self.preset_combo.setCurrentIndex(max(0, idx))
        self._loading = False
        self.refresh_preset_meta()

    def current_preset(self) -> Optional[Preset]:
        name = self.preset_combo.currentData()
        return next((p for p in self._presets if p.name == name), None)

    def preset_name(self) -> str:
        preset = self.current_preset()
        if not preset:
            return "Custom"
        return preset.name + (" *" if self.is_modified() else "")

    def is_modified(self) -> bool:
        preset = self.current_preset()
        return bool(preset) and preset.settings.to_dict() != self.settings().to_dict()

    def _on_preset_selected(self, _index: int) -> None:
        if self._loading:
            return
        preset = self.current_preset()
        if preset:
            self.set_settings(preset.settings)
        self.refresh_preset_meta()
        self.changed.emit()

    def refresh_preset_meta(self) -> None:
        preset = self.current_preset()
        self.preset_desc.setText(preset.description if preset else "")
        self.delete_btn.setVisible(bool(preset) and not preset.builtin)
        modified = self.is_modified()
        self.modified_label.setVisible(modified)
        self.reset_btn.setVisible(modified)

    # ---- settings <-> widgets --------------------------------------------------
    def set_settings(self, s: EncodeSettings) -> None:
        self._loading = True
        modes = [MODE_SIZE, MODE_QUALITY, MODE_BITRATE]
        mode_idx = modes.index(s.mode) if s.mode in modes else 0
        self.mode_group.button(mode_idx).setChecked(True)
        self.mode_stack.setCurrentIndex(mode_idx)
        self.size_spin.setValue(s.target_size_mb)
        set_combo(self.codec_combo, s.codec)
        self._apply_crf_range(s.codec)
        self.crf_spin.setValue(s.crf)
        self.bitrate_spin.setValue(s.video_bitrate_kbps)
        set_combo(self.hw_combo, s.hardware)
        self.speed_slider.setValue(s.speed)
        set_combo(self.res_combo, s.max_height)
        set_combo(self.fps_combo, s.max_fps)
        self.two_pass_check.setChecked(s.two_pass)
        set_combo(self.audio_combo, s.audio_codec)
        set_combo(self.abitrate_combo, s.audio_bitrate_kbps)
        set_combo(self.channels_combo, s.audio_channels)
        set_combo(self.tracks_combo, s.audio_tracks)
        set_combo(self.container_combo, s.container)
        self.metadata_check.setChecked(s.strip_metadata)
        self.extra_edit.setText(s.extra_args)
        self._loading = False
        self._update_speed_label()
        self._refresh_state()

    def settings(self) -> EncodeSettings:
        checked = self.mode_group.checkedButton()
        return EncodeSettings(
            mode=checked.property("mode") if checked else MODE_SIZE,
            target_size_mb=round(self.size_spin.value(), 2),
            crf=self.crf_spin.value(),
            video_bitrate_kbps=self.bitrate_spin.value(),
            codec=self.codec_combo.currentData(),
            hardware=self.hw_combo.currentData(),
            speed=self.speed_slider.value(),
            two_pass=self.two_pass_check.isChecked(),
            max_height=self.res_combo.currentData(),
            max_fps=self.fps_combo.currentData(),
            audio_codec=self.audio_combo.currentData(),
            audio_bitrate_kbps=self.abitrate_combo.currentData(),
            audio_channels=self.channels_combo.currentData(),
            audio_tracks=self.tracks_combo.currentData(),
            container=self.container_combo.currentData(),
            strip_metadata=self.metadata_check.isChecked(),
            extra_args=self.extra_edit.text(),
        )

    def set_output_options(self, folder: str, template: str, overwrite: str) -> None:
        self._loading = True
        self.folder_edit.setText(folder)
        self.template_edit.setText(template)
        set_combo(self.overwrite_combo, overwrite)
        self._loading = False

    def output_options(self):
        return (
            self.folder_edit.text().strip(),
            self.template_edit.text().strip() or "{name}_shrunk",
            self.overwrite_combo.currentData(),
        )

    def set_hardware_availability(self, available: Dict[str, bool]) -> None:
        self._hw_available = available
        model = self.hw_combo.model()
        for i in range(self.hw_combo.count()):
            key = self.hw_combo.itemData(i)
            ok = available.get(key, key == "cpu")
            label = HARDWARE[key] + ("" if ok else "  (not detected)")
            self.hw_combo.setItemText(i, label)
            item = model.item(i)
            if item is not None:
                item.setEnabled(ok or key == self.hw_combo.currentData())
        self._refresh_state()

    def set_estimate(self, text: str) -> None:
        self.estimate_label.setText(text)
        self.estimate_label.setVisible(bool(text))

    # ---- internal reactions ----------------------------------------------------
    def _browse_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Output folder", self.folder_edit.text())
        if folder:
            self.folder_edit.setText(folder)

    def _on_mode_clicked(self, idx: int) -> None:
        self.mode_stack.setCurrentIndex(idx)
        self._emit_changed()

    def _apply_crf_range(self, codec: str) -> None:
        lo, hi = CRF_RANGE.get(codec, (0, 51))
        for w in (self.crf_slider, self.crf_spin):
            w.setRange(lo, hi)
        self.crf_hint.setText(f"Recommended for {codec.upper()}: {DEFAULT_CRF.get(codec, 23)}. "
                              "Lower numbers keep more detail.")

    def _on_codec_changed(self) -> None:
        if self._loading:
            return
        codec = self.codec_combo.currentData()
        old_default = None
        for c, d in DEFAULT_CRF.items():
            if self.crf_spin.value() == d:
                old_default = c
        self._apply_crf_range(codec)
        if old_default:
            # The user was on a recommended value, so follow the new codec's recommendation.
            self.crf_spin.setValue(DEFAULT_CRF[codec])
        # Keep container/audio combinations valid.
        if codec in ("h264", "h265") and self.container_combo.currentData() == "webm":
            set_combo(self.container_combo, "mp4")
        if codec == "vp9" and self.container_combo.currentData() in ("mp4", "mov"):
            set_combo(self.container_combo, "webm")
        self._emit_changed()

    def _update_speed_label(self) -> None:
        self.speed_label.setText(SPEEDS[self.speed_slider.value()])

    def _emit_changed(self) -> None:
        if self._loading:
            return
        s = self.settings()
        if s.container == "webm" and s.audio_codec == "aac":
            self._loading = True
            set_combo(self.audio_combo, "opus")
            self._loading = False
        self._refresh_state()
        self.refresh_preset_meta()
        self.changed.emit()

    def _refresh_state(self) -> None:
        s = self.settings()
        audio_on = s.audio_codec not in ("none", "copy")
        self.abitrate_combo.setEnabled(audio_on)
        self.channels_combo.setEnabled(audio_on)
        self.tracks_combo.setEnabled(audio_on)
        two_pass_possible = s.mode != MODE_QUALITY and s.is_software and s.codec != "av1"
        self.two_pass_check.setEnabled(two_pass_possible)
        notes = []
        if s.mode == MODE_SIZE and not s.is_software:
            notes.append("Hardware encoders are less precise with size limits; clips are retried "
                         "automatically if they come out too big.")
        if s.hardware != "cpu" and self._hw_available and not self._hw_available.get(s.hardware):
            notes.append(f"{HARDWARE[s.hardware]} was not detected on this computer.")
        self.video_hint.setText("\n".join(notes))
        self.video_hint.setVisible(bool(notes))

        errors = validate(s)
        if not errors and (s.codec, s.hardware) not in ENCODERS:
            errors.append("This codec isn't available for the chosen encoder.")
        self.error_label.setText(errors[0] if errors else "")
        self.error_label.setVisible(bool(errors))
