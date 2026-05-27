from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from media_clinaer.logging.events import EventType
from media_clinaer.logging.logger import JsonLineLogger
from media_clinaer.quarantine.executor import QuarantineExecutor
from media_clinaer.quarantine.manifest import ManifestWriter
from media_clinaer.quarantine.planner import QuarantinePlanner
from media_clinaer.storage.database import Database
from media_clinaer.storage.repositories import QuarantineRepository


@dataclass(frozen=True)
class QuarantineResult:
    scan_session_id: int
    total_count: int
    completed_count: int
    failed_count: int
    manifest_path: Path


class QuarantineService:
    def __init__(
        self,
        database: Database,
        logger: JsonLineLogger,
        quarantine_dir: Path,
        timezone: str = "Asia/Tokyo",
    ) -> None:
        self.database = database
        self.logger = logger
        self.quarantine_dir = quarantine_dir
        self.timezone = ZoneInfo(timezone)

    def quarantine_selected_defaults(self, scan_session_id: int) -> QuarantineResult:
        session_label = datetime.now(self.timezone).strftime("%Y%m%d_%H%M%S")
        planner = QuarantinePlanner(self.quarantine_dir)
        executor = QuarantineExecutor()
        manifest_writer = ManifestWriter()
        session_dir = self.quarantine_dir / session_label

        connection = self.database.connect()
        try:
            repository = QuarantineRepository(connection)
            candidates = repository.list_selected_candidates(scan_session_id)
            outcomes = []

            self.logger.info(
                EventType.QUARANTINE_STARTED,
                "Quarantine started",
                details={
                    "scan_session_id": scan_session_id,
                    "candidate_count": len(candidates),
                },
            )

            for candidate in candidates:
                plan = planner.build_plan(candidate, session_label=session_label)
                outcome = executor.execute(plan)
                repository.insert_outcome(outcome)
                outcomes.append(outcome)
                if outcome.status == "completed":
                    self.logger.info(
                        EventType.QUARANTINE_COMPLETED,
                        "File quarantined",
                        path=str(candidate.original_path),
                        details={"quarantined_path": str(plan.quarantined_path)},
                    )
                elif outcome.status == "delete_failed":
                    self.logger.warning(
                        EventType.QUARANTINE_DELETE_FAILED,
                        "File copied but original delete failed",
                        path=str(candidate.original_path),
                        details={
                            "quarantined_path": str(plan.quarantined_path),
                            "error": outcome.error_message,
                        },
                    )
                else:
                    self.logger.warning(
                        EventType.QUARANTINE_COPY_FAILED,
                        "File quarantine failed",
                        path=str(candidate.original_path),
                        details={"error": outcome.error_message},
                    )

            manifest_path = manifest_writer.write(session_dir, outcomes)
            completed_count = sum(1 for outcome in outcomes if outcome.status == "completed")
            failed_count = len(outcomes) - completed_count
            return QuarantineResult(
                scan_session_id=scan_session_id,
                total_count=len(outcomes),
                completed_count=completed_count,
                failed_count=failed_count,
                manifest_path=manifest_path,
            )
        finally:
            connection.close()
