from __future__ import annotations

from media_clinaer.analysis.image_similarity import hash_distance
from media_clinaer.models.detection_group import DetectionCandidate, DetectionGroup


class SimilarDetector:
    def __init__(self, max_distance: int) -> None:
        self.max_distance = max_distance

    def detect(self, candidates: list[DetectionCandidate]) -> list[DetectionGroup]:
        parent = {candidate.media_file_id: candidate.media_file_id for candidate in candidates}

        def find(item_id: int) -> int:
            while parent[item_id] != item_id:
                parent[item_id] = parent[parent[item_id]]
                item_id = parent[item_id]
            return item_id

        def union(left_id: int, right_id: int) -> None:
            left_root = find(left_id)
            right_root = find(right_id)
            if left_root != right_root:
                parent[right_root] = left_root

        for left_index, left in enumerate(candidates):
            if left.perceptual_hash is None:
                continue
            for right in candidates[left_index + 1 :]:
                if right.perceptual_hash is None:
                    continue
                if left.sha256 == right.sha256:
                    continue
                distance = hash_distance(left.perceptual_hash, right.perceptual_hash)
                if distance <= self.max_distance:
                    union(left.media_file_id, right.media_file_id)

        grouped: dict[int, list[DetectionCandidate]] = {}
        for candidate in candidates:
            grouped.setdefault(find(candidate.media_file_id), []).append(candidate)

        groups: list[DetectionGroup] = []
        for items in grouped.values():
            if len(items) < 2:
                continue
            groups.append(
                DetectionGroup(
                    group_type="similar_image",
                    confidence=0.8,
                    reason=f"pHash distance <= {self.max_distance}",
                    items=sorted(items, key=lambda item: item.path),
                )
            )
        return sorted(groups, key=lambda group: group.items[0].path)
