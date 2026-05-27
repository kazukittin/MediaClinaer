from __future__ import annotations

from media_clinaer.models.detection_group import DetectionCandidate, DetectionGroup


class BlurryDetector:
    def __init__(self, blur_threshold: float) -> None:
        self.blur_threshold = blur_threshold

    def detect(self, candidates: list[DetectionCandidate]) -> list[DetectionGroup]:
        groups: list[DetectionGroup] = []
        for candidate in candidates:
            if candidate.blur_score is None:
                continue
            if candidate.blur_score < self.blur_threshold:
                groups.append(
                    DetectionGroup(
                        group_type="blurry_image",
                        confidence=0.7,
                        reason=(
                            f"blur_score {candidate.blur_score:.2f} "
                            f"< {self.blur_threshold:.2f}"
                        ),
                        items=[candidate],
                    )
                )
        return sorted(groups, key=lambda group: group.items[0].path)
