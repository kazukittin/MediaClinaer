from __future__ import annotations

from pathlib import Path

import imagehash
from PIL import Image


def calculate_perceptual_hash(path: Path) -> str:
    with Image.open(path) as image:
        return str(imagehash.phash(image))


def hash_distance(left: str, right: str) -> int:
    return (int(left, 16) ^ int(right, 16)).bit_count()
