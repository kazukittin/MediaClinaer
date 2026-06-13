from __future__ import annotations

from enum import StrEnum


class EventType(StrEnum):
    APP_STARTED = "app_started"
    APP_FOLDER_NOT_WRITABLE = "app_folder_not_writable"
    SCAN_STARTED = "scan_started"
    SCAN_COMPLETED = "scan_completed"
    SCAN_CANCELLED = "scan_cancelled"
    FILE_SCAN_FAILED = "file_scan_failed"
    LONG_PATH_SKIPPED = "long_path_skipped"
    CACHE_REUSED = "cache_reused"
    BLURRY_DETECTED = "blurry_detected"
    QUARANTINE_STARTED = "quarantine_started"
    QUARANTINE_COMPLETED = "quarantine_completed"
    QUARANTINE_COPY_FAILED = "quarantine_copy_failed"
    QUARANTINE_DELETE_FAILED = "quarantine_delete_failed"
    QUARANTINE_ROLLBACK_FAILED = "quarantine_rollback_failed"
    NAS_FOLDER_UNAVAILABLE = "nas_folder_unavailable"
    NAS_PERMISSION_DENIED = "nas_permission_denied"
    FOLDER_SCAN_FAILED = "folder_scan_failed"
    METADATA_READ_FAILED = "metadata_read_failed"
    IMAGE_ANALYSIS_FAILED = "image_analysis_failed"
