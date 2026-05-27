from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from media_clinaer.app_context import AppContext
from media_clinaer.config.manager import ConfigManager
from media_clinaer.config.models import AppConfig
from media_clinaer.logging.logger import JsonLineLogger
from media_clinaer.services.detection_service import DetectionService
from media_clinaer.services.quarantine_service import QuarantineService
from media_clinaer.services.result_service import ResultService
from media_clinaer.services.scan_service import ScanService
from media_clinaer.storage.database import Database
from media_clinaer.ui.workers import FunctionWorker


class MainWindow(QMainWindow):
    def __init__(
        self,
        context: AppContext,
        config_manager: ConfigManager,
        config: AppConfig,
        database: Database,
        logger: JsonLineLogger,
    ) -> None:
        super().__init__()
        self.context = context
        self.config_manager = config_manager
        self.config = config
        self.database = database
        self.logger = logger
        self.thread_pool = QThreadPool.globalInstance()
        self.current_scan_session_id: int | None = config.ui.last_opened_result_session_id
        self.has_quarantine_candidates = False

        self.setWindowTitle("MediaClinaer")
        self.setMinimumSize(880, 560)
        self._build_ui()
        self._load_config_paths()

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setSpacing(10)

        title = QLabel("MediaClinaer")
        title.setObjectName("TitleLabel")
        layout.addWidget(title)

        self.folder_list = QListWidget()
        self.folder_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        layout.addWidget(self.folder_list)

        folder_buttons = QHBoxLayout()
        self.add_folder_button = QPushButton("フォルダ追加")
        self.remove_folder_button = QPushButton("選択解除")
        folder_buttons.addWidget(self.add_folder_button)
        folder_buttons.addWidget(self.remove_folder_button)
        folder_buttons.addStretch(1)
        layout.addLayout(folder_buttons)

        action_buttons = QHBoxLayout()
        self.scan_button = QPushButton("スキャン")
        self.quarantine_button = QPushButton("候補を隔離")
        self.quarantine_button.setEnabled(False)
        action_buttons.addWidget(self.scan_button)
        action_buttons.addWidget(self.quarantine_button)
        action_buttons.addStretch(1)
        layout.addLayout(action_buttons)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.status_label = QLabel("フォルダを追加してスキャンを開始できます。")
        layout.addWidget(self.status_label)

        self.results = QPlainTextEdit()
        self.results.setReadOnly(True)
        self.results.setPlaceholderText("検出結果がここに表示されます。")
        layout.addWidget(self.results, stretch=1)

        self.setCentralWidget(root)

        self.add_folder_button.clicked.connect(self._add_folder)
        self.remove_folder_button.clicked.connect(self._remove_selected_folders)
        self.scan_button.clicked.connect(self._start_scan)
        self.quarantine_button.clicked.connect(self._start_quarantine)

    def _load_config_paths(self) -> None:
        for path in self.config.scan.target_paths:
            self.folder_list.addItem(path)

    def _add_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "スキャンするフォルダを選択")
        if folder:
            existing = {
                self.folder_list.item(index).text()
                for index in range(self.folder_list.count())
            }
            if folder not in existing:
                self.folder_list.addItem(folder)
            self._save_target_paths()

    def _remove_selected_folders(self) -> None:
        for item in self.folder_list.selectedItems():
            self.folder_list.takeItem(self.folder_list.row(item))
        self._save_target_paths()

    def _target_paths(self) -> list[str]:
        return [self.folder_list.item(index).text() for index in range(self.folder_list.count())]

    def _save_target_paths(self) -> None:
        self.config.scan.target_paths = self._target_paths()
        self.config_manager.save(self.config)

    def _start_scan(self) -> None:
        target_paths = self._target_paths()
        if not target_paths:
            QMessageBox.information(self, "フォルダ未選択", "スキャンするフォルダを追加してください。")
            return
        self._save_target_paths()
        self._set_busy(True, "スキャン中です。")
        self.results.clear()
        self.has_quarantine_candidates = False

        def run_scan_and_detection():
            scan_result = ScanService(self.database, self.config, self.logger).scan(target_paths)
            detection_result = DetectionService(
                self.database,
                self.logger,
                self.config,
            ).detect_duplicates(scan_result.session_id)
            summaries = ResultService(self.database).list_detection_group_summaries(
                scan_result.session_id
            )
            return scan_result, detection_result, summaries

        worker = FunctionWorker(run_scan_and_detection)
        worker.signals.succeeded.connect(self._scan_finished)
        worker.signals.failed.connect(self._worker_failed)
        worker.signals.finished.connect(lambda: self._set_busy(False))
        self.thread_pool.start(worker)

    def _scan_finished(self, payload: object) -> None:
        scan_result, detection_result, summaries = payload
        self.current_scan_session_id = scan_result.session_id
        self.config.ui.last_opened_result_session_id = scan_result.session_id
        self.config_manager.save(self.config)

        lines = [
            f"スキャン対象: {scan_result.total_files} 件",
            f"処理済み: {scan_result.scanned_files} 件",
            f"キャッシュ利用: {scan_result.cache_used_count} 件",
            f"エラー: {scan_result.error_count} 件",
            "",
            f"完全重複グループ: {detection_result.duplicate_group_count} 件",
            f"重複候補ファイル: {detection_result.duplicate_item_count} 件",
            f"類似画像グループ: {detection_result.similar_group_count} 件",
            f"類似画像候補ファイル: {detection_result.similar_item_count} 件",
            f"ブレ画像候補: {detection_result.blurry_item_count} 件",
        ]
        for summary in summaries:
            if summary.group_type == "duplicate_image":
                label = "重複画像"
            elif summary.group_type == "duplicate_video":
                label = "重複映像"
            elif summary.group_type == "blurry_image":
                label = "ブレ画像"
            else:
                label = "類似画像"
            lines.append(
                f"- {label}: {summary.item_count} 件中 {summary.selected_count} 件を隔離候補"
            )
        self.results.setPlainText("\n".join(lines))
        candidate_count = (
            detection_result.duplicate_item_count
            + detection_result.similar_item_count
            + detection_result.blurry_item_count
        )
        self.has_quarantine_candidates = candidate_count > 0
        self.quarantine_button.setEnabled(self.has_quarantine_candidates)
        self.status_label.setText("スキャンと完全重複検出が完了しました。")

    def _start_quarantine(self) -> None:
        if self.current_scan_session_id is None:
            QMessageBox.information(self, "結果なし", "先にスキャンを実行してください。")
            return
        reply = QMessageBox.question(
            self,
            "隔離の確認",
            "初期候補として選ばれた重複ファイルを隔離します。",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._set_busy(True, "隔離処理中です。")

        def run_quarantine():
            return QuarantineService(
                self.database,
                self.logger,
                self.context.quarantine_dir,
            ).quarantine_selected_defaults(self.current_scan_session_id)

        worker = FunctionWorker(run_quarantine)
        worker.signals.succeeded.connect(self._quarantine_finished)
        worker.signals.failed.connect(self._worker_failed)
        worker.signals.finished.connect(lambda: self._set_busy(False))
        self.thread_pool.start(worker)

    def _quarantine_finished(self, payload: object) -> None:
        result = payload
        self.results.appendPlainText("")
        self.results.appendPlainText("隔離結果")
        self.results.appendPlainText(f"対象: {result.total_count} 件")
        self.results.appendPlainText(f"成功: {result.completed_count} 件")
        self.results.appendPlainText(f"失敗: {result.failed_count} 件")
        self.results.appendPlainText(f"manifest: {result.manifest_path}")
        self.status_label.setText("隔離処理が完了しました。")
        self.has_quarantine_candidates = False
        self.quarantine_button.setEnabled(False)

    def _worker_failed(self, message: str) -> None:
        self.status_label.setText("処理に失敗しました。")
        QMessageBox.warning(self, "処理失敗", message)

    def _set_busy(self, busy: bool, message: str | None = None) -> None:
        self.add_folder_button.setEnabled(not busy)
        self.remove_folder_button.setEnabled(not busy)
        self.scan_button.setEnabled(not busy)
        if busy:
            self.quarantine_button.setEnabled(False)
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, 1)
            self.progress.setValue(0)
            self.quarantine_button.setEnabled(self.has_quarantine_candidates)
        if message:
            self.status_label.setText(message)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Delete:
            self._remove_selected_folders()
            return
        super().keyPressEvent(event)
