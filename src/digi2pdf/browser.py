from __future__ import annotations

from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def create_chrome_driver(*, headless: bool, chrome_binary: Path | None = None) -> webdriver.Chrome:
    options = Options()
    if chrome_binary is not None:
        options.binary_location = str(chrome_binary)
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=3080,3708")
    options.add_argument("--log-level=3")
    options.add_argument("--disable-notifications")
    return webdriver.Chrome(options=options)
