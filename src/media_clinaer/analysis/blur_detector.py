from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def calculate_blur_score(path: Path) -> float:
    image_bytes = np.fromfile(path, dtype=np.uint8)
    image = cv2.imdecode(image_bytes, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f"Failed to read image for blur detection: {path}")
    return float(cv2.Laplacian(image, cv2.CV_64F).var())
