from __future__ import annotations

from pathlib import Path

import cv2


def calculate_blur_score(path: Path) -> float:
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f"Failed to read image for blur detection: {path}")
    return float(cv2.Laplacian(image, cv2.CV_64F).var())
