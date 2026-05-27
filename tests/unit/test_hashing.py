from media_clinaer.analysis.hashing import calculate_sha256


def test_calculate_sha256(tmp_path):
    target = tmp_path / "sample.jpg"
    target.write_bytes(b"same content")

    assert (
        calculate_sha256(target)
        == "a636bd7cd42060a4d07fa1bfbcc010eb7794c2ba721e1e3e4c20335a15b66eaf"
    )
