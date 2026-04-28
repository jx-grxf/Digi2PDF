from __future__ import annotations

from selenium import webdriver
from selenium.webdriver.chrome.options import Options


def create_chrome_driver(*, headless: bool) -> webdriver.Chrome:
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=3080,3708")
    options.add_argument("--log-level=3")
    options.add_argument("--disable-notifications")
    return webdriver.Chrome(options=options)
