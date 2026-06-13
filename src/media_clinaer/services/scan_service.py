from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from media_clinaer.analysis.blur_detector import calculate_blur_score
from media_clinaer.config.models import AppConfig
from media_clinaer.logging.events import EventType
from media_clinaer.logging.logger import JsonLineLogger
from media_clinaer.models.media_file import MediaFileRecord
from media_clinaer.scanner.file_collector import FileCollector
from media_clinaer.scanner.metadata_reader import MetadataReader
from media_clinaer.services.cache_service import CacheService
from media_clinaer.storage.database import Database
from media_clinaer.storage.repositories import AnalysisCacheRepository, ScanRepository


SCAN_COMMIT_BATCH_SIZE = 200
PROGRESS_UPDATE_INTERVAL = 100


@dataclass(frozen=True)
class ScanResult:
    session_id: int
    total_files: int
    scanned_files: int
    cache_used_count: int
    error_count: int


@dataclass(frozen=True)
class ScanProgress:
    phase: str
    total_files: int
    processed_files: int
    cache_used_count: int
    error_count: int
    current_path: str | None = None


class ScanService:
    def __init__(
        self,
        database: Database,
        config: AppConfig,
        logger: JsonLineLogger,
    ) -> None:
        self.database = database
        self.config = config
        self.logger = logger

    def scan(
        self,
        target_paths: list[str] | None = None,
        progress_callback: Callable[[ScanProgress], None] | None = None,
    ) -> ScanResult:
        targets = target_paths if target_paths is not None else self.config.scan.target_paths
        connection = self.database.connect()
        try:
            scan_repository = ScanRepository(connection)
            cache_repository = AnalysisCacheRepository(connection)
            cache_service = CacheService(cache_repository)
            collector = FileCollector(self.config.scan, self.logger)
            metadata_reader = MetadataReader(self.config.scan)

            session = scan_repository.create_session(targets)
            self.logger.info(
                EventType.SCAN_STARTED,
                "Scan started",
                details={"session_id": session.id, "targets": targets},
            )

            self._emit_progress(
                progress_callback,
                ScanProgress(
                    phase="collecting",
                    total_files=0,
                    processed_files=0,
                    cache_used_count=0,
                    error_count=0,
                ),
            )

            paths = list(collector.collect(targets))
            total_files = len(paths)
            scanned_files = 0
            cache_used_count = 0
            error_count = 0

            self._emit_progress(
                progress_callback,
                ScanProgress(
                    phase="scanning",
                    total_files=total_files,
                    processed_files=0,
                    cache_used_count=0,
                    error_count=0,
                ),
            )

            pending_writes = 0
            for path in paths:
                try:
                    metadata = metadata_reader.read(path)
                    record = cache_service.build_from_cache(metadata)
                    if record is not None:
                        cache_used_count += 1
                        self.logger.debug(
                            EventType.CACHE_REUSED,
                            "Analysis cache reused",
                            path=str(path),
                        )
                    else:
                        sha256 = None
                        perceptual_hash = None
                        blur_score = None
                        if metadata.media_type == "image":
                            blur_score = calculate_blur_score(path)
                        record = MediaFileRecord(
                            metadata=metadata,
                            sha256=sha256,
                            perceptual_hash=perceptual_hash,
                            blur_score=blur_score,
                            cache_status="fresh",
                        )
                        cache_service.save_success(record, commit=False)
                        pending_writes += 1
                    scan_repository.insert_media_file(session.id, record, commit=False)
                    pending_writes += 1
                    if pending_writes >= SCAN_COMMIT_BATCH_SIZE:
                        connection.commit()
                        pending_writes = 0
                    scanned_files += 1
                except OSError as exc:
                    error_count += 1
                    self.logger.warning(
                        EventType.FILE_SCAN_FAILED,
                        f"Failed to scan file: {exc}",
                        path=str(path),
                    )
                except Exception as exc:
                    error_count += 1
                    self.logger.error(
                        EventType.FILE_SCAN_FAILED,
                        f"Unexpected scan error: {exc}",
                        path=str(path),
                    )
                finally:
                    processed_files = scanned_files + error_count
                    if (
                        processed_files == total_files
                        or processed_files % PROGRESS_UPDATE_INTERVAL == 0
                    ):
                        self._emit_progress(
                            progress_callback,
                            ScanProgress(
                                phase="scanning",
                                total_files=total_files,
                                processed_files=processed_files,
                                cache_used_count=cache_used_count,
                                error_count=error_count,
                                current_path=str(path),
                            ),
                        )

            if pending_writes:
                connection.commit()
            scan_repository.finish_session(
                session.id,
                status="completed",
                total_files=total_files,
                scanned_files=scanned_files,
                cache_used_count=cache_used_count,
                error_count=error_count,
            )
            self.logger.info(
                EventType.SCAN_COMPLETED,
                "Scan completed",
                details={
                    "session_id": session.id,
                    "total_files": total_files,
                    "scanned_files": scanned_files,
                    "cache_used_count": cache_used_count,
                    "error_count": error_count,
                },
            )
            return ScanResult(
                session_id=session.id,
                total_files=total_files,
                scanned_files=scanned_files,
                cache_used_count=cache_used_count,
                error_count=error_count,
            )
        finally:
            connection.close()

    def _emit_progress(
        self,
        progress_callback: Callable[[ScanProgress], None] | None,
        progress: ScanProgress,
    ) -> None:
        if progress_callback is not None:
            progress_callback(progress)
