from __future__ import annotations

import hashlib
from pathlib import Path

from media_clinaer.models.quarantine_record import QuarantineCandidate, QuarantinePlan


class QuarantinePlanner:
    def __init__(self, quarantine_dir: Path) -> None:
        self.quarantine_dir = quarantine_dir

    def create_session_dir(self, session_label: str) -> Path:
        return self.quarantine_dir / session_label / "files"

    def build_plan(
        self,
        candidate: QuarantineCandidate,
        *,
        session_label: str,
    ) -> QuarantinePlan:
        files_dir = self.create_session_dir(session_label)
        destination = files_dir / candidate.original_path.name
        if destination.exists():
            destination = self._with_short_hash(destination, candidate)
        return QuarantinePlan(candidate=candidate, quarantined_path=destination)

    def _with_short_hash(
        self,
        destination: Path,
        candidate: QuarantineCandidate,
    ) -> Path:
        digest = hashlib.sha1(candidate.original_normalized_path.encode("utf-8")).hexdigest()
        return destination.with_name(
            f"{destination.stem}__{digest[:8]}{destination.suffix}"
        )
