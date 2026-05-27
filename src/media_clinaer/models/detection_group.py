from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DetectionCandidate:
    media_file_id: int
    path: str
    media_type: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True)
class DetectionGroup:
    group_type: str
    confidence: float
    reason: str
    items: list[DetectionCandidate]
