from __future__ import annotations

from collections import defaultdict

from media_clinaer.models.detection_group import DetectionCandidate, DetectionGroup


class DuplicateDetector:
    def detect(self, candidates: list[DetectionCandidate]) -> list[DetectionGroup]:
        grouped: dict[tuple[str, str], list[DetectionCandidate]] = defaultdict(list)
        for candidate in candidates:
            grouped[(candidate.media_type, candidate.sha256)].append(candidate)

        detection_groups: list[DetectionGroup] = []
        for (media_type, sha256), items in grouped.items():
            if len(items) < 2:
                continue
            group_type = "duplicate_image" if media_type == "image" else "duplicate_video"
            detection_groups.append(
                DetectionGroup(
                    group_type=group_type,
                    confidence=1.0,
                    reason=f"SHA-256 matched: {sha256}",
                    items=sorted(items, key=lambda item: item.path),
                )
            )
        return sorted(
            detection_groups,
            key=lambda group: (group.group_type, group.items[0].sha256),
        )
