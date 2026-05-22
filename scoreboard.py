#!/usr/bin/env python3
"""Rugby Scoreboard — Python/PyQt6 edition"""

import sys
import os
import json
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QTabWidget,
    QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QLineEdit, QSpinBox, QCheckBox,
    QGroupBox, QRadioButton, QMessageBox, QKeySequenceEdit,
    QSizePolicy, QStatusBar,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QKeySequence, QShortcut

# ── Constants ──────────────────────────────────────────────────────────────────
OUTPUT_DIR  = Path("Output")
CONFIG_FILE = Path("hotkeys.json")

TRY_POINTS        = 5
CONVERSION_POINTS = 2
PENALTY_POINTS    = 3
DROP_GOAL_POINTS  = 3

HALF_NAMES = {1: "1º Tempo", 2: "2º Tempo", 3: "Prorrogação", 4: "Prorrogação 2"}

DEFAULT_HOTKEYS: dict[str, str] = {
    "home_try":        "F1",
    "home_penalty":    "F2",
    "home_conversion": "F3",
    "home_drop":       "F4",
    "home_undo":       "F5",
    "timer_toggle":    "Space",
    "away_try":        "F7",
    "away_penalty":    "F6",
    "away_conversion": "F9",
    "away_drop":       "F8",
    "away_undo":       "F10",
    "timer_reset":     "Ctrl+R",
    "score_reset":     "Ctrl+0",
    "half_up":         "Ctrl+Up",
    "half_down":       "Ctrl+Down",
}

# Stream Deck 5×3 layout — (action_key, display_label, bg_color)
DECK_LAYOUT: list[tuple[str, str, str]] = [
    ("home_try",        "Home\nTRY +5",    "#1d6b2a"),
    ("home_penalty",    "Home\nPEN +3",    "#1a3d7a"),
    ("timer_toggle",    "START /\nSTOP",   "#4a4a5a"),
    ("away_penalty",    "Away\nPEN +3",    "#1a3d7a"),
    ("away_try",        "Away\nTRY +5",    "#1d6b2a"),
    ("home_conversion", "Home\nCNV +2",    "#7a5a1a"),
    ("home_drop",       "Home\nDRP +3",    "#5a1a7a"),
    ("timer_reset",     "RESET\nTEMPO",    "#4a2a00"),
    ("away_drop",       "Away\nDRP +3",    "#5a1a7a"),
    ("away_conversion", "Away\nCNV +2",    "#7a5a1a"),
    ("home_undo",       "Home\n−1",        "#7a1a1a"),
    ("half_up",         "TEMPO\nUP",       "#1a4a7a"),
    ("score_reset",     "RESET\nPLACAR",   "#5a0000"),
    ("half_down",       "TEMPO\nDOWN",     "#1a4a7a"),
    ("away_undo",       "Away\n−1",        "#7a1a1a"),
]

# Ordered list for the editable table (left col | right col)
ACTIONS_LEFT = [
    ("home_try",        "TRY Casa (+5)"),
    ("home_penalty",    "Penal Casa (+3)"),
    ("home_conversion", "Conversão Casa (+2)"),
    ("home_drop",       "Drop Casa (+3)"),
    ("home_undo",       "Desfazer Casa (−1)"),
    ("timer_toggle",    "Iniciar / Parar"),
    ("timer_reset",     "Reset Tempo"),
    ("score_reset",     "Reset Placar"),
]
ACTIONS_RIGHT = [
    ("away_try",        "TRY Visitante (+5)"),
    ("away_penalty",    "Penal Visitante (+3)"),
    ("away_conversion", "Conversão Visit. (+2)"),
    ("away_drop",       "Drop Visitante (+3)"),
    ("away_undo",       "Desfazer Visit. (−1)"),
    ("half_up",         "Próximo Tempo"),
    ("half_down",       "Tempo Anterior"),
]


