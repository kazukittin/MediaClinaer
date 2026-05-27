from __future__ import annotations

from media_clinaer.models.detection_group import DetectionGroup


def count_group_items(groups: list[DetectionGroup]) -> int:
    return sum(len(group.items) for group in groups)
