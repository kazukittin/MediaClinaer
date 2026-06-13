from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DetectionCandidate:
    media_file_id: int
    path: str
    media_type: str
    size_bytes: int
    sha256: str | None = None
    perceptual_hash: str | None = None
    blur_score: float | None = None


@dataclass(frozen=True)
class DetectionGroup:
    group_type: str
    confidence: float
    reason: str
    items: list[DetectionCandidate]
