import sys
import os
import json
import threading
import asyncio
import webbrowser
import logging
import traceback
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
    QTabWidget, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QSlider, 
    QProgressBar, QScrollArea, QCheckBox, QFileDialog, QFrame, QSizePolicy, 
    QComboBox, QMenu, QSpinBox, QDialog, QListWidget, QInputDialog, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QObject, QTimer, QUrl
from PySide6.QtGui import QPixmap
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

from core import config, database, director, scraper
from core.logger import get_logger

DARK_STYLESHEET = """
QMainWindow, QWidget, QDialog { background-color: #1e1e1e; color: #ecf0f1; font-family: 'Segoe UI', Arial, sans-serif; }
QTabWidget::pane { border: 1px solid #3a3a3a; background: #1e1e1e; }
QTabBar::tab { background: #2d2d2d; color: #95a5a6; padding: 10px 20px; border: 1px solid #3a3a3a; border-bottom: none; }
QTabBar::tab:selected { background: #8b0000; color: white; font-weight: bold; }
QTabBar::tab:hover:!selected { background: #a52a2a; color: white; }
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QListWidget { background-color: #121212; border: 1px solid #3a3a3a; color: #ffffff; padding: 5px; }
QComboBox::drop-down { border-left: 1px solid #3a3a3a; }
QPushButton { background-color: #2c3e50; color: white; padding: 8px; border: none; font-weight: bold; }
QPushButton:hover { background-color: #34495e; }
QPushButton:disabled { background-color: #555555; color: #888888; }
QProgressBar { border: 1px solid #3a3a3a; background-color: #121212; text-align: center; color: white; }
QProgressBar::chunk { background-color: #e67e22; }
QSlider::groove:horizontal { border: 1px solid #3a3a3a; height: 8px; background: #121212; margin: 2px 0; }
QSlider::handle:horizontal { background: #8b0000; border: 1px solid #5c0000; width: 18px; margin: -2px 0; border-radius: 3px; }
QScrollArea { border: none; background-color: transparent; }
QScrollArea > QWidget > QWidget { background-color: transparent; }
QCheckBox { color: #e67e22; font-weight: bold; }
QMenu { background-color: #2d2d2d; border: 1px solid #3a3a3a; }
QMenu::item { padding: 5px 20px; }
QMenu::item:selected { background-color: #e67e22; }
"""

COLOR_BLOOD = "#8b0000"
COLOR_HAZARD = "#e67e22"
COLOR_TOXIC = "#2c5e1a"
COLOR_STEEL = "#2c3e50"
COLOR_TEXT_MUTED = "#95a5a6"

SLOT_GROUPS = {
    "The Survivors": ["Bill", "Zoey", "Francis", "Louis", "Coach", "Ellis", "Nick", "Rochelle"],
    "The Infected": ["Tank", "Boomer", "Smoker", "Hunter", "Jockey", "Charger", "Spitter", "Witch", "Common Infected", "Uncommon Infected"],
    "Primary Firearms": ["AK-47", "Assault Rifle (M16)", "Desert Rifle (SCAR)", "SG552", "SMG (Uzi)", "Silenced SMG", "MP5", "Pump Shotgun", "Chrome Shotgun", "Auto Shotgun", "Combat Shotgun (SPAS-12)", "Hunting Rifle", "Military Sniper", "AWP", "Scout", "M60", "Grenade Launcher"],
    "Sidearms": ["Pistols", "Magnum"],
    "Melee Weapons": ["Fireaxe", "Katana", "Machete", "Knife", "Frying Pan", "Crowbar", "Baseball Bat", "Cricket Bat", "Golf Club", "Tonfa", "Shovel", "Pitchfork", "Guitar", "Chainsaw"],
    "Consumables": ["Medkit", "Pain Pills", "Adrenaline", "Defibrillator", "Pipe Bomb", "Molotov", "Boomer Bile"],
    "World Items": ["Ammo Pile", "Gas Can", "Propane Tank", "Oxygen Tank", "Gnome"],
    "UI & Experience": ["Menus & Loading", "Icons & HUD", "Misc UI"],
    "Environment & FX": ["Concert Props", "Vehicles", "World Props", "Combat Music", "Infected Cues", "Game States", "Gore", "Infected FX", "Environment FX"]
}

COMPACT_SLOTS = [
    "Bill", "Zoey", "Francis", "Louis", "Coach", "Ellis", "Nick", "Rochelle",
    "Tank", "Boomer", "Smoker", "Hunter", "Jockey", "Charger", "Spitter", "Witch",
    "AK-47", "Assault Rifle (M16)", "Pump Shotgun", "Auto Shotgun", "Military Sniper", "SMG (Uzi)",
    "Medkit", "Pain Pills", "Pipe Bomb", "Molotov", "Boomer Bile"
]

