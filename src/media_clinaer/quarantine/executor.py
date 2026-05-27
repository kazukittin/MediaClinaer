from __future__ import annotations

import shutil
import stat
from pathlib import Path

from media_clinaer.models.quarantine_record import QuarantineOutcome, QuarantinePlan


class QuarantineExecutor:
    def execute(self, plan: QuarantinePlan) -> QuarantineOutcome:
        source = plan.candidate.original_path
        destination = plan.quarantined_path
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        except OSError as exc:
            self._remove_incomplete(destination)
            return QuarantineOutcome(plan, "copy_failed", str(exc))

        if not self._verify_size(source, destination):
            self._remove_incomplete(destination)
            return QuarantineOutcome(plan, "copy_failed", "Copied file size mismatch")

        try:
            self._delete_source(source)
        except OSError as exc:
            return QuarantineOutcome(plan, "delete_failed", str(exc))

        return QuarantineOutcome(plan, "completed")

    def _delete_source(self, source: Path) -> None:
        try:
            source.unlink()
        except PermissionError:
            source.chmod(source.stat().st_mode | stat.S_IWRITE)
            source.unlink()

    def _verify_size(self, source: Path, destination: Path) -> bool:
        try:
            return source.stat().st_size == destination.stat().st_size
        except OSError:
            return False

    def _remove_incomplete(self, destination: Path) -> None:
        try:
            if destination.exists():
                destination.unlink()
        except OSError:
            pass
