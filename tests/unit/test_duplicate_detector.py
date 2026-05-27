from media_clinaer.detection.duplicate_detector import DuplicateDetector
from media_clinaer.models.detection_group import DetectionCandidate


def test_duplicate_detector_groups_matching_hashes_by_media_type():
    candidates = [
        DetectionCandidate(1, "a.jpg", "image", "same", 4),
        DetectionCandidate(2, "b.jpg", "image", "same", 4),
        DetectionCandidate(3, "c.mp4", "video", "same", 4),
        DetectionCandidate(4, "d.mp4", "video", "same", 4),
        DetectionCandidate(5, "e.jpg", "image", "other", 4),
    ]

    groups = DuplicateDetector().detect(candidates)

    assert [group.group_type for group in groups] == [
        "duplicate_image",
        "duplicate_video",
    ]
    assert [len(group.items) for group in groups] == [2, 2]