# ── Main Window ────────────────────────────────────────────────────────────────
class ScoreboardApp(QMainWindow):

    def __init__(self) -> None:
        super().__init__()

        # Game state
        self.home_score  = 0
        self.away_score  = 0
        self.half        = 1
        self.home_name   = "Casa"
        self.away_name   = "Visitante"

        # Timer state
        self.timer_running   = False
        self.timer_minutes   = 40
        self.timer_seconds   = 0
        self.timer_direction = "countdown"  # "countdown" | "stopwatch"

        # Hotkey state
        self.hotkeys_enabled   = False
        self._keyboard_hooked  = False
        self._keyboard_handles: list = []      # handles from 'keyboard' lib
        self._shortcuts:        list[QShortcut] = []  # Qt fallback shortcuts

        # UI widget refs (set in _build_*)
        self._deck_buttons: dict[str, QPushButton]     = {}
        self._key_editors:  dict[str, QKeySequenceEdit] = {}

        self.hotkeys = self._load_hotkeys()

        self._qt_timer = QTimer(self)
        self._qt_timer.setInterval(1000)
        self._qt_timer.timeout.connect(self._tick)

        OUTPUT_DIR.mkdir(exist_ok=True)
        self._build_ui()
        self._apply_theme()
        self._refresh_clock_display()
        self._write_outputs()

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        self.setWindowTitle("Rugby Scoreboard 1.0")
        self.setMinimumSize(720, 540)

        root = QWidget()
        self.setCentralWidget(root)
        vbox = QVBoxLayout(root)
        vbox.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        vbox.addWidget(self.tabs)

        self._tab_scoreboard = QWidget()
        self._tab_settings   = QWidget()
        self._tab_hotkeys    = QWidget()

        self.tabs.addTab(self._tab_scoreboard, "Placar")
        self.tabs.addTab(self._tab_settings,   "Configurações")
        self.tabs.addTab(self._tab_hotkeys,    "Hotkeys / Stream Deck")

        self._build_scoreboard_tab()
        self._build_settings_tab()
        self._build_hotkeys_tab()

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Pronto")

    # ── Scoreboard tab ─────────────────────────────────────────────────────────

    def _build_scoreboard_tab(self) -> None:
        layout = QVBoxLayout(self._tab_scoreboard)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Team names
        names_row = QHBoxLayout()
        self._home_name_input = QLineEdit("Casa")
        self._home_name_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._home_name_input.setMaximumWidth(160)

        self._half_label = QLabel(HALF_NAMES[1])
        self._half_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._half_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))

        self._away_name_input = QLineEdit("Visitante")
        self._away_name_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._away_name_input.setMaximumWidth(160)

        names_row.addWidget(self._home_name_input)
        names_row.addStretch()
        names_row.addWidget(self._half_label)
        names_row.addStretch()
        names_row.addWidget(self._away_name_input)
        layout.addLayout(names_row)

        # Main area
        main_area = QHBoxLayout()
        main_area.setSpacing(12)
        main_area.addLayout(self._build_team_panel("home"), stretch=2)
        main_area.addLayout(self._build_center_panel(),    stretch=3)
        main_area.addLayout(self._build_team_panel("away"), stretch=2)
        layout.addLayout(main_area)

        # Bottom bar
        bar = QHBoxLayout()
        bar.setSpacing(6)

        btn_update = QPushButton("Atualizar Times")
        btn_update.clicked.connect(self._update_team_names)

        btn_reset_timer = QPushButton("Reset Tempo")
        btn_reset_timer.clicked.connect(self._reset_timer)

        self._btn_start = QPushButton("▶  Iniciar")
        self._btn_start.setMinimumHeight(44)
        self._btn_start.setMinimumWidth(120)
        self._btn_start.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        self._btn_start.setObjectName("startButton")
        self._btn_start.clicked.connect(self._toggle_timer)

        btn_reset_score = QPushButton("Reset Placar")
        btn_reset_score.clicked.connect(self._reset_score)

        btn_swap = QPushButton("↔  Trocar")
        btn_swap.clicked.connect(self._swap_teams)

        for b in [btn_update, btn_reset_timer, btn_reset_score, btn_swap]:
            b.setMinimumHeight(36)

        bar.addWidget(btn_update)
        bar.addWidget(btn_reset_timer)
        bar.addWidget(self._btn_start)
        bar.addWidget(btn_reset_score)
        bar.addWidget(btn_swap)
        layout.addLayout(bar)

    def _build_team_panel(self, side: str) -> QVBoxLayout:
        panel = QVBoxLayout()
        panel.setSpacing(6)
        panel.setAlignment(Qt.AlignmentFlag.AlignTop)

        score = QLabel("0")
        score.setFont(QFont("Arial", 64, QFont.Weight.Bold))
        score.setAlignment(Qt.AlignmentFlag.AlignCenter)
        score.setMinimumHeight(100)

        if side == "home":
            self._home_score_label = score
        else:
            self._away_score_label = score
        panel.addWidget(score)

        btn_try = QPushButton(f"TRY  +{TRY_POINTS}")
        btn_try.setMinimumHeight(44)
        btn_try.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        btn_try.setObjectName("btnTry")
        panel.addWidget(btn_try)

        row1 = QHBoxLayout()
        btn_pen = QPushButton(f"PEN\n+{PENALTY_POINTS}")
        btn_cnv = QPushButton(f"CNV\n+{CONVERSION_POINTS}")
        btn_pen.setObjectName("btnPen")
        btn_cnv.setObjectName("btnCnv")
        for b in [btn_pen, btn_cnv]:
            b.setMinimumHeight(42)
        row1.addWidget(btn_pen)
        row1.addWidget(btn_cnv)
        panel.addLayout(row1)

        row2 = QHBoxLayout()
        btn_drp  = QPushButton(f"DRP\n+{DROP_GOAL_POINTS}")
        btn_undo = QPushButton("−1")
        btn_drp.setObjectName("btnDrp")
        btn_undo.setObjectName("btnUndo")
        for b in [btn_drp, btn_undo]:
            b.setMinimumHeight(42)
        row2.addWidget(btn_drp)
        row2.addWidget(btn_undo)
        panel.addLayout(row2)

        if side == "home":
            btn_try.clicked.connect(lambda: self._add_score("home", TRY_POINTS))
            btn_pen.clicked.connect(lambda: self._add_score("home", PENALTY_POINTS))
            btn_cnv.clicked.connect(lambda: self._add_score("home", CONVERSION_POINTS))
            btn_drp.clicked.connect(lambda: self._add_score("home", DROP_GOAL_POINTS))
            btn_undo.clicked.connect(lambda: self._add_score("home", -1))
        else:
            btn_try.clicked.connect(lambda: self._add_score("away", TRY_POINTS))
            btn_pen.clicked.connect(lambda: self._add_score("away", PENALTY_POINTS))
            btn_cnv.clicked.connect(lambda: self._add_score("away", CONVERSION_POINTS))
            btn_drp.clicked.connect(lambda: self._add_score("away", DROP_GOAL_POINTS))
            btn_undo.clicked.connect(lambda: self._add_score("away", -1))

        return panel

    def _build_center_panel(self) -> QVBoxLayout:
        panel = QVBoxLayout()
        panel.setSpacing(8)
        panel.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._clock_label = QLabel("40:00")
        self._clock_label.setFont(QFont("Arial", 42, QFont.Weight.Bold))
        self._clock_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._clock_label.setObjectName("clockLabel")
        panel.addWidget(self._clock_label)

        half_row = QHBoxLayout()
        btn_half_down = QPushButton("▽")
        btn_half_down.setFixedSize(36, 36)
        btn_half_down.setToolTip("Tempo anterior")
        btn_half_down.clicked.connect(lambda: self._change_half(-1))

        half_label_static = QLabel("Tempo")
        half_label_static.setAlignment(Qt.AlignmentFlag.AlignCenter)

        btn_half_up = QPushButton("△")
        btn_half_up.setFixedSize(36, 36)
        btn_half_up.setToolTip("Próximo tempo")
        btn_half_up.clicked.connect(lambda: self._change_half(1))

        half_row.addWidget(btn_half_down)
        half_row.addStretch()
        half_row.addWidget(half_label_static)
        half_row.addStretch()
        half_row.addWidget(btn_half_up)
        panel.addLayout(half_row)

        timer_group = QGroupBox("Configurar Tempo")
        timer_grid = QGridLayout(timer_group)
        timer_grid.setSpacing(6)

        timer_grid.addWidget(QLabel("Min"), 0, 0)
        self._min_spin = QSpinBox()
        self._min_spin.setRange(0, 99)
        self._min_spin.setValue(40)
        self._min_spin.valueChanged.connect(self._on_timer_input_changed)
        timer_grid.addWidget(self._min_spin, 0, 1)

        timer_grid.addWidget(QLabel("Seg"), 1, 0)
        self._sec_spin = QSpinBox()
        self._sec_spin.setRange(0, 59)
        self._sec_spin.setValue(0)
        self._sec_spin.valueChanged.connect(self._on_timer_input_changed)
        timer_grid.addWidget(self._sec_spin, 1, 1)

        panel.addWidget(timer_group)
        return panel

    # ── Settings tab ───────────────────────────────────────────────────────────

    def _build_settings_tab(self) -> None:
        layout = QVBoxLayout(self._tab_settings)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self._always_top_cb = QCheckBox("Sempre visível (Always on Top)")
        self._always_top_cb.toggled.connect(self._toggle_always_on_top)
        layout.addWidget(self._always_top_cb)

        mode_group = QGroupBox("Modo do Cronômetro")
        mode_layout = QVBoxLayout(mode_group)
        self._countdown_rb = QRadioButton("Contagem regressiva — padrão Rugby (ex: 40:00 → 00:00)")
        self._stopwatch_rb = QRadioButton("Cronômetro — conta crescente (00:00 → ∞)")
        self._countdown_rb.setChecked(True)
        self._countdown_rb.toggled.connect(self._on_timer_mode_changed)
        mode_layout.addWidget(self._countdown_rb)
        mode_layout.addWidget(self._stopwatch_rb)
        layout.addWidget(mode_group)

        preset_group = QGroupBox("Presets de Duração do Tempo")
        preset_row = QHBoxLayout(preset_group)
        for label, mins in [("10 min", 10), ("20 min", 20), ("40 min", 40), ("80 min (Jogo)", 80)]:
            btn = QPushButton(label)
            btn.setMinimumHeight(34)
            btn.clicked.connect(lambda _, m=mins: self._set_preset(m))
            preset_row.addWidget(btn)
        layout.addWidget(preset_group)

        obs_group = QGroupBox("Saída para OBS (arquivos de texto)")
        obs_layout = QVBoxLayout(obs_group)
        obs_layout.addWidget(QLabel(f"Arquivos gravados em: ./{OUTPUT_DIR}/"))
        for name in ("Home_Score.txt", "Away_Score.txt", "Home_Name.txt",
                     "Away_Name.txt", "Half.txt", "Clock.txt"):
            obs_layout.addWidget(QLabel(f"    • {name}"))
        obs_layout.addWidget(QLabel(""))
        obs_layout.addWidget(QLabel(
            "No OBS: Adicionar fonte → Texto → Ler de arquivo → selecione o .txt desejado."
        ))
        layout.addWidget(obs_group)
        layout.addStretch()

    # ── Hotkeys tab ────────────────────────────────────────────────────────────

    def _build_hotkeys_tab(self) -> None:
        layout = QVBoxLayout(self._tab_hotkeys)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        # Enable toggle
        self._hotkeys_cb = QCheckBox(
            "Ativar Hotkeys  "
            "(funciona em background com 'keyboard';  fallback Qt quando app está focado)"
        )
        self._hotkeys_cb.toggled.connect(self._toggle_hotkeys)
        layout.addWidget(self._hotkeys_cb)

        # ── Stream Deck visual grid ────────────────────────────────────────────
        deck_group = QGroupBox("Layout do Stream Deck — Rise Mode Vision 02  (15 teclas, 5×3)")
        deck_grid = QGridLayout(deck_group)
        deck_grid.setSpacing(4)

        for idx, (action, display, color) in enumerate(DECK_LAYOUT):
            key = self.hotkeys.get(action, "")
            btn = QPushButton(f"{key}\n{display}")
            btn.setFixedSize(120, 66)
            btn.setStyleSheet(
                f"background-color:{color}; color:#ffffff; "
                f"font-size:10px; font-weight:bold; border-radius:6px;"
            )
            btn.setEnabled(False)
            self._deck_buttons[action] = btn
            row, col = divmod(idx, 5)
            deck_grid.addWidget(btn, row, col)

        layout.addWidget(deck_group)

        # ── Editable hotkey table ──────────────────────────────────────────────
        edit_group = QGroupBox(
            "Editar Hotkeys — clique no campo e pressione a combinação desejada  "
            "(ex: Ctrl+F,  Shift+P,  F11…)"
        )
        edit_grid = QGridLayout(edit_group)
        edit_grid.setSpacing(5)
        edit_grid.setColumnStretch(1, 1)
        edit_grid.setColumnStretch(3, 0)   # gap
        edit_grid.setColumnStretch(4, 1)
        edit_grid.setColumnStretch(5, 1)

        # Header
        for col, txt in [(0, "Ação"), (1, "Tecla"), (4, "Ação"), (5, "Tecla")]:
            h = QLabel(f"<b>{txt}</b>")
            h.setAlignment(Qt.AlignmentFlag.AlignCenter)
            edit_grid.addWidget(h, 0, col)

        for row, (action, label) in enumerate(ACTIONS_LEFT, start=1):
            lbl = QLabel(label)
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            edit_grid.addWidget(lbl, row, 0)

            editor = QKeySequenceEdit(QKeySequence(self.hotkeys.get(action, "")))
            editor.keySequenceChanged.connect(
                lambda seq, a=action: self._on_hotkey_changed(a, seq)
            )
            self._key_editors[action] = editor
            edit_grid.addWidget(editor, row, 1)

        for row, (action, label) in enumerate(ACTIONS_RIGHT, start=1):
            lbl = QLabel(label)
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            edit_grid.addWidget(lbl, row, 4)

            editor = QKeySequenceEdit(QKeySequence(self.hotkeys.get(action, "")))
            editor.keySequenceChanged.connect(
                lambda seq, a=action: self._on_hotkey_changed(a, seq)
            )
            self._key_editors[action] = editor
            edit_grid.addWidget(editor, row, 5)

        layout.addWidget(edit_group)

        # Restore defaults button
        btn_defaults = QPushButton("↺  Restaurar Padrões")
        btn_defaults.setMaximumWidth(200)
        btn_defaults.clicked.connect(self._reset_hotkeys_to_defaults)
        layout.addWidget(btn_defaults, alignment=Qt.AlignmentFlag.AlignRight)

        # Instructions
        info = QLabel(
            "<b>Como configurar o Stream Deck:</b><br>"
            "1. Edite os hotkeys acima — clique no campo e pressione a combinação (ex: Ctrl+F, Shift+P)<br>"
            "2. No software do Stream Deck: crie perfil 'Rugby' → para cada tecla adicione "
            "ação <i>Tecla de Atalho</i> com o atalho escolhido acima<br>"
            "3. Ative os hotkeys (caixa acima) — para funcionar em background instale: "
            "<code>pip install keyboard</code><br>"
            "4. Stream Deck envia o atalho → app recebe → placar/tempo atualiza automaticamente"
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        layout.addStretch()

    # ── Hotkey change handlers ─────────────────────────────────────────────────

    def _on_hotkey_changed(self, action: str, seq: QKeySequence) -> None:
        key_str = seq.toString(QKeySequence.SequenceFormat.PortableText)
        self.hotkeys[action] = key_str
        self._update_deck_button(action)
        self._save_hotkeys()
        if self.hotkeys_enabled:
            self._register_hotkeys()

    def _update_deck_button(self, action: str) -> None:
        btn = self._deck_buttons.get(action)
        if btn is None:
            return
        display = next((d for a, d, _ in DECK_LAYOUT if a == action), action)
        key = self.hotkeys.get(action, "")
        btn.setText(f"{key}\n{display}")

    def _update_all_deck_buttons(self) -> None:
        for action in self._deck_buttons:
            self._update_deck_button(action)

    def _reset_hotkeys_to_defaults(self) -> None:
        self.hotkeys = dict(DEFAULT_HOTKEYS)
        for action, editor in self._key_editors.items():
            editor.blockSignals(True)
            editor.setKeySequence(QKeySequence(self.hotkeys.get(action, "")))
            editor.blockSignals(False)
        self._update_all_deck_buttons()
        self._save_hotkeys()
        if self.hotkeys_enabled:
            self._register_hotkeys()
        self.status_bar.showMessage("Hotkeys restaurados para o padrão")

    # ── Logic: Scoring ─────────────────────────────────────────────────────────

    def _add_score(self, side: str, points: int) -> None:
        if side == "home":
            self.home_score = max(0, self.home_score + points)
            self._home_score_label.setText(str(self.home_score))
        else:
            self.away_score = max(0, self.away_score + points)
            self._away_score_label.setText(str(self.away_score))
        action_name = {
            TRY_POINTS: "TRY", CONVERSION_POINTS: "Conversão",
            PENALTY_POINTS: "Penal", DROP_GOAL_POINTS: "Drop", -1: "Desfazer",
        }.get(points, f"+{points}")
        team = self.home_name if side == "home" else self.away_name
        self.status_bar.showMessage(
            f"{team}: {action_name}  →  {self.home_score} × {self.away_score}"
        )
        self._write_outputs()

    def _reset_score(self) -> None:
        self.home_score = 0
        self.away_score = 0
        self._home_score_label.setText("0")
        self._away_score_label.setText("0")
        self.status_bar.showMessage("Placar zerado")
        self._write_outputs()

    def _update_team_names(self) -> None:
        self.home_name = self._home_name_input.text().strip() or "Casa"
        self.away_name = self._away_name_input.text().strip() or "Visitante"
        self.status_bar.showMessage(f"Times: {self.home_name} × {self.away_name}")
        self._write_outputs()

    def _swap_teams(self) -> None:
        self.home_score, self.away_score = self.away_score, self.home_score
        self.home_name,  self.away_name  = self.away_name,  self.home_name
        self._home_score_label.setText(str(self.home_score))
        self._away_score_label.setText(str(self.away_score))
        self._home_name_input.setText(self.home_name)
        self._away_name_input.setText(self.away_name)
        self.status_bar.showMessage("Times trocados")
        self._write_outputs()

    def _change_half(self, delta: int) -> None:
        self.half = max(1, self.half + delta)
        self._half_label.setText(HALF_NAMES.get(self.half, f"Tempo {self.half}"))
        self.status_bar.showMessage(HALF_NAMES.get(self.half, f"Tempo {self.half}"))
        self._write_outputs()

    # ── Logic: Timer ──────────────────────────────────────────────────────────

    def _toggle_timer(self) -> None:
        if self.timer_running:
            self._qt_timer.stop()
            self.timer_running = False
            self._btn_start.setText("▶  Iniciar")
            self.status_bar.showMessage("Tempo pausado")
        else:
            self._qt_timer.start()
            self.timer_running = True
            self._btn_start.setText("⏸  Parar")
            self.status_bar.showMessage("Cronômetro rodando…")

    def _tick(self) -> None:
        if self.timer_direction == "countdown":
            if self.timer_seconds > 0:
                self.timer_seconds -= 1
            elif self.timer_minutes > 0:
                self.timer_minutes -= 1
                self.timer_seconds = 59
            else:
                self._qt_timer.stop()
                self.timer_running = False
                self._btn_start.setText("▶  Iniciar")
                self.status_bar.showMessage("⏱ Tempo esgotado!")
        else:
            self.timer_seconds += 1
            if self.timer_seconds >= 60:
                self.timer_seconds = 0
                self.timer_minutes += 1

        self._refresh_clock_display()
        self._write_outputs()

    def _reset_timer(self) -> None:
        if self.timer_running:
            self.status_bar.showMessage("Pare o cronômetro antes de resetar")
            return
        self.timer_minutes = self._min_spin.value()
        self.timer_seconds = self._sec_spin.value()
        self._refresh_clock_display()
        self.status_bar.showMessage("Tempo resetado")
        self._write_outputs()

    def _on_timer_input_changed(self) -> None:
        if not self.timer_running:
            self.timer_minutes = self._min_spin.value()
            self.timer_seconds = self._sec_spin.value()
            self._refresh_clock_display()
            self._write_outputs()

    def _refresh_clock_display(self) -> None:
        self._clock_label.setText(f"{self.timer_minutes:02d}:{self.timer_seconds:02d}")

    def _on_timer_mode_changed(self) -> None:
        self.timer_direction = "countdown" if self._countdown_rb.isChecked() else "stopwatch"

    def _set_preset(self, minutes: int) -> None:
        self._min_spin.setValue(minutes)
        self._sec_spin.setValue(0)
        if not self.timer_running:
            self.timer_minutes = minutes
            self.timer_seconds = 0
            self._refresh_clock_display()
        self.status_bar.showMessage(f"Preset: {minutes} minutos")

    # ── Logic: Settings ────────────────────────────────────────────────────────

    def _toggle_always_on_top(self, on: bool) -> None:
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, on)
        self.show()

    # ── Logic: Hotkeys ─────────────────────────────────────────────────────────

    def _toggle_hotkeys(self, enabled: bool) -> None:
        self.hotkeys_enabled = enabled
        if enabled:
            self._register_hotkeys()
        else:
            self._unregister_hotkeys()

    def _action_map(self) -> dict:
        return {
            "home_try":        lambda: self._add_score("home", TRY_POINTS),
            "home_penalty":    lambda: self._add_score("home", PENALTY_POINTS),
            "home_conversion": lambda: self._add_score("home", CONVERSION_POINTS),
            "home_drop":       lambda: self._add_score("home", DROP_GOAL_POINTS),
            "home_undo":       lambda: self._add_score("home", -1),
            "away_try":        lambda: self._add_score("away", TRY_POINTS),
            "away_penalty":    lambda: self._add_score("away", PENALTY_POINTS),
            "away_conversion": lambda: self._add_score("away", CONVERSION_POINTS),
            "away_drop":       lambda: self._add_score("away", DROP_GOAL_POINTS),
            "away_undo":       lambda: self._add_score("away", -1),
            "timer_toggle":    self._toggle_timer,
            "timer_reset":     self._reset_timer,
            "score_reset":     self._reset_score,
            "half_up":         lambda: self._change_half(1),
            "half_down":       lambda: self._change_half(-1),
        }

    def _register_hotkeys(self) -> None:
        # ── Try global 'keyboard' library first ───────────────────────────────
        try:
            import keyboard as kb

            # Remove previously registered handles individually (avoids unhook_all bug)
            for handle in self._keyboard_handles:
                try:
                    kb.remove_hotkey(handle)
                except Exception:
                    pass
            self._keyboard_handles.clear()

            for action, callback in self._action_map().items():
                key_str = self.hotkeys.get(action, "")
                if not key_str:
                    continue
                kb_key = self._qt_key_to_kb(key_str)
                try:
                    handle = kb.add_hotkey(kb_key, callback)
                    self._keyboard_handles.append(handle)
                except Exception:
                    pass  # skip invalid/unsupported combos silently

            self._keyboard_hooked = True
            self.status_bar.showMessage("✓ Hotkeys globais ativados (biblioteca 'keyboard')")
            return

        except ImportError:
            pass
        except Exception as exc:
            self.status_bar.showMessage(f"'keyboard' indisponível — usando Qt shortcuts. ({exc})")

        # ── Fallback: Qt shortcuts (focused window only) ───────────────────────
        self._register_qt_shortcuts()
        self.status_bar.showMessage("✓ Hotkeys Qt ativados (funcionam com a janela focada)")

    def _register_qt_shortcuts(self) -> None:
        for sc in self._shortcuts:
            sc.setEnabled(False)
        self._shortcuts.clear()

        for action, callback in self._action_map().items():
            key_str = self.hotkeys.get(action, "")
            if not key_str:
                continue
            try:
                sc = QShortcut(QKeySequence(key_str), self)
                sc.activated.connect(callback)
                self._shortcuts.append(sc)
            except Exception:
                pass

    def _unregister_hotkeys(self) -> None:
        if self._keyboard_hooked:
            try:
                import keyboard as kb
                for handle in self._keyboard_handles:
                    try:
                        kb.remove_hotkey(handle)
                    except Exception:
                        pass
                self._keyboard_handles.clear()
            except Exception:
                pass
            self._keyboard_hooked = False

        for sc in self._shortcuts:
            sc.setEnabled(False)
        self._shortcuts.clear()

        self.hotkeys_enabled = False
        self.status_bar.showMessage("Hotkeys desativados")

    @staticmethod
    def _qt_key_to_kb(qt_key: str) -> str:
        """Convert Qt portable key sequence string to 'keyboard' lib format."""
        special = {
            "Return": "enter", "Escape": "esc", "Delete": "delete",
            "Backspace": "backspace", "Tab": "tab", "Space": "space",
            "Up": "up", "Down": "down", "Left": "left", "Right": "right",
            "PageUp": "page up", "PageDown": "page down",
            "Home": "home", "End": "end", "Insert": "insert",
            "Plus": "+", "Minus": "-",
        }
        result = qt_key
        for qt_name, kb_name in special.items():
            result = result.replace(qt_name, kb_name)
        return result.lower()

    # ── Config persistence ─────────────────────────────────────────────────────

    def _load_hotkeys(self) -> dict[str, str]:
        if CONFIG_FILE.exists():
            try:
                saved = json.loads(CONFIG_FILE.read_text())
                return {**DEFAULT_HOTKEYS, **saved}
            except Exception:
                pass
        return dict(DEFAULT_HOTKEYS)

    def _save_hotkeys(self) -> None:
        try:
            CONFIG_FILE.write_text(json.dumps(self.hotkeys, indent=2))
        except Exception:
            pass

    # ── OBS output ────────────────────────────────────────────────────────────

    def _write_outputs(self) -> None:
        OUTPUT_DIR.mkdir(exist_ok=True)
        files = {
            "Home_Score.txt": str(self.home_score),
            "Away_Score.txt": str(self.away_score),
            "Home_Name.txt":  self.home_name,
            "Away_Name.txt":  self.away_name,
            "Half.txt":       HALF_NAMES.get(self.half, str(self.half)),
            "Clock.txt":      f"{self.timer_minutes:02d}:{self.timer_seconds:02d}",
        }
        for name, content in files.items():
            try:
                (OUTPUT_DIR / name).write_text(content, encoding="utf-8")
            except OSError:
                pass

    # ── Theme ─────────────────────────────────────────────────────────────────

    def _apply_theme(self) -> None:
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #1e1e2e;
                color: #cdd6f4;
                font-family: Arial, sans-serif;
            }
            QTabWidget::pane { border: 1px solid #45475a; }
            QTabBar::tab {
                background: #313244; color: #cdd6f4;
                padding: 7px 18px; border: 1px solid #45475a; border-bottom: none;
            }
            QTabBar::tab:selected { background: #45475a; color: #ffffff; }
            QPushButton {
                background: #313244; color: #cdd6f4;
                border: 1px solid #45475a; border-radius: 5px;
                padding: 4px 10px; min-height: 28px;
            }
            QPushButton:hover   { background: #45475a; }
            QPushButton:pressed { background: #585b70; }
            QPushButton#startButton {
                background: #1e6b1e; color: #ffffff;
                border: 1px solid #28a828; font-weight: bold;
            }
            QPushButton#startButton:hover { background: #248a24; }
            QPushButton#btnTry  { background: #1d6b2a; color: #fff; border-color: #28a040; }
            QPushButton#btnTry:hover  { background: #258035; }
            QPushButton#btnPen  { background: #1a3d7a; color: #fff; border-color: #2a5ab0; }
            QPushButton#btnPen:hover  { background: #1f4a96; }
            QPushButton#btnCnv  { background: #7a5a1a; color: #fff; border-color: #a07820; }
            QPushButton#btnCnv:hover  { background: #906820; }
            QPushButton#btnDrp  { background: #5a1a7a; color: #fff; border-color: #7a28a0; }
            QPushButton#btnDrp:hover  { background: #6a208a; }
            QPushButton#btnUndo { background: #7a1a1a; color: #fff; border-color: #a02020; }
            QPushButton#btnUndo:hover { background: #8a2020; }
            QLabel            { color: #cdd6f4; }
            QLabel#clockLabel { color: #f5c842; }
            QLineEdit, QSpinBox, QKeySequenceEdit {
                background: #313244; color: #cdd6f4;
                border: 1px solid #45475a; border-radius: 4px; padding: 4px;
            }
            QKeySequenceEdit:focus { border-color: #89b4fa; }
            QGroupBox {
                border: 1px solid #45475a; border-radius: 5px;
                margin-top: 10px; padding-top: 6px;
                color: #89b4fa; font-weight: bold;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; }
            QCheckBox, QRadioButton { color: #cdd6f4; spacing: 6px; }
            QStatusBar { background: #181825; color: #a6adc8; font-size: 11px; }
        """)

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def closeEvent(self, event) -> None:
        self._unregister_hotkeys()
        self._save_hotkeys()
        super().closeEvent(event)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Rugby Scoreboard")
    window = ScoreboardApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
