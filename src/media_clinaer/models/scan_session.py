from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScanSession:
    id: int
    status: str
