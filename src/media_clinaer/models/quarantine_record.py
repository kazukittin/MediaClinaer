from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class QuarantineCandidate:
    media_file_id: int
    original_path: Path
    original_normalized_path: str
    original_size_bytes: int
    original_modified_at: str
    source_storage_type: str


@dataclass(frozen=True)
class QuarantinePlan:
    candidate: QuarantineCandidate
    quarantined_path: Path


@dataclass(frozen=True)
class QuarantineOutcome:
    plan: QuarantinePlan
    status: str
    error_message: str | None = None
