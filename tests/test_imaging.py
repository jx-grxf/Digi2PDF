from __future__ import annotations

from pathlib import Path

from PIL import Image

from digi2pdf.imaging import crop_image, images_are_identical, save_images_as_pdf
from digi2pdf.models import CropBox


def test_crop_image(tmp_path: Path) -> None:
    image_path = tmp_path / "page.png"
    Image.new("RGB", (10, 10), "white").save(image_path)

    crop_image(image_path, CropBox(left=2, top=2, right=8, bottom=9))

    with Image.open(image_path) as image:
        assert image.size == (6, 7)


def test_images_are_identical(tmp_path: Path) -> None:
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    Image.new("RGB", (4, 4), "red").save(first)
    Image.new("RGB", (4, 4), "red").save(second)

    assert images_are_identical(first, second)


def test_save_images_as_pdf(tmp_path: Path) -> None:
    page = tmp_path / "page.png"
    pdf = tmp_path / "book.pdf"
    Image.new("RGB", (20, 20), "blue").save(page)

    save_images_as_pdf([page], pdf)

    assert pdf.exists()
    assert pdf.stat().st_size > 0
