from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThreadPool
from PySide6.QtGui import QIcon, QPixmap
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
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
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


PATH_ROLE = Qt.ItemDataRole.UserRole.value + 1
MEDIA_TYPE_ROLE = Qt.ItemDataRole.UserRole.value + 2
RESULT_DISPLAY_GROUP_LIMIT = 1000


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
        self._populating_results_tree = False
        self._thumbnail_cache: dict[str, QIcon] = {}

        self.setWindowTitle("MediaClinaer")
        self.setMinimumSize(880, 560)
        self._build_ui()
        self._load_config_paths()

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setSpacing(10)

        self.folder_list = QListWidget()
        self.folder_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.folder_list.setMaximumHeight(34)
        layout.addWidget(self.folder_list)

        action_buttons = QHBoxLayout()
        self.add_folder_button = QPushButton("フォルダ追加")
        self.remove_folder_button = QPushButton("選択解除")
        self.scan_button = QPushButton("スキャン")
        self.quarantine_button = QPushButton("候補を隔離")
        self.quarantine_button.setEnabled(False)
        action_buttons.addWidget(self.add_folder_button)
        action_buttons.addWidget(self.remove_folder_button)
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

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs, stretch=1)

        self.results = QPlainTextEdit()
        self.results.setReadOnly(True)
        self.results.setPlaceholderText("ログがここに表示されます。")
        self.tabs.addTab(self.results, "ログ")

        candidates_tab = QWidget()
        candidates_layout = QVBoxLayout(candidates_tab)
        candidates_layout.setSpacing(8)
        selection_label = QLabel("隔離候補の選択")
        candidates_layout.addWidget(selection_label)

        self.result_tree = QTreeWidget()
        self.result_tree.setColumnCount(4)
        self.result_tree.setHeaderLabels(["選択", "種類", "ファイル", "情報"])
        self.result_tree.setRootIsDecorated(True)
        self.result_tree.setAlternatingRowColors(True)
        self.result_tree.setIconSize(QSize(72, 72))
        candidates_layout.addWidget(self.result_tree, stretch=2)

        self.preview_label = QLabel("画像を選択するとプレビューを表示します。")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(220)
        self.preview_label.setStyleSheet("border: 1px solid #cccccc; background: #fafafa;")
        candidates_layout.addWidget(self.preview_label, stretch=1)
        self.tabs.addTab(candidates_tab, "隔離候補")

        self.setCentralWidget(root)

        self.add_folder_button.clicked.connect(self._add_folder)
        self.remove_folder_button.clicked.connect(self._remove_selected_folders)
        self.scan_button.clicked.connect(self._start_scan)
        self.quarantine_button.clicked.connect(self._start_quarantine)
        self.result_tree.itemChanged.connect(self._result_tree_item_changed)
        self.result_tree.itemSelectionChanged.connect(self._preview_selected_item)

    def _load_config_paths(self) -> None:
        for path in self.config.scan.target_paths:
            self.folder_list.addItem(path)

    def _add_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "スキャンするフォルダを選択")
        if folder:
            self.folder_list.clear()
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
        self.result_tree.clear()
        self._thumbnail_cache.clear()
        self.preview_label.setText("画像を選択するとプレビューを表示します。")
        self.preview_label.setPixmap(QPixmap())
        self.has_quarantine_candidates = False

        def run_scan_and_detection(progress):
            scan_result = ScanService(
                self.database,
                self.config,
                self.logger,
            ).scan(target_paths, progress_callback=progress)
            progress(
                {
                    "phase": "detecting",
                    "message": "検出中です。",
                    "total_files": scan_result.total_files,
                    "processed_files": scan_result.total_files,
                    "cache_used_count": scan_result.cache_used_count,
                    "error_count": scan_result.error_count,
                }
            )
            detection_result = DetectionService(
                self.database,
                self.logger,
                self.config,
            ).detect_duplicates(scan_result.session_id, progress_callback=progress)
            progress(
                {
                    "phase": "loading_results",
                    "message": "表示する候補一覧を読み込んでいます。",
                    "total_files": 0,
                    "processed_files": 0,
                    "cache_used_count": scan_result.cache_used_count,
                    "error_count": scan_result.error_count,
                }
            )
            details = ResultService(self.database).list_detection_group_details(
                scan_result.session_id,
                max_groups=RESULT_DISPLAY_GROUP_LIMIT,
            )
            return scan_result, detection_result, details

        worker = FunctionWorker(run_scan_and_detection)
        worker.signals.progress.connect(self._scan_progress)
        worker.signals.succeeded.connect(self._scan_finished)
        worker.signals.failed.connect(self._worker_failed)
        worker.signals.finished.connect(lambda: self._set_busy(False))
        self.thread_pool.start(worker)

    def _scan_finished(self, payload: object) -> None:
        scan_result, detection_result, details = payload
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
        lines.append("")
        lines.append("検出グループ詳細")
        total_group_count = (
            detection_result.duplicate_group_count
            + detection_result.similar_group_count
            + detection_result.blurry_group_count
        )
        if total_group_count > len(details):
            lines.append(
                f"表示件数が多いため、先頭 {len(details)} / {total_group_count} "
                "グループだけ表示しています。"
            )
        for index, detail in enumerate(details, start=1):
            summary = detail.summary
            label = self._group_label(summary.group_type)
            lines.append(
                f"[{index}] {label}: {summary.item_count} 件中 "
                f"{summary.selected_count} 件を隔離候補"
            )
            lines.append(f"  理由: {summary.reason}")
            for item in detail.items:
                selected_label = "隔離候補" if item.selected_by_default else "保持"
                size_label = self._format_size(item.size_bytes)
                blur_label = (
                    f", blur={item.blur_score:.2f}"
                    if item.blur_score is not None
                    else ""
                )
                phash_label = (
                    f", pHash={item.perceptual_hash}"
                    if item.perceptual_hash is not None
                    else ""
                )
                lines.append(
                    f"  - {selected_label}: {item.path} "
                    f"({size_label}, 更新={item.modified_at}{blur_label}{phash_label})"
                )
        self.results.setPlainText("\n".join(lines))
        self._populate_result_tree(details)
        self.has_quarantine_candidates = self._selected_tree_item_count() > 0
        self.quarantine_button.setEnabled(self.has_quarantine_candidates)
        self.tabs.setCurrentIndex(1)
        self.status_label.setText("スキャンと検出が完了しました。")

    def _scan_progress(self, payload: object) -> None:
        if isinstance(payload, dict):
            phase = str(payload.get("phase", ""))
            total_files = int(payload.get("total_files", 0))
            processed_files = int(payload.get("processed_files", 0))
            cache_used_count = int(payload.get("cache_used_count", 0))
            error_count = int(payload.get("error_count", 0))
            message = str(payload.get("message", "処理中です。"))
            current_path = payload.get("current_path")
        else:
            phase = str(getattr(payload, "phase", ""))
            total_files = int(getattr(payload, "total_files", 0))
            processed_files = int(getattr(payload, "processed_files", 0))
            cache_used_count = int(getattr(payload, "cache_used_count", 0))
            error_count = int(getattr(payload, "error_count", 0))
            current_path = getattr(payload, "current_path", None)
            message = self._scan_phase_label(phase)

        if total_files > 0:
            self.progress.setRange(0, total_files)
            self.progress.setValue(min(processed_files, total_files))
        else:
            self.progress.setRange(0, 0)

        lines = [
            message,
            f"処理済み: {processed_files} / {total_files} 件",
            f"キャッシュ利用: {cache_used_count} 件",
            f"エラー: {error_count} 件",
        ]
        if current_path:
            lines.append(f"現在: {current_path}")
        self.status_label.setText("  ".join(lines))

    def _scan_phase_label(self, phase: str) -> str:
        if phase == "collecting":
            return "対象ファイルを集めています。"
        if phase == "scanning":
            return "画像と映像を解析しています。"
        if phase == "detecting":
            return "重複・類似・ブレを検出しています。"
        if phase == "loading_results":
            return "表示する候補一覧を読み込んでいます。"
        return "処理中です。"

    def _group_label(self, group_type: str) -> str:
        if group_type == "duplicate_image":
            return "重複画像"
        if group_type == "duplicate_video":
            return "重複映像"
        if group_type == "blurry_image":
            return "ブレ画像"
        return "類似画像"

    def _format_size(self, size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        if size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        return f"{size_bytes / 1024 / 1024:.1f} MB"

    def _populate_result_tree(self, details: object) -> None:
        self._populating_results_tree = True
        self.result_tree.clear()
        try:
            duplicate_root = QTreeWidgetItem(["", "重複・類似画像", "", ""])
            blur_root = QTreeWidgetItem(["", "ブレ画像", "", ""])
            self.result_tree.addTopLevelItem(duplicate_root)
            self.result_tree.addTopLevelItem(blur_root)

            for detail in details:
                category = (
                    blur_root
                    if detail.summary.group_type == "blurry_image"
                    else duplicate_root
                )
                self._add_detection_group_item(category, detail)

            for root_item in (duplicate_root, blur_root):
                if root_item.childCount() == 0:
                    root_item.addChild(QTreeWidgetItem(["", "", "候補なし", ""]))
                root_item.setExpanded(True)

            self.result_tree.resizeColumnToContents(0)
            self.result_tree.resizeColumnToContents(1)
        finally:
            self._populating_results_tree = False

    def _add_detection_group_item(
        self,
        category: QTreeWidgetItem,
        detail: object,
    ) -> None:
        summary = detail.summary
        label = self._group_label(summary.group_type)
        group_item = QTreeWidgetItem(
            [
                "",
                label,
                f"{summary.item_count} 件中 {summary.selected_count} 件を隔離候補",
                summary.reason,
            ]
        )
        category.addChild(group_item)

        for item in detail.items:
            selected_label = "隔離する" if item.selected_by_default else "残す"
            info = self._item_info_label(item)
            child = QTreeWidgetItem(
                [
                    selected_label,
                    item.media_type,
                    item.path,
                    info,
                ]
            )
            child.setFlags(
                child.flags()
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
            )
            child.setCheckState(
                0,
                Qt.CheckState.Checked
                if item.selected_by_default
                else Qt.CheckState.Unchecked,
            )
            child.setData(0, Qt.ItemDataRole.UserRole, item.detection_group_item_id)
            child.setData(2, PATH_ROLE, item.path)
            child.setData(2, MEDIA_TYPE_ROLE, item.media_type)
            child.setIcon(2, self._thumbnail_icon(item.path, item.media_type))
            group_item.addChild(child)
        group_item.setExpanded(True)

    def _item_info_label(self, item: object) -> str:
        parts = [self._format_size(item.size_bytes), f"更新={item.modified_at}"]
        if item.blur_score is not None:
            parts.append(f"blur={item.blur_score:.2f}")
        if item.perceptual_hash is not None:
            parts.append(f"pHash={item.perceptual_hash}")
        return ", ".join(parts)

    def _thumbnail_icon(self, path: str, media_type: str) -> QIcon:
        if media_type != "image":
            return QIcon()
        cached = self._thumbnail_cache.get(path)
        if cached is not None:
            return cached

        pixmap = QPixmap()
        try:
            pixmap.loadFromData(Path(path).read_bytes())
        except OSError:
            icon = QIcon()
        else:
            if pixmap.isNull():
                icon = QIcon()
            else:
                thumbnail = pixmap.scaled(
                    72,
                    72,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                icon = QIcon(thumbnail)
        self._thumbnail_cache[path] = icon
        return icon

    def _preview_selected_item(self) -> None:
        items = self.result_tree.selectedItems()
        if not items:
            return
        item = items[0]
        path = item.data(2, PATH_ROLE)
        media_type = item.data(2, MEDIA_TYPE_ROLE)
        if not path or media_type != "image":
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText("画像ファイルを選択するとプレビューを表示します。")
            return

        pixmap = QPixmap()
        try:
            pixmap.loadFromData(Path(str(path)).read_bytes())
        except OSError:
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText("プレビューを読み込めませんでした。")
            return
        if pixmap.isNull():
            self.preview_label.setPixmap(QPixmap())
            self.preview_label.setText("プレビューを読み込めませんでした。")
            return

        target_size = self.preview_label.size()
        scaled = pixmap.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_label.setText("")
        self.preview_label.setPixmap(scaled)

    def _result_tree_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if self._populating_results_tree or column != 0:
            return
        group_item_id = item.data(0, Qt.ItemDataRole.UserRole)
        if group_item_id is None:
            return
        selected = item.checkState(0) == Qt.CheckState.Checked
        item.setText(0, "隔離する" if selected else "残す")
        ResultService(self.database).set_detection_item_selected(int(group_item_id), selected)
        selected_count = self._selected_tree_item_count()
        self.has_quarantine_candidates = selected_count > 0
        self.quarantine_button.setEnabled(self.has_quarantine_candidates)
        self.status_label.setText(f"隔離候補: {selected_count} 件")

    def _selected_tree_item_count(self) -> int:
        count = 0
        for top_index in range(self.result_tree.topLevelItemCount()):
            count += self._selected_tree_item_count_recursive(
                self.result_tree.topLevelItem(top_index)
            )
        return count

    def _selected_tree_item_count_recursive(self, item: QTreeWidgetItem) -> int:
        count = 0
        if item.data(0, Qt.ItemDataRole.UserRole) is not None:
            count += int(item.checkState(0) == Qt.CheckState.Checked)
        for child_index in range(item.childCount()):
            count += self._selected_tree_item_count_recursive(item.child(child_index))
        return count

    def _start_quarantine(self) -> None:
        if self.current_scan_session_id is None:
            QMessageBox.information(self, "結果なし", "先にスキャンを実行してください。")
            return
        selected_count = self._selected_tree_item_count()
        if selected_count == 0:
            QMessageBox.information(self, "候補なし", "隔離するファイルにチェックを入れてください。")
            return
        reply = QMessageBox.question(
            self,
            "隔離の確認",
            f"チェックした {selected_count} 件のファイルを隔離します。",
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

        completed_items = [item for item in result.items if item.status == "completed"]
        failed_items = [item for item in result.items if item.status != "completed"]

        if completed_items:
            self.results.appendPlainText("")
            self.results.appendPlainText("成功したファイル")
            for item in completed_items:
                self.results.appendPlainText(f"- 元: {item.original_path}")
                self.results.appendPlainText(f"  隔離先: {item.quarantined_path}")

        if failed_items:
            self.results.appendPlainText("")
            self.results.appendPlainText("失敗したファイル")
            for item in failed_items:
                self.results.appendPlainText(
                    f"- {self._quarantine_status_label(item.status)}: {item.original_path}"
                )
                self.results.appendPlainText(f"  隔離先: {item.quarantined_path}")
                if item.error_message:
                    self.results.appendPlainText(f"  理由: {item.error_message}")

        self.status_label.setText("隔離処理が完了しました。")
        self.has_quarantine_candidates = False
        self.quarantine_button.setEnabled(False)

    def _quarantine_status_label(self, status: str) -> str:
        if status == "copy_failed":
            return "コピー失敗"
        if status == "verify_failed":
            return "検証失敗"
        if status == "delete_failed":
            return "元ファイル削除失敗"
        return status

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
