from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw

from digi2pdf.imaging import (
    crop_image,
    image_has_page_content,
    images_are_identical,
    save_images_as_pdf,
)
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


def test_image_has_page_content_rejects_blank_capture(tmp_path: Path) -> None:
    blank = tmp_path / "blank.png"
    page = tmp_path / "page.png"
    Image.new("RGB", (20, 20), "black").save(blank)
    image = Image.new("RGB", (40, 40), "white")
    ImageDraw.Draw(image).text((4, 4), "page", fill="black")
    image.save(page)

    assert not image_has_page_content(blank)
    assert image_has_page_content(page)


def test_save_images_as_pdf(tmp_path: Path) -> None:
    page = tmp_path / "page.png"
    pdf = tmp_path / "book.pdf"
    Image.new("RGB", (20, 20), "blue").save(page)

    save_images_as_pdf([page], pdf)

    assert pdf.exists()
    assert pdf.stat().st_size > 0


def test_save_images_as_pdf_keeps_all_pages(tmp_path: Path) -> None:
    pages = []
    for index, color in enumerate(("blue", "green", "red"), start=1):
        page = tmp_path / f"page-{index}.png"
        Image.new("RGB", (20, 20), color).save(page)
        pages.append(page)
    pdf = tmp_path / "book.pdf"

    save_images_as_pdf(pages, pdf)

    contents = pdf.read_bytes()
    assert len(re.findall(rb"/Type\s*/Page\b", contents)) == 3
