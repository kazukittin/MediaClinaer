from media_clinaer.analysis.blur_detector import calculate_blur_score
from media_clinaer.detection.blurry_detector import BlurryDetector
from media_clinaer.models.detection_group import DetectionCandidate
from tests.image_helpers import write_blurry_test_image, write_test_image


def test_calculate_blur_score_is_lower_for_blurry_image(tmp_path):
    sharp = tmp_path / "sharp.jpg"
    blurry = tmp_path / "blurry.jpg"
    write_test_image(sharp)
    write_blurry_test_image(blurry)

    assert calculate_blur_score(sharp) > calculate_blur_score(blurry)


def test_blurry_detector_creates_single_item_groups():
    candidates = [
        DetectionCandidate(1, "sharp.jpg", "image", "sha-a", 10, blur_score=500.0),
        DetectionCandidate(2, "blurry.jpg", "image", "sha-b", 10, blur_score=20.0),
    ]

    groups = BlurryDetector(blur_threshold=100.0).detect(candidates)

    assert len(groups) == 1
    assert groups[0].group_type == "blurry_image"
    assert groups[0].items[0].media_file_id == 2
