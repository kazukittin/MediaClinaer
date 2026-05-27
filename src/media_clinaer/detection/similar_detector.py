from __future__ import annotations

from media_clinaer.analysis.image_similarity import hash_distance
from media_clinaer.models.detection_group import DetectionCandidate, DetectionGroup


class _BKNode:
    def __init__(self, hash_value: str, candidate: DetectionCandidate) -> None:
        self.hash_value = hash_value
        self.candidates = [candidate]
        self.children: dict[int, _BKNode] = {}


class _BKTree:
    def __init__(self) -> None:
        self.root: _BKNode | None = None

    def add(self, candidate: DetectionCandidate) -> None:
        if candidate.perceptual_hash is None:
            return
        if self.root is None:
            self.root = _BKNode(candidate.perceptual_hash, candidate)
            return

        node = self.root
        while True:
            distance = hash_distance(candidate.perceptual_hash, node.hash_value)
            if distance == 0:
                node.candidates.append(candidate)
                return
            child = node.children.get(distance)
            if child is None:
                node.children[distance] = _BKNode(candidate.perceptual_hash, candidate)
                return
            node = child

    def query(self, hash_value: str, max_distance: int) -> list[DetectionCandidate]:
        if self.root is None:
            return []
        matches: list[DetectionCandidate] = []
        stack = [self.root]
        while stack:
            node = stack.pop()
            distance = hash_distance(hash_value, node.hash_value)
            if distance <= max_distance:
                matches.extend(node.candidates)

            lower = distance - max_distance
            upper = distance + max_distance
            for child_distance, child in node.children.items():
                if lower <= child_distance <= upper:
                    stack.append(child)
        return matches


class SimilarDetector:
    def __init__(self, max_distance: int) -> None:
        self.max_distance = max_distance

    def detect(self, candidates: list[DetectionCandidate]) -> list[DetectionGroup]:
        parent = {candidate.media_file_id: candidate.media_file_id for candidate in candidates}
        tree = _BKTree()

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

        for candidate in candidates:
            if candidate.perceptual_hash is None:
                continue
            for match in tree.query(candidate.perceptual_hash, self.max_distance):
                if candidate.sha256 == match.sha256:
                    continue
                union(candidate.media_file_id, match.media_file_id)
            tree.add(candidate)

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
