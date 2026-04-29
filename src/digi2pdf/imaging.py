from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, JpegImagePlugin

from digi2pdf.models import CropBox

# Pillow's PDF writer delegates RGB pages to the JPEG plugin. Importing the
# plugin explicitly keeps PDF export stable with lazy plugin registration.
_JPEG_PLUGIN = JpegImagePlugin


def crop_image(image_path: Path, crop_box: CropBox) -> None:
    with Image.open(image_path) as image:
        cropped = image.crop((crop_box.left, crop_box.top, crop_box.right, crop_box.bottom))
        cropped.save(image_path)


def images_are_identical(first_path: Path, second_path: Path) -> bool:
    if not first_path.exists() or not second_path.exists():
        return False

    with Image.open(first_path) as first, Image.open(second_path) as second:
        if first.size != second.size:
            return False
        return bool(np.array_equal(np.array(first), np.array(second)))


def image_has_page_content(image_path: Path) -> bool:
    with Image.open(image_path) as image:
        grayscale = image.convert("L")
        pixels = np.array(grayscale)
        deviation = float(pixels.std())
        return deviation >= 3.0


def save_images_as_pdf(image_paths: list[Path], pdf_path: Path) -> None:
    if not image_paths:
        raise ValueError("Cannot create a PDF without pages.")

    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(image_paths[0]) as first_image:
        first_page = first_image.convert("RGB")
        remaining_pages = []
        try:
            for path in image_paths[1:]:
                with Image.open(path) as image:
                    remaining_pages.append(image.convert("RGB"))
            first_page.save(pdf_path, save_all=True, append_images=remaining_pages, resolution=300.0)
        finally:
            for page in remaining_pages:
                page.close()
            first_page.close()
