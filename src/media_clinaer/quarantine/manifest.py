from __future__ import annotations

import json
from pathlib import Path

from media_clinaer.models.quarantine_record import QuarantineOutcome


class ManifestWriter:
    def write(self, session_dir: Path, outcomes: list[QuarantineOutcome]) -> Path:
        session_dir.mkdir(parents=True, exist_ok=True)
        manifest_path = session_dir / "manifest.json"
        payload = [
            {
                "media_file_id": outcome.plan.candidate.media_file_id,
                "original_path": str(outcome.plan.candidate.original_path),
                "quarantined_path": str(outcome.plan.quarantined_path),
                "status": outcome.status,
                "error_message": outcome.error_message,
            }
            for outcome in outcomes
        ]
        manifest_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return manifest_path
