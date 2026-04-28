from __future__ import annotations

import shutil
from pathlib import Path
from time import sleep

import numpy as np
from PIL import Image
from selenium.common import (
    ElementNotInteractableException,
    NoSuchElementException,
    TimeoutException,
)
from selenium.webdriver import ActionChains, Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from digi2pdf.imaging import crop_image, images_are_identical, save_images_as_pdf
from digi2pdf.models import BookChoice, BookType, CropBox, ProgressSink, RuntimeOptions
from digi2pdf.paths import safe_filename
from digi2pdf.tui import ask_book, ask_credentials, ask_sub_book


class Digi2PDFSession:
    def __init__(self, browser: WebDriver, options: RuntimeOptions, sink: ProgressSink) -> None:
        self.browser = browser
        self.options = options
        self.sink = sink
        self.wait = WebDriverWait(browser, 20)

    def run(self) -> None:
        self.sink.step("Opening Digi4School overview")
        self.browser.get("https://digi4school.at/overview")
        self.wait.until(
            EC.any_of(
                EC.visibility_of_element_located((By.XPATH, '//*[@id="ion-input-0"]')),
                EC.visibility_of_element_located((By.CLASS_NAME, "entry-heading")),
            )
        )

        if self._exists(By.ID, "ion-input-0"):
            self._login()

        book_names, book_elements = self._get_books()
        if not book_names:
            raise RuntimeError("No books found after login.")

        selected = "all" if self.options.all_books else ask_book(book_names)
        if selected is None:
            self.sink.warn("Cancelled before selecting a book.")
            return

        if selected == "all":
            self._save_all_books(book_elements)
            return

        assert isinstance(selected, BookChoice)
        self._open_book(selected, book_elements[selected.index])
        self._save_current_book(selected.title)

    def _login(self) -> None:
        email, password = ask_credentials()
        if not email or not password:
            raise RuntimeError("Email and password are required for login.")

        self.sink.step("Submitting Digi4School login")
        email_field = self.browser.find_element(By.XPATH, '//*[@id="ion-input-0"]')
        password_field = self.browser.find_element(By.XPATH, '//*[@id="ion-input-1"]')
        email_field.clear()
        email_field.send_keys(email)
        password_field.clear()
        password_field.send_keys(password)

        shadow_host = self.browser.find_element(
            By.XPATH,
            '//*[@id="main-content"]/app-login/ion-content/div[1]/div/form/div[2]/ion-button[1]',
        )
        self.browser.execute_script(
            "arguments[0].shadowRoot.querySelector('button[type=\"submit\"]').click();",
            shadow_host,
        )
        sleep(self.options.delay_seconds + 1)

        if self._exists(By.XPATH, '//*[@id="ion-input-0"]'):
            if self._exists(By.CLASS_NAME, "alert-button"):
                self.browser.find_element(By.CLASS_NAME, "alert-button").click()
            raise RuntimeError("Login failed. Check your Digi4School credentials.")

    def _get_books(self) -> tuple[list[str], list[object]]:
        self.browser.execute_script("document.body.style.zoom='10%'")
        book_elements = self.browser.find_elements(By.CLASS_NAME, "entry-heading")
        book_names = [book.text.strip() for book in book_elements if book.text.strip()]
        return book_names, book_elements

    def _open_book(self, choice: BookChoice, element: object) -> None:
        self.sink.step(f"Opening {choice.title}")
        element.click()
        sleep(self.options.delay_seconds)
        self.browser.switch_to.window(self.browser.window_handles[-1])

    def _save_current_book(self, title: str) -> None:
        sleep(self.options.delay_seconds + 1)
        book_type = self._detect_book_type()

        if book_type is BookType.SUB_BOOKS:
            title = self._select_sub_book(title)
            sleep(self.options.delay_seconds + 1)
            book_type = self._detect_book_type()

        if book_type is BookType.DIGI4SCHOOL:
            self._prepare_digi4school(title)
        elif book_type is BookType.SCOOK:
            self._prepare_scook(title)
        elif book_type is BookType.BIBOX:
            self._prepare_bibox(title)
        else:
            raise RuntimeError(
                "Unsupported book type. Try increasing the page delay if the book is still loading."
            )

    def _select_sub_book(self, parent_title: str) -> str:
        self.sink.step("Sub-books detected")
        elements = self.browser.find_elements(By.CLASS_NAME, "tx")
        names = [element.text.strip() for element in elements if element.text.strip()]
        selected = ask_sub_book(names)
        if selected is None:
            raise RuntimeError("No sub-book selected.")

        elements[selected.index].click()
        sleep(self.options.delay_seconds)
        self.browser.switch_to.window(self.browser.window_handles[-1])
        return f"{parent_title}/{selected.title}"

    def _detect_book_type(self) -> BookType:
        sleep(self.options.delay_seconds + 2)
        if self._exists(By.CLASS_NAME, "tx"):
            return BookType.SUB_BOOKS
        if self._exists(By.XPATH, '//*[@id="txtPage"]'):
            return BookType.DIGI4SCHOOL
        if self._exists(By.XPATH, '//*[@id="page-product-viewer"]'):
            return BookType.SCOOK
        if self._exists(
            By.XPATH,
            '//*[@id="bbx"]/app-root/app-book/div/mat-sidenav-container/mat-sidenav-content/app-double-page-view/div[1]/div[2]/app-book-page-viewer/div/app-book-gl/div/canvas',
        ) or self._exists(By.XPATH, '//*[@id="undefined"]/app-book-gl/div/canvas'):
            return BookType.BIBOX
        return BookType.UNKNOWN

    def _prepare_digi4school(self, title: str) -> None:
        self._click_if_visible(By.CLASS_NAME, "tlypageguide_dismiss", "Closing infotour popup")
        self._click_if_visible(By.ID, "routlineClose", "Closing outline popup")
        sleep(self.options.delay_seconds)
        self.browser.find_element(By.ID, "btnFirst").click()
        sleep(self.options.delay_seconds)
        if self._exists(By.ID, "btnZoomHeight"):
            self.browser.find_element(By.ID, "btnZoomHeight").click()

        rect = self.browser.execute_script(
            "return document.getElementById('pg1Overlay').getBoundingClientRect();"
        )
        self._capture_book(title, BookType.DIGI4SCHOOL, CropBox.from_browser_rect(rect))

    def _prepare_scook(self, title: str) -> None:
        sleep(self.options.delay_seconds)
        self._click_if_visible(
            By.XPATH,
            '//*[@id="unity-veritas-product-viewer-component-67076960"]/div[1]/aside/div[1]/div[1]/span',
            "Closing chapter panel",
        )
        iframe = self.browser.find_elements(By.TAG_NAME, "iframe")[0]
        iframe_rect = self.browser.execute_script(
            "return document.getElementsByClassName('book-frame')[0].getBoundingClientRect();"
        )
        self.browser.switch_to.frame(iframe)
        sleep(self.options.delay_seconds)
        rect = self.browser.execute_script(
            "return document.getElementsByClassName('annotations-drawable')[0].getBoundingClientRect();"
        )
        crop_box = CropBox(
            left=int(rect["left"] + iframe_rect["left"]),
            top=int(rect["top"] + iframe_rect["top"]),
            right=int(rect["right"] + iframe_rect["left"]),
            bottom=int(rect["bottom"] + iframe_rect["top"]),
        )
        self.browser.find_element(
            By.XPATH, "/html/body/div[3]/div/div[2]/div/div/div/div[5]/div/div[2]/div[2]/button[1]"
        ).click()
        self._capture_book(title, BookType.SCOOK, crop_box)

    def _prepare_bibox(self, title: str) -> None:
        wait = WebDriverWait(self.browser, 20)
        self.browser.set_window_size(2580, 3708)

        if self._exists(By.ID, "flip-right"):
            self.sink.step("Switching old BiBox viewer to the new viewer")
            self.browser.find_element(By.XPATH, '//*[@id="version-switch"]').click()
            sleep(self.options.delay_seconds)
            self.browser.find_element(
                By.XPATH,
                '//*[@id="mat-mdc-dialog-2"]/div/div/app-version-switch-modal/app-dialog-actions/div/div/button[2]',
            ).click()
            sleep(self.options.delay_seconds)

        self._click_if_visible(
            By.XPATH,
            '//*[@id="cdk-dialog-0"]/bbx-notification-modal/app-standard-popup/div/div[3]/button',
            "Closing BiBox notification popup",
        )
        wait.until(EC.element_to_be_clickable((By.XPATH, '//*[@id="page-nav-layout"]/app-toggle-item[1]/button/i')))
        self.browser.find_element(By.XPATH, '//*[@id="page-nav-layout"]/app-toggle-item[1]/button/i').click()

        wait.until(EC.visibility_of_element_located((By.XPATH, '//*[@id="page-name"]')))
        page_field = self.browser.find_element(By.XPATH, '//*[@id="page-name"]')
        page_field.send_keys("1")
        page_field.send_keys(Keys.ENTER)
        sleep(self.options.delay_seconds)

        temp_path = self.options.output_dir / ".digi2pdf_bibox_probe.png"
        self.browser.save_screenshot(str(temp_path))
        crop_box = self._calculate_bibox_crop_box(temp_path)
        temp_path.unlink(missing_ok=True)
        self._capture_book(title, BookType.BIBOX, crop_box)

    def _capture_book(self, title: str, book_type: BookType, crop_box: CropBox) -> None:
        book_dir = self.options.output_dir / safe_filename(title)
        if book_dir.exists() and not self.options.keep_images:
            shutil.rmtree(book_dir)
        book_dir.mkdir(parents=True, exist_ok=True)

        action = ActionChains(self.browser)
        self._nudge_mouse(action)
        page_paths: list[Path] = []
        page = 1

        self.sink.step(f"Capturing {title}")
        while True:
            page_path = book_dir / f"{page:04d}.png"
            self.browser.save_screenshot(str(page_path))
            crop_image(page_path, crop_box)
            page_paths.append(page_path)
            self.sink.step(f"Captured page {page}")

            if len(page_paths) > 1 and images_are_identical(page_paths[-2], page_paths[-1]):
                page_paths[-1].unlink(missing_ok=True)
                page_paths.pop()
                break

            self._next_page(book_type)
            self._nudge_mouse(action)
            sleep(self.options.delay_seconds)
            page += 1

        pdf_path = book_dir / f"{book_dir.name}.pdf"
        save_images_as_pdf(page_paths, pdf_path)
        self.sink.step(f"PDF written: {pdf_path}")

        if not self.options.keep_images:
            for page_path in page_paths:
                page_path.unlink(missing_ok=True)

    def _next_page(self, book_type: BookType) -> None:
        if book_type is BookType.DIGI4SCHOOL:
            self.browser.find_element(By.ID, "btnNext").click()
        elif book_type is BookType.SCOOK:
            self.browser.find_element(
                By.XPATH, '//*[@id="content-0"]/div/div/div/div[5]/div/div[2]/div[2]/button[3]'
            ).click()
        elif book_type is BookType.BIBOX:
            self.browser.find_element(By.XPATH, '//*[@id="book-frame"]/nav/div[2]/div/a[2]').click()
        else:
            raise RuntimeError(f"Cannot navigate unknown book type: {book_type.value}")

    def _save_all_books(self, book_elements: list[object]) -> None:
        for index, element in enumerate(book_elements):
            title = element.text.strip() or f"book-{index + 1}"
            self._open_book(BookChoice(title=title, index=index), element)
            try:
                self._save_current_book(title)
            except Exception as error:
                self.sink.warn(f"Skipped {title}: {error}")
            finally:
                if len(self.browser.window_handles) > 1:
                    self.browser.close()
                    self.browser.switch_to.window(self.browser.window_handles[0])
                sleep(self.options.delay_seconds)

    def _calculate_bibox_crop_box(self, image_path: Path) -> CropBox:
        with Image.open(image_path) as image:
            cropped = image.convert("RGB").crop((64, 24, 2502, 3506))
            image_array = np.array(cropped)

        height, width, _ = image_array.shape
        top = 0
        while top < height and np.all(image_array[top, :] == (243, 245, 246)):
            top += 1
        left = 0
        while left < width and np.all(image_array[:, left] == (243, 245, 246)):
            left += 1
        right = width - 1
        while right > 0 and np.all(image_array[:, right] == (243, 245, 246)):
            right -= 1
        bottom = height - 1
        while bottom > 0 and np.all(image_array[bottom, :] == (243, 245, 246)):
            bottom -= 1

        return CropBox(left=left + 119, top=top + 79, right=right + 64, bottom=bottom + 24)

    def _exists(self, locator_type: str, locator_value: str) -> bool:
        try:
            self.browser.find_element(locator_type, locator_value)
            return True
        except NoSuchElementException:
            return False

    def _click_if_visible(self, locator_type: str, locator_value: str, message: str) -> None:
        if not self._exists(locator_type, locator_value):
            return
        self.sink.step(message)
        try:
            self.browser.find_element(locator_type, locator_value).click()
        except (ElementNotInteractableException, TimeoutException):
            self.sink.warn(f"Popup was detected but not clickable: {message}")

    @staticmethod
    def _nudge_mouse(action: ActionChains) -> None:
        action.move_by_offset(200, 200).perform()
        action.move_by_offset(-200, -200).perform()
