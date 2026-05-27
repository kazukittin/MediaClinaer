from media_clinaer.detection.similar_detector import SimilarDetector
from media_clinaer.models.detection_group import DetectionCandidate


def test_similar_detector_groups_images_with_close_phash():
    candidates = [
        DetectionCandidate(1, "a.jpg", "image", "sha-a", 10, "0000000000000000"),
        DetectionCandidate(2, "b.jpg", "image", "sha-b", 10, "0000000000000001"),
        DetectionCandidate(3, "c.jpg", "image", "sha-c", 10, "ffffffffffffffff"),
    ]

    groups = SimilarDetector(max_distance=2).detect(candidates)

    assert len(groups) == 1
    assert groups[0].group_type == "similar_image"
    assert [item.media_file_id for item in groups[0].items] == [1, 2]
