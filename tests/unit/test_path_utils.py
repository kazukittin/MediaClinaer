from pathlib import Path

from media_clinaer.scanner.path_utils import detect_media_type, get_extension


def test_detect_media_type_matches_configured_extensions():
    image_extensions = {".jpg", ".jpeg", ".png"}
    video_extensions = {".mp4"}

    assert detect_media_type(Path("photo.JPG"), image_extensions, video_extensions) == "image"
    assert detect_media_type(Path("movie.mp4"), image_extensions, video_extensions) == "video"
    assert detect_media_type(Path("note.txt"), image_extensions, video_extensions) is None


def test_get_extension_is_lowercase():
    assert get_extension(Path("PHOTO.JPEG")) == ".jpeg"
