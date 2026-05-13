from __future__ import annotations

from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def create_chrome_driver(
    *,
    headless: bool,
    chrome_binary: Path | None = None,
    user_data_dir: Path | None = None,
) -> webdriver.Chrome:
    options = Options()
    if chrome_binary is not None:
        options.binary_location = str(chrome_binary)
    if headless:
        options.add_argument("--headless=new")
    if user_data_dir is not None:
        options.add_argument(f"--user-data-dir={user_data_dir}")
    options.add_argument("--window-size=3080,3708")
    options.add_argument("--log-level=3")
    options.add_argument("--disable-notifications")
    options.add_argument("--no-first-run")
    options.add_argument("--no-default-browser-check")
    return webdriver.Chrome(options=options)
