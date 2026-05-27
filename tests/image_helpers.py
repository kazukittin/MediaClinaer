from pathlib import Path

from PIL import ImageFilter
from PIL import Image, ImageDraw


def write_test_image(path: Path, *, variant: int = 0) -> None:
    image = Image.new("RGB", (64, 64), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((8, 8, 56, 56), outline="black", width=3)
    draw.line((8, 8 + variant, 56, 56), fill="blue", width=2)
    draw.ellipse((22, 22, 42, 42), fill="red")
    image.save(path)


def write_blurry_test_image(path: Path) -> None:
    image = Image.new("RGB", (64, 64), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((8, 8, 56, 56), outline="black", width=3)
    draw.line((8, 8, 56, 56), fill="blue", width=2)
    draw.ellipse((22, 22, 42, 42), fill="red")
    image = image.filter(ImageFilter.GaussianBlur(radius=4))
    image.save(path)