class ImageManager(QObject):
    def __init__(self):
        super().__init__()
        self.manager = QNetworkAccessManager(self)
        self.cache = {}
        
    def load_image(self, url, label_widget):
        if not url:
            label_widget.setPixmap(QPixmap())
            return
            
        if url in self.cache:
            label_widget.setPixmap(self.cache[url])
            return
            
        request = QNetworkRequest(QUrl(url))
        reply = self.manager.get(request)
        
        def on_finished():
            if reply.error() == QNetworkReply.NoError:
                img_data = reply.readAll()
                pixmap = QPixmap()
                pixmap.loadFromData(img_data)
                pixmap = pixmap.scaled(40, 40, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                self.cache[url] = pixmap
                label_widget.setPixmap(pixmap)
            reply.deleteLater()
            
        reply.finished.connect(on_finished)

class AppSignals(QObject):
    progress = Signal(str, float)
    stats = Signal(dict)
    scrape_log = Signal(str)
    sys_log = Signal(str)
    prune_msg = Signal(str, bool)
    refresh_ui = Signal()
    generation_complete = Signal()
    deploy_complete = Signal()

class QtLogHandler(logging.Handler):
    def __init__(self, signal):
        super().__init__()
        self.signal = signal
        self.setFormatter(logging.Formatter('[%(levelname)s] %(name)s: %(message)s'))

    def emit(self, record):
        msg = self.format(record)
        self.signal.emit(msg)

log = get_logger("UI_Main")

class AssetInspectorDialog(QDialog):
    def __init__(self, mod_id, mod_title, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Deep-Scan X-Ray visualizer")
        self.resize(500, 400)
        
        layout = QVBoxLayout(self)
        
        title_lbl = QLabel(f"Assets mapped inside:\n{mod_title}")
        title_lbl.setStyleSheet(f"color: {COLOR_HAZARD}; font-weight: bold; font-size: 14px;")
        layout.addWidget(title_lbl)
        
        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        
        self.load_assets(mod_id)
        
    def load_assets(self, mod_id):
        mod_item = database.get_mod_by_id(mod_id)
        if mod_item and mod_item.eval.raw_paths:
            for path in mod_item.eval.raw_paths:
                self.list_widget.addItem(path)
        else:
            self.list_widget.addItem("No raw path data available.")
            self.list_widget.addItem("(Mod was cached before the Inspector update, or has no assets).")


class L4D2RandomizerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("L4D2 Mod Director (VPK Engine)")
        self.resize(1150, 750)
        self.setStyleSheet(DARK_STYLESHEET)

        database.init_pool_db()

        self.mixed_pool = []
        self.current_assignments = {}
        self.current_selected_ids = []
        self.show_advanced = False
        self.blend_mode = -1.0 
        self.ui_initialized = False
        self.image_manager = ImageManager()

        self.signals = AppSignals()
        self.signals.progress.connect(self.update_progress_ui)
        self.signals.stats.connect(self.update_stats_ui)
        self.signals.scrape_log.connect(self.append_scrape_log_ui)
        self.signals.sys_log.connect(self.append_sys_log_ui)
        self.signals.refresh_ui.connect(self.refresh_ui_view)
        self.signals.generation_complete.connect(self._enable_post_gen_ui)
        self.signals.deploy_complete.connect(self.on_deploy_complete)
        self.signals.prune_msg.connect(self.update_prune_msg)

        qt_handler = QtLogHandler(self.signals.sys_log)
        qt_handler.setLevel(logging.INFO)
        logging.getLogger().addHandler(qt_handler)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.tab_director = QWidget()
        self.tab_scraper = QWidget()
        self.tab_settings = QWidget()
        self.tab_sys_logs = QWidget()

        self.tabs.addTab(self.tab_director, "The Director")
        self.tabs.addTab(self.tab_scraper, "Passive Scraper")
        self.tabs.addTab(self.tab_settings, "Settings & Maintenance")
        self.tabs.addTab(self.tab_sys_logs, "System Logs")

        self.setup_settings_tab()
        self.setup_director_tab()
        self.setup_scraper_tab()
        self.setup_sys_logs_tab()

        log.info("Application Initialized. Optimized SQLite Database & Engine Filters active.")

    def setup_settings_tab(self):
        layout = QGridLayout(self.tab_settings)

        config_group = QFrame()
        config_layout = QVBoxLayout(config_group)
        lbl_api_title = QLabel("API & Sync Credentials")
        lbl_api_title.setStyleSheet(f"color: {COLOR_HAZARD}; font-size: 16px; font-weight: bold;")
        config_layout.addWidget(lbl_api_title)

        self.cfg_api = QLineEdit(config.USER_CONFIG.get("STEAM_API_KEY", ""))
        config_layout.addWidget(QLabel("Steam API Key:"))
        config_layout.addWidget(self.cfg_api)

        self.cfg_col = QLineEdit(config.USER_CONFIG.get("COLLECTION_ID", ""))
        config_layout.addWidget(QLabel("Collection ID:"))
        config_layout.addWidget(self.cfg_col)

        self.cfg_ses = QLineEdit(config.USER_CONFIG.get("SESSION_ID", ""))
        config_layout.addWidget(QLabel("Session ID:"))
        config_layout.addWidget(self.cfg_ses)

        self.cfg_sec = QLineEdit(config.USER_CONFIG.get("STEAM_LOGIN_SECURE", ""))
        self.cfg_sec.setEchoMode(QLineEdit.Password)
        config_layout.addWidget(QLabel("Steam Login Secure:"))
        config_layout.addWidget(self.cfg_sec)
        
        self.chk_allow_packs = QCheckBox("Allow Multi-Item Packs (Bypass >7 Tag Limit)")
        self.chk_allow_packs.setChecked(config.USER_CONFIG.get("ALLOW_PACKS", False))
        config_layout.addWidget(self.chk_allow_packs)

        config_layout.addStretch()

        qol_group = QFrame()
        qol_layout = QVBoxLayout(qol_group)
        lbl_qol_title = QLabel("Always Include (QOL Mods)")
        lbl_qol_title.setStyleSheet(f"color: {COLOR_HAZARD}; font-size: 16px; font-weight: bold;")
        qol_layout.addWidget(lbl_qol_title)
        qol_layout.addWidget(QLabel("Enter Workshop IDs (one per line):"))
        self.cfg_qol = QPlainTextEdit("\n".join(config.USER_CONFIG.get("QOL_MODS", [])))
        qol_layout.addWidget(self.cfg_qol)

        maint_group = QFrame()
        maint_layout = QVBoxLayout(maint_group)
        lbl_maint = QLabel("Database Maintenance")
        lbl_maint.setStyleSheet(f"color: {COLOR_HAZARD}; font-size: 16px; font-weight: bold;")
        maint_layout.addWidget(lbl_maint)
        self.lbl_prune = QLabel("Clean out dead/deleted workshop items from the local cache.")
        maint_layout.addWidget(self.lbl_prune)
        
        self.btn_prune = QPushButton("🧹 PRUNE DEAD LINKS")
        self.btn_prune.setStyleSheet(f"background-color: {COLOR_BLOOD};")
        self.btn_prune.clicked.connect(self.run_pruner)
        maint_layout.addWidget(self.btn_prune)

        self.btn_save_cfg = QPushButton("💾 SAVE CONFIGURATION")
        self.btn_save_cfg.setStyleSheet(f"background-color: {COLOR_HAZARD}; color: white;")
        self.btn_save_cfg.clicked.connect(self.save_configuration)

        layout.addWidget(config_group, 0, 0)
        layout.addWidget(qol_group, 0, 1)
        layout.addWidget(self.btn_save_cfg, 1, 0, 1, 2)
        layout.addWidget(maint_group, 2, 0, 1, 2)
        layout.setRowStretch(0, 3)
        layout.setRowStretch(2, 1)

    def save_configuration(self):
        try:
            new_qol = [line.strip() for line in self.cfg_qol.toPlainText().split("\n") if line.strip()]
            new_cfg = {
                "STEAM_API_KEY": self.cfg_api.text().strip(),
                "COLLECTION_ID": self.cfg_col.text().strip(),
                "SESSION_ID": self.cfg_ses.text().strip(),
                "STEAM_LOGIN_SECURE": self.cfg_sec.text().strip(),
                "QOL_MODS": new_qol,
                "ALLOW_PACKS": self.chk_allow_packs.isChecked(),
                "SCRAPER_FILTERS": config.USER_CONFIG.get("SCRAPER_FILTERS", {"MAX_SIZE_MB": 500, "MIN_SUBS": 10})
            }
            config.save_user_config(new_cfg)
            config.USER_CONFIG.update(new_cfg)
            self.lbl_prune.setText("Configuration Saved Successfully!")
            self.lbl_prune.setStyleSheet("color: #2ecc71;")
            log.info("User configuration successfully updated and saved.")
        except Exception as e:
            log.error(f"Failed to save configuration: {e}")
            self.lbl_prune.setText(f"Error saving config: {e}")
            self.lbl_prune.setStyleSheet(f"color: {COLOR_BLOOD};")

    def run_pruner(self):
        self.btn_prune.setEnabled(False)
        self.btn_prune.setText("PRUNING...")
        log.info("Manual Database Prune initiated by user.")
        def task():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(scraper.prune_database_async(
                lambda txt, val: self.signals.prune_msg.emit(txt, False)
            ))
            self.signals.prune_msg.emit("🧹 PRUNE DEAD LINKS", True)
            
        threading.Thread(target=task, daemon=True).start()

    def update_prune_msg(self, txt, finished):
        if finished:
            self.btn_prune.setEnabled(True)
            self.btn_prune.setText(txt)
        else:
            self.lbl_prune.setText(txt)
            self.lbl_prune.setStyleSheet("color: white;")

    def setup_director_tab(self):
        layout = QHBoxLayout(self.tab_director)

        left_frame = QWidget()
        left_layout = QVBoxLayout(left_frame)
        left_layout.setContentsMargins(10, 10, 10, 10)

        lbl_title = QLabel("Active Loadout Engine")
        lbl_title.setStyleSheet(f"color: {COLOR_BLOOD}; font-size: 20px; font-weight: bold;")
        left_layout.addWidget(lbl_title)

        theme_group = QWidget()
        theme_layout = QVBoxLayout(theme_group)
        self.theme_lbl = QLabel("Target Generation Theme:")
        self.theme_lbl.setStyleSheet("font-weight: bold;")
        theme_layout.addWidget(self.theme_lbl)
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Any Theme", "Anime", "Realistic", "Meme", "Tactical", "Horror"])
        theme_layout.addWidget(self.theme_combo)
        left_layout.addWidget(theme_group)
        
        # New Filter Group Module
        filter_group = QWidget()
        filter_layout = QVBoxLayout(filter_group)
        self.filter_lbl = QLabel("Loadout Algorithm Filter:")
        self.filter_lbl.setStyleSheet("font-weight: bold;")
        filter_layout.addWidget(self.filter_lbl)

        self.filter_combo = QComboBox()
        self.filter_combo.addItems([
            "None", 
            "Trending", 
            "Most Subscribed", 
            "Recently Updated", 
            "Recently Uploaded"
        ])
        filter_layout.addWidget(self.filter_combo)
        left_layout.addWidget(filter_group)

        ratio_group = QWidget()
        ratio_layout = QVBoxLayout(ratio_group)
        self.ratio_lbl = QLabel("Pool Source: Auto Blend (Random %)")
        self.ratio_lbl.setStyleSheet("font-weight: bold;")
        ratio_layout.addWidget(self.ratio_lbl)

        self.ratio_slider = QSlider(Qt.Horizontal)
        self.ratio_slider.setRange(0, 100)
        self.ratio_slider.setValue(50)
        self.ratio_slider.valueChanged.connect(self.on_slider_move)
        ratio_layout.addWidget(self.ratio_slider)

        ratio_btn_layout = QHBoxLayout()
        self.btn_new = QPushButton("New Only")
        self.btn_new.clicked.connect(lambda: self.set_ratio(0))
        self.btn_auto = QPushButton("Auto")
        self.btn_auto.clicked.connect(lambda: self.set_ratio(-1))
        self.btn_cache = QPushButton("Cache Only")
        self.btn_cache.clicked.connect(lambda: self.set_ratio(100))
        ratio_btn_layout.addWidget(self.btn_new)
        ratio_btn_layout.addWidget(self.btn_auto)
        ratio_btn_layout.addWidget(self.btn_cache)
        ratio_layout.addLayout(ratio_btn_layout)
        left_layout.addWidget(ratio_group)

        action_layout = QHBoxLayout()
        self.generate_btn = QPushButton("1. GENERATE LOADOUT")
        self.generate_btn.setStyleSheet(f"background-color: {COLOR_BLOOD}; font-size: 14px; padding: 15px;")
        self.generate_btn.clicked.connect(self.start_generation)
        
        self.reset_btn = QPushButton("↻ RESET")
        self.reset_btn.setEnabled(False)
        self.reset_btn.clicked.connect(self.reset_loadout)
        
        action_layout.addWidget(self.generate_btn, stretch=3)
        action_layout.addWidget(self.reset_btn, stretch=1)
        left_layout.addLayout(action_layout)

        self.status_label = QLabel("Ready to build the apocalypse.")
        self.status_label.setStyleSheet(f"color: {COLOR_TEXT_MUTED};")
        left_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        left_layout.addWidget(self.progress_bar)

        self.stats_label = QLabel("Database: 0 Mods | Cached: 0% | New: 0%")
        left_layout.addWidget(self.stats_label)
        left_layout.addStretch()

        self.play_btn = QPushButton("2. DEPLOY TO STEAM")
        self.play_btn.setEnabled(False)
        self.play_btn.setStyleSheet(f"background-color: {COLOR_TOXIC}; font-size: 16px; padding: 20px;")
        self.play_btn.clicked.connect(self.start_sync)
        left_layout.addWidget(self.play_btn)

        right_frame = QWidget()
        right_layout = QVBoxLayout(right_frame)
        
        review_top_layout = QHBoxLayout()
        lbl_review = QLabel("Assignment Review")
        lbl_review.setStyleSheet("font-size: 16px; font-weight: bold;")
        review_top_layout.addWidget(lbl_review)
        review_top_layout.addStretch()
        
        self.btn_view_compact = QPushButton("Compact")
        self.btn_view_compact.clicked.connect(lambda: self.toggle_view(False))
        self.btn_view_adv = QPushButton("Advanced")
        self.btn_view_adv.clicked.connect(lambda: self.toggle_view(True))
        review_top_layout.addWidget(self.btn_view_compact)
        review_top_layout.addWidget(self.btn_view_adv)
        right_layout.addLayout(review_top_layout)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.scroll_content)
        right_layout.addWidget(self.scroll_area)

        self.placeholder_lbl = QLabel("Click 'Generate Loadout' or 'Load Preset'.")
        self.placeholder_lbl.setAlignment(Qt.AlignCenter)
        self.placeholder_lbl.setStyleSheet(f"color: {COLOR_TEXT_MUTED}; margin-top: 100px;")
        self.scroll_layout.addWidget(self.placeholder_lbl)

        bot_layout = QHBoxLayout()
        self.btn_export = QPushButton("📄 File")
        self.btn_export.setToolTip("Export to Text File")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self.export_txt)
        
        self.btn_share = QPushButton("🔗 Code")
        self.btn_share.setToolTip("Generate Shareable Text Code")
        self.btn_share.setEnabled(False)
        self.btn_share.clicked.connect(self.show_share_code)
        
        self.btn_import = QPushButton("📥 Import")
        self.btn_import.setToolTip("Import from Share Code")
        self.btn_import.clicked.connect(self.import_share_code)
        
        self.reroll_all_btn = QPushButton("🎲 Reroll Entire Loadout")
        self.reroll_all_btn.setEnabled(False)
        self.reroll_all_btn.setStyleSheet("background-color: #8e44ad;")
        self.reroll_all_btn.clicked.connect(self.reroll_all)
        
        bot_layout.addWidget(self.btn_export)
        bot_layout.addWidget(self.btn_share)
        bot_layout.addWidget(self.btn_import)
        bot_layout.addStretch()
        bot_layout.addWidget(self.reroll_all_btn)
        right_layout.addLayout(bot_layout)

        layout.addWidget(left_frame, stretch=3)
        layout.addWidget(right_frame, stretch=5)

    def setup_scraper_tab(self):
        layout = QHBoxLayout(self.tab_scraper)
        self.tag_vars, self.entity_vars = {}, {}

        left_frame = QWidget()
        left_layout = QVBoxLayout(left_frame)
        lbl_scrape = QLabel("Scraping Targets")
        lbl_scrape.setStyleSheet(f"color: {COLOR_HAZARD}; font-size: 16px; font-weight: bold;")
        left_layout.addWidget(lbl_scrape)
        
        btn_layout = QHBoxLayout()
        btn_all = QPushButton("All")
        btn_all.clicked.connect(lambda: self.set_all_targets(True))
        btn_none = QPushButton("None")
        btn_none.clicked.connect(lambda: self.set_all_targets(False))
        btn_layout.addWidget(btn_all)
        btn_layout.addWidget(btn_none)
        left_layout.addLayout(btn_layout)

        scrape_tabs = QTabWidget()
        tab_tags = QWidget()
        tab_ents = QWidget()
        scrape_tabs.addTab(tab_tags, "Tags (Broad)")
        scrape_tabs.addTab(tab_ents, "Entities (Targeted)")
        
        tags_scroll = QScrollArea()
        tags_scroll.setWidgetResizable(True)
        tags_content = QWidget()
        tags_layout = QVBoxLayout(tags_content)
        for tag in sorted(config.ALLOWED_TAGS):
            cb = QCheckBox(tag)
            cb.setChecked(True)
            self.tag_vars[tag] = cb
            tags_layout.addWidget(cb)
        tags_scroll.setWidget(tags_content)
        QVBoxLayout(tab_tags).addWidget(tags_scroll)

        ents_scroll = QScrollArea()
        ents_scroll.setWidgetResizable(True)
        ents_content = QWidget()
        ents_layout = QVBoxLayout(ents_content)
        for ent in sorted(config.VPK_DICT.keys()):
            cb = QCheckBox(ent)
            cb.setChecked(False)
            self.entity_vars[ent] = cb
            ents_layout.addWidget(cb)
        ents_scroll.setWidget(ents_content)
        QVBoxLayout(tab_ents).addWidget(ents_scroll)

        left_layout.addWidget(scrape_tabs)
        
        filter_group = QFrame()
        filter_layout = QGridLayout(filter_group)
        lbl_filters = QLabel("Quality Filters")
        lbl_filters.setStyleSheet(f"color: {COLOR_HAZARD}; font-size: 14px; font-weight: bold;")
        filter_layout.addWidget(lbl_filters, 0, 0, 1, 2)

        filter_layout.addWidget(QLabel("Max Size (MB):"), 1, 0)
        self.spin_max_size = QSpinBox()
        self.spin_max_size.setRange(10, 5000)
        self.spin_max_size.setValue(config.USER_CONFIG.get("SCRAPER_FILTERS", {}).get("MAX_SIZE_MB", 500))
        self.spin_max_size.valueChanged.connect(self.save_scraper_filters)
        filter_layout.addWidget(self.spin_max_size, 1, 1)

        filter_layout.addWidget(QLabel("Min Subs:"), 2, 0)
        self.spin_min_subs = QSpinBox()
        self.spin_min_subs.setRange(0, 100000)
        self.spin_min_subs.setValue(config.USER_CONFIG.get("SCRAPER_FILTERS", {}).get("MIN_SUBS", 10))
        self.spin_min_subs.valueChanged.connect(self.save_scraper_filters)
        filter_layout.addWidget(self.spin_min_subs, 2, 1)

        left_layout.addWidget(filter_group)

        right_frame = QWidget()
        right_layout = QVBoxLayout(right_frame)
        
        top_ctrl = QHBoxLayout()
        self.db_stat_lbl = QLabel("Database Size: 0")
        self.db_stat_lbl.setStyleSheet("font-weight: bold;")
        top_ctrl.addWidget(self.db_stat_lbl)
        top_ctrl.addStretch()

        self.btn_stop_scrape = QPushButton("STOP")
        self.btn_stop_scrape.setEnabled(False)
        self.btn_stop_scrape.setStyleSheet(f"background-color: {COLOR_BLOOD}; padding: 10px 20px;")
        self.btn_stop_scrape.clicked.connect(self.stop_passive_scrape)
        
        self.btn_start_scrape = QPushButton("START MINING")
        self.btn_start_scrape.setStyleSheet(f"background-color: {COLOR_TOXIC}; padding: 10px 20px;")
        self.btn_start_scrape.clicked.connect(self.start_passive_scrape)
        
        top_ctrl.addWidget(self.btn_stop_scrape)
        top_ctrl.addWidget(self.btn_start_scrape)
        right_layout.addLayout(top_ctrl)

        self.scrape_log_widget = QPlainTextEdit()
        self.scrape_log_widget.setReadOnly(True)
        self.scrape_log_widget.setStyleSheet("background-color: #0a0a0a; color: #00FF41; font-family: Consolas;")
        right_layout.addWidget(self.scrape_log_widget)

        layout.addWidget(left_frame, stretch=1)
        layout.addWidget(right_frame, stretch=2)

        self.db_timer = QTimer(self)
        self.db_timer.timeout.connect(self.update_db_stat)
        self.db_timer.start(5000)
        self.update_db_stat()
        
    def save_scraper_filters(self):
        if "SCRAPER_FILTERS" not in config.USER_CONFIG:
            config.USER_CONFIG["SCRAPER_FILTERS"] = {}
        config.USER_CONFIG["SCRAPER_FILTERS"]["MAX_SIZE_MB"] = self.spin_max_size.value()
        config.USER_CONFIG["SCRAPER_FILTERS"]["MIN_SUBS"] = self.spin_min_subs.value()
        config.save_user_config(config.USER_CONFIG)
        log.debug(f"Updated Scraper Filters: Max {self.spin_max_size.value()}MB, Min {self.spin_min_subs.value()} Subs.")

    def setup_sys_logs_tab(self):
        layout = QVBoxLayout(self.tab_sys_logs)
        
        header = QHBoxLayout()
        lbl_sys = QLabel("Engine Health & Diagnostics")
        lbl_sys.setStyleSheet(f"color: {COLOR_HAZARD}; font-size: 16px; font-weight: bold;")
        header.addWidget(lbl_sys)
        header.addStretch()
        
        btn_clear = QPushButton("Clear Log")
        btn_clear.clicked.connect(lambda: self.sys_log_widget.clear())
        header.addWidget(btn_clear)
        layout.addLayout(header)

        self.sys_log_widget = QPlainTextEdit()
        self.sys_log_widget.setReadOnly(True)
        self.sys_log_widget.setStyleSheet("background-color: #121212; color: #e0e0e0; font-family: Consolas;")
        layout.addWidget(self.sys_log_widget)

    def update_db_stat(self):
        try:
            self.db_stat_lbl.setText(f"Total Mapped Mods: {database.get_db_size()}")
        except Exception as e:
            log.warning(f"Failed to fetch DB size: {e}")

    def set_all_targets(self, state):
        for cb in self.tag_vars.values(): cb.setChecked(state)
        for cb in self.entity_vars.values(): cb.setChecked(state)

    def append_scrape_log_ui(self, msg):
        self.scrape_log_widget.appendPlainText(msg)

    def append_sys_log_ui(self, msg):
        if not hasattr(self, 'sys_log_widget'): return
            
        if "[ERROR]" in msg or "[CRITICAL]" in msg:
            html_msg = f"<span style='color: #ff4444;'>{msg}</span>"
        elif "[WARNING]" in msg:
            html_msg = f"<span style='color: #ffaa00;'>{msg}</span>"
        elif "[DEBUG]" in msg:
            html_msg = f"<span style='color: #888888;'>{msg}</span>"
        else:
            html_msg = f"<span>{msg}</span>"
            
        self.sys_log_widget.appendHtml(html_msg)

    def start_passive_scrape(self):
        active_targets = [("tag", t) for t, cb in self.tag_vars.items() if cb.isChecked()] + \
                         [("entity", e) for e, cb in self.entity_vars.items() if cb.isChecked()]
        if not active_targets: 
            log.warning("Attempted to start scraper with no targets selected.")
            return
        
        scraper.PASSIVE_SCRAPE_FLAG = True
        self.btn_start_scrape.setEnabled(False)
        self.btn_stop_scrape.setEnabled(True)
        log.info("Passive Scraper GUI flag set. Launching background thread.")

        def run_loop():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(scraper.passive_scrape_loop(
                    active_targets, 
                    lambda m: self.signals.scrape_log.emit(m)
                ))
            except Exception as e:
                log.error(f"Fatal error in passive scrape thread: {e}\n{traceback.format_exc()}")

        threading.Thread(target=run_loop, daemon=True).start()

    def stop_passive_scrape(self):
        scraper.PASSIVE_SCRAPE_FLAG = False
        self.btn_start_scrape.setEnabled(True)
        self.btn_stop_scrape.setEnabled(False)
        log.info("Passive Scraper GUI flag disabled. Loop will terminate shortly.")

    def on_slider_move(self, value):
        self.blend_mode = float(value) / 100.0
        self.ratio_lbl.setText(f"Pool Source: {int(value)}% Cached / {100 - int(value)}% New")

    def set_ratio(self, val):
        if val == -1:
            self.blend_mode = -1.0
            self.ratio_lbl.setText("Pool Source: Auto Blend (Random %)")
            self.ratio_slider.setValue(50) 
        else:
            self.blend_mode = val / 100.0
            self.ratio_slider.setValue(val)
            self.ratio_lbl.setText(f"Pool Source: {val}% Cached / {100 - val}% New")

    def update_progress_ui(self, text, val):
        self.status_label.setText(text)
        self.progress_bar.setValue(int(val * 100))

    def update_stats_ui(self, stats):
        self.stats_label.setText(f"Database: {stats['total']} Mods | Cached: {stats['cached_pct']}% | New: {stats['new_pct']}%")

    def _build_all_slots(self):
        self.slot_widgets = {}
        self.group_frames = {}

        for group_name, slots in SLOT_GROUPS.items():
            group_frame = QWidget()
            group_layout = QVBoxLayout(group_frame)
            group_layout.setContentsMargins(0, 5, 0, 10)
            
            hdr = QLabel(f"--- {group_name.upper()} ---")
            hdr.setStyleSheet(f"color: {COLOR_HAZARD}; font-size: 14px; font-weight: bold;")
            group_layout.addWidget(hdr)

            self.group_frames[group_name] = {"frame": group_frame, "rows": []}

            for base_slot in slots:
                for suffix in [" [Model]", " [Sound]"]:
                    full_slot_name = base_slot + suffix

                    row_frame = QWidget()
                    row_layout = QHBoxLayout(row_frame)
                    row_layout.setContentsMargins(0, 2, 0, 2)

                    lbl_color = "#3498db" if "[Model]" in full_slot_name else "#f1c40f"
                    lbl = QLabel(full_slot_name)
                    lbl.setFixedWidth(190)
                    lbl.setStyleSheet(f"color: {lbl_color}; font-weight: bold;")
                    row_layout.addWidget(lbl)
                    
                    thumb_lbl = QLabel()
                    thumb_lbl.setFixedSize(40, 40)
                    thumb_lbl.setStyleSheet("background-color: #121212; border: 1px solid #3a3a3a;")
                    row_layout.addWidget(thumb_lbl)

                    mod_btn = QPushButton("--- EMPTY ---")
                    mod_btn.setStyleSheet(f"background-color: transparent; color: {COLOR_TEXT_MUTED}; text-align: left; padding-left: 10px;")
                    mod_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                    
                    mod_btn.setContextMenuPolicy(Qt.CustomContextMenu)
                    def make_context_menu_slot(s_name):
                        return lambda pos: self.show_theme_menu(pos, s_name)
                    mod_btn.customContextMenuRequested.connect(make_context_menu_slot(full_slot_name))
                    
                    row_layout.addWidget(mod_btn)

                    reroll_btn = QPushButton("🎲")
                    reroll_btn.setFixedWidth(30)
                    reroll_btn.clicked.connect(lambda checked=False, s=full_slot_name: self.reroll_single(s))
                    row_layout.addWidget(reroll_btn)
                    
                    clear_btn = QPushButton("X")
                    clear_btn.setFixedWidth(30)
                    clear_btn.setStyleSheet(f"background-color: {COLOR_BLOOD};")
                    clear_btn.clicked.connect(lambda checked=False, s=full_slot_name: self.clear_single(s))
                    row_layout.addWidget(clear_btn)

                    self.slot_widgets[full_slot_name] = {
                        "row_frame": row_frame,
                        "mod_btn": mod_btn,
                        "thumb_lbl": thumb_lbl,
                        "base_slot": base_slot
                    }
                    self.group_frames[group_name]["rows"].append({
                        "name": full_slot_name, 
                        "base_slot": base_slot, 
                        "row_frame": row_frame
                    })
                    
                    group_layout.addWidget(row_frame)

            self.scroll_layout.addWidget(group_frame)
            group_frame.setVisible(False)

    def refresh_ui_view(self):
        if not self.ui_initialized:
            self._build_all_slots()
            self.ui_initialized = True

        self.placeholder_lbl.setVisible(False)

        for group_name, group_data in self.group_frames.items():
            has_visible_row = False
            for row_data in group_data["rows"]:
                full_slot_name = row_data["name"]
                base_slot = row_data["base_slot"]

                has_assignment = full_slot_name in self.current_assignments
                is_compact_visible = self.show_advanced or (base_slot in COMPACT_SLOTS)

                if has_assignment and is_compact_visible:
                    row_data["row_frame"].setVisible(True)
                    has_visible_row = True
                    self._update_button_ui(full_slot_name, self.current_assignments[full_slot_name])
                else:
                    row_data["row_frame"].setVisible(False)

            group_data["frame"].setVisible(has_visible_row)

    def _update_button_ui(self, slot_name, mod_data):
        if not hasattr(self, 'slot_widgets') or slot_name not in self.slot_widgets:
            return
            
        btn = self.slot_widgets[slot_name]["mod_btn"]
        thumb = self.slot_widgets[slot_name]["thumb_lbl"]
        
        if getattr(btn, "_has_url_connection", False):
            try: btn.clicked.disconnect()
            except RuntimeError: pass
            btn._has_url_connection = False

        if mod_data:
            theme_indicator = f"[{mod_data['theme_tag']}] " if mod_data.get("theme_tag") and mod_data["theme_tag"] != "None" else ""
            title = f"{theme_indicator}{mod_data['title']}"
            
            if len(title) > 42: title = title[:39] + "..."
            
            mod_id = mod_data["id"]
            btn.setText(title)
            
            text_color = "#3498db" if theme_indicator else "#ffffff"
            btn.setStyleSheet(f"background-color: transparent; color: {text_color}; font-weight: bold; text-align: left; padding-left: 10px;")
            
            btn.clicked.connect(lambda checked=False, i=mod_id: webbrowser.open(f"https://steamcommunity.com/sharedfiles/filedetails/?id={i}"))
            btn._has_url_connection = True
            
            self.image_manager.load_image(mod_data.get("preview_url", ""), thumb)
        else:
            btn.setText("--- EMPTY ---")
            btn.setStyleSheet(f"background-color: transparent; color: {COLOR_TEXT_MUTED}; text-align: left; padding-left: 10px;")
            thumb.setPixmap(QPixmap()) 

    def show_theme_menu(self, pos, slot_name):
        mod_data = self.current_assignments.get(slot_name)
        if not mod_data: return
        
        btn = self.slot_widgets[slot_name]["mod_btn"]
        menu = QMenu(self)
        
        inspect_action = menu.addAction("🔍 Inspect Raw Assets")
        inspect_action.triggered.connect(lambda checked=False, m=mod_data["id"], t=mod_data["title"]: self.show_inspector(m, t))
        menu.addSeparator()
        
        themes = [self.theme_combo.itemText(i) for i in range(1, self.theme_combo.count())]
        themes.insert(0, "None")
        
        for theme in themes:
            action = menu.addAction(f"Tag as: {theme}")
            action.triggered.connect(lambda checked=False, t=theme, m=mod_data["id"], s=slot_name: self.set_mod_theme(m, t, s))
            
        menu.exec_(btn.mapToGlobal(pos))

    def show_inspector(self, mod_id, title):
        log.info(f"User opened Deep-Scan Inspector for Mod ID {mod_id}")
        dialog = AssetInspectorDialog(mod_id, title, self)
        dialog.exec()

    def set_mod_theme(self, mod_id, theme, slot_name):
        database.update_mod_theme(mod_id, theme)
        self.signals.sys_log.emit(f"[INFO] User tagged Mod ID {mod_id} with theme: '{theme}'")
        
        if slot_name in self.current_assignments and self.current_assignments[slot_name]["id"] == mod_id:
            self.current_assignments[slot_name]["theme_tag"] = theme
            self._update_button_ui(slot_name, self.current_assignments[slot_name])
            
        for pool_mod in self.mixed_pool:
            if pool_mod.id == mod_id:
                pool_mod.theme_tag = theme

    def toggle_view(self, advanced):
        self.show_advanced = advanced
        self.btn_view_adv.setStyleSheet("background-color: #8b0000;" if advanced else "")
        self.btn_view_compact.setStyleSheet("" if advanced else "background-color: #8b0000;")
        self.refresh_ui_view()

    def start_generation(self):
        log.info("Starting loadout generation process...")
        self.ratio_slider.setEnabled(False)
        self.btn_new.setEnabled(False)
        self.btn_auto.setEnabled(False)
        self.btn_cache.setEnabled(False)
        self.theme_combo.setEnabled(False)
        self.filter_combo.setEnabled(False)
        
        self.generate_btn.setEnabled(False)
        self.reset_btn.setEnabled(False)
        self.play_btn.setEnabled(False)
        self.reroll_all_btn.setEnabled(False)
        self.btn_export.setEnabled(False)
        self.btn_share.setEnabled(False)
        self.btn_import.setEnabled(False)
        
        target_theme = self.theme_combo.currentText()
        target_filter = self.filter_combo.currentText()
        threading.Thread(target=self.run_phase_1, args=(target_theme, target_filter), daemon=True).start()

    def run_phase_1(self, target_theme, target_filter):
        try:
            self.mixed_pool, stats = director.prep_mixed_pool(
                lambda txt, val: self.signals.progress.emit(txt, val), 
                cache_ratio=self.blend_mode,
                target_theme=target_theme,
                filter_mode=target_filter
            )
            
            if stats: 
                self.signals.stats.emit(stats)
            
            if not self.mixed_pool:
                self.signals.progress.emit(f"Error: 0 mods found for theme '{target_theme}' with active filters.", 1.0)
                self.signals.sys_log.emit(f"[WARNING] Loadout generation aborted. No mods in pool for theme: {target_theme}")
                self.signals.generation_complete.emit()
                return

            self.signals.progress.emit(f"Allocating {target_theme} slots...", 0.9)
            self.current_assignments, self.current_selected_ids = director.allocate_loadout(self.mixed_pool)
            
            self.signals.refresh_ui.emit()
            self.signals.progress.emit("Phase 1 Complete. Review assignments.", 1.0)
            log.info("Loadout generated successfully.")
            
            self.signals.generation_complete.emit()
        except Exception as e:
            log.error(f"Error during loadout generation: {e}\n{traceback.format_exc()}")
            self.signals.progress.emit(f"Error: {e}", 1.0)
            self.signals.generation_complete.emit()

    def _enable_post_gen_ui(self):
        self.play_btn.setEnabled(True)
        self.reset_btn.setEnabled(True)
        self.reset_btn.setStyleSheet(f"background-color: {COLOR_BLOOD};")
        self.reroll_all_btn.setEnabled(True)
        self.btn_export.setEnabled(True)
        self.btn_share.setEnabled(True)
        self.btn_import.setEnabled(True)
        self.theme_combo.setEnabled(True)
        self.filter_combo.setEnabled(True)
        self.ratio_slider.setEnabled(True)
        self.btn_new.setEnabled(True)
        self.btn_auto.setEnabled(True)
        self.btn_cache.setEnabled(True)

    def reset_loadout(self):
        log.info("User triggered loadout reset.")
        self.mixed_pool = []
        self.current_assignments = {}
        self.current_selected_ids = []
        
        self.status_label.setText("Ready to build the apocalypse.")
        self.status_label.setStyleSheet(f"color: {COLOR_TEXT_MUTED};")
        self.progress_bar.setValue(0)
        self.stats_label.setText("Database: 0 Mods | Cached: 0% | New: 0%")
        
        if self.ui_initialized:
            for group_data in self.group_frames.values():
                group_data["frame"].setVisible(False)
                
        self.placeholder_lbl.setVisible(True)
        
        self.ratio_slider.setEnabled(True)
        self.btn_new.setEnabled(True)
        self.btn_auto.setEnabled(True)
        self.btn_cache.setEnabled(True)
        self.theme_combo.setEnabled(True)
        self.filter_combo.setEnabled(True)
        
        self.generate_btn.setEnabled(True)
        self.reset_btn.setEnabled(False)
        self.reset_btn.setStyleSheet("")
        self.play_btn.setEnabled(False)
        self.play_btn.setText("2. DEPLOY TO STEAM")
        self.play_btn.setStyleSheet(f"background-color: {COLOR_TOXIC}; font-size: 16px; padding: 20px;")
        self.reroll_all_btn.setEnabled(False)
        self.btn_export.setEnabled(False)
        self.btn_share.setEnabled(False)

    def clear_single(self, full_slot_name):
        log.debug(f"Clearing single slot: {full_slot_name}")
        old_mod = self.current_assignments.get(full_slot_name)
        if old_mod:
            old_id = old_mod["id"]
            if old_id in self.current_selected_ids:
                self.current_selected_ids.remove(old_id)
            for k, v in list(self.current_assignments.items()):
                if v and v["id"] == old_id:
                    self.current_assignments[k] = None
                    self._update_button_ui(k, None)

    def reroll_all(self):
        log.info("Rerolling entire loadout matrix.")
        self.current_assignments, self.current_selected_ids = director.allocate_loadout(self.mixed_pool)
        self.refresh_ui_view()

    def reroll_single(self, full_slot_name):
        log.debug(f"Rerolling single slot: {full_slot_name}")
        success = director.reroll_single_slot(full_slot_name, self.mixed_pool, self.current_assignments, self.current_selected_ids)
        if success:
            self.refresh_ui_view()
        else:
            log.warning(f"Failed to reroll {full_slot_name} - pool exhausted or conflicted.")
            self.status_label.setText(f"No valid non-conflicting mods found for {full_slot_name}!")
            self.status_label.setStyleSheet(f"color: {COLOR_BLOOD};")

    def start_sync(self):
        log.info(f"Initiating Steam Sync with {len(self.current_selected_ids)} selected items.")
        self.play_btn.setEnabled(False)
        self.play_btn.setText("THE DIRECTOR IS SHUFFLING THE DECK...")
        self.status_label.setText("Prepare for the apocalypse. Syncing with Steam...")
        self.status_label.setStyleSheet(f"color: {COLOR_HAZARD};")
        self.reset_btn.setEnabled(False)
        self.reroll_all_btn.setEnabled(False)
        
        threading.Thread(target=self.run_phase_2, daemon=True).start()

    def run_phase_2(self):
        try:
            director.sync_collection_loadout(
                config.USER_CONFIG["COLLECTION_ID"], 
                self.current_selected_ids, 
                lambda txt, val: self.signals.progress.emit(txt, val)
            )
            self.signals.deploy_complete.emit()
            log.info("Steam Sync thread completed successfully.")
        except Exception as e:
            log.error(f"Error during Steam deployment: {e}\n{traceback.format_exc()}")
            self.signals.progress.emit(f"Deploy Error: {e}", 1.0)

    def on_deploy_complete(self):
        self.play_btn.setText("✔ COLLECTION LIVE")
        self.play_btn.setStyleSheet("background-color: #2980b9; font-size: 16px; padding: 20px;")
        self.status_label.setText("Sync Successful. Go start your game.")
        self.status_label.setStyleSheet("color: #2ecc71;")
        self.reset_btn.setEnabled(True)

    def export_txt(self):
        filepath, _ = QFileDialog.getSaveFileName(self, "Export Loadout", "", "Text Files (*.txt)")
        if not filepath: return
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("=== L4D2 Mod Director Loadout ===\n\n")
                for group, slots in SLOT_GROUPS.items():
                    f.write(f"\n[{group.upper()}]\n")
                    for base in slots:
                        for sfx in [" [Model]", " [Sound]"]:
                            slot = base + sfx
                            data = self.current_assignments.get(slot)
                            if data: f.write(f"{slot.ljust(30)} : {data['title']} ({data['id']})\n")
            self.status_label.setText(f"Exported to {os.path.basename(filepath)}")
            self.status_label.setStyleSheet("color: #2ecc71;")
            log.info(f"Loadout exported to TXT: {filepath}")
        except Exception as e:
            log.error(f"Failed to export TXT: {e}")

    def show_share_code(self):
        code = director.generate_share_code(self.current_assignments)
        if not code:
            QMessageBox.warning(self, "Export Error", "Failed to generate share code. Loadout might be empty.")
            return
            
        dialog = QInputDialog(self)
        dialog.setWindowTitle("Share Loadout")
        dialog.setLabelText("Copy this code to share with friends on Discord:")
        dialog.setTextValue(code)
        dialog.resize(400, 150)
        dialog.exec()

    def import_share_code(self):
        code, ok = QInputDialog.getText(self, "Import Loadout", "Paste a Share Code here:")
        if not ok or not code.strip(): return
        
        decoded_assignments = director.decode_share_code(code.strip())
        if not decoded_assignments:
            QMessageBox.critical(self, "Import Error", "Invalid or corrupted share code.")
            return
            
        mod_ids = list(decoded_assignments.values())
        db_mods = database.get_mods_by_ids(mod_ids)
        
        mod_lookup = {m.id: {"id": m.id, "title": m.title, "preview_url": m.preview_url, "theme_tag": m.theme_tag} for m in db_mods}
        
        missing_mods = []
        new_assignments = {}
        new_selected_ids = []
        
        for slot, mod_id in decoded_assignments.items():
            if mod_id in mod_lookup:
                new_assignments[slot] = mod_lookup[mod_id]
                new_selected_ids.append(mod_id)
            else:
                missing_mods.append(mod_id)
                new_assignments[slot] = None
                
        self.current_assignments = new_assignments
        self.current_selected_ids = list(set(new_selected_ids))
        
        self.refresh_ui_view()
        self._enable_post_gen_ui()
        
        if missing_mods:
            self.status_label.setText(f"Imported! Warning: {len(missing_mods)} mods are missing from your local cache.")
            self.status_label.setStyleSheet(f"color: {COLOR_HAZARD};")
            log.warning(f"Share Code imported, but missing {len(missing_mods)} mods from local DB.")
        else:
            self.status_label.setText("Share Code successfully imported!")
            self.status_label.setStyleSheet("color: #2ecc71;")
            log.info("Share Code successfully imported and reconstructed.")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = L4D2RandomizerApp()
    window.show()
    sys.exit(app.exec())