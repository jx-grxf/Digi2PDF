from __future__ import annotations

import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path
from threading import Lock
from time import sleep

import numpy as np
from PIL import Image
from selenium.common import (
    ElementClickInterceptedException,
    ElementNotInteractableException,
    NoSuchElementException,
    TimeoutException,
)
from selenium.webdriver import ActionChains, Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from digi2pdf.browser import create_chrome_driver
from digi2pdf.concurrency import parse_manual_worker_count, recommend_workers
from digi2pdf.credentials import clear_credentials, load_credentials, save_credentials
from digi2pdf.imaging import (
    crop_image,
    image_has_page_content,
    images_are_identical,
    save_images_as_pdf,
)
from digi2pdf.models import BookChoice, BookType, CropBox, ProgressSink, RuntimeOptions
from digi2pdf.ocr import OcrUnavailableError, apply_ocr, recommended_ocr_jobs
from digi2pdf.paths import safe_filename
from digi2pdf.tui import (
    LOGIN_CANCEL,
    LOGIN_CLEAR,
    LOGIN_DIFFERENT,
    OCR_FAIL,
    OCR_KEEP_PDF,
    OCR_RETRY,
    ask_books,
    ask_credentials,
    ask_login_recovery,
    ask_ocr_by_book,
    ask_ocr_failure_action,
    ask_retry_failed_books,
    ask_sub_book,
    ask_worker_count,
)

MANAGED_MARKER = ".digi2pdf-export"


class Digi2PDFSession:
    def __init__(self, browser: WebDriver, options: RuntimeOptions, sink: ProgressSink) -> None:
        self.browser = browser
        self.options = options
        self.sink = sink
        self.wait = WebDriverWait(browser, 20)
        self.current_book_index: int | None = None
        self._page_change_attempts = 8
        self._used_book_dirs: set[Path] = set()
        self._directory_lock = Lock()

    def run(self) -> bool:
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

        selected = "all" if self.options.all_books else ask_books(book_names)
        if selected is None:
            self.sink.warn("Cancelled before selecting a book.")
            return False

        if selected == "all":
            choices = [BookChoice(title=title, index=index) for index, title in enumerate(book_names)]
            self.options.ocr_by_book.update(
                {choice.index: self.options.ocr_enabled for choice in choices}
            )
            return self._save_books(choices, book_elements)

        if self.options.ocr_enabled:
            self.options.ocr_by_book.update(
                ask_ocr_by_book(selected, default=self.options.ocr_enabled)
            )
        if not selected:
            self.sink.warn("No books selected.")
            return False
        return self._save_books(selected, book_elements)

    def _login(self) -> None:
        stored = None if self.options.forget_login else load_credentials()
        while True:
            email, password, remember = ask_credentials(stored)
            if not email or not password:
                action = ask_login_recovery("Email and password are required.")
                if action == LOGIN_CLEAR:
                    clear_credentials()
                    stored = None
                elif action in (LOGIN_DIFFERENT, LOGIN_CLEAR):
                    stored = None
                elif action == LOGIN_CANCEL:
                    raise RuntimeError("Login cancelled.")
                continue

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

            if not self._exists(By.XPATH, '//*[@id="ion-input-0"]'):
                if remember:
                    try:
                        save_credentials(email, password)
                        self.sink.step("Login saved securely in the system keychain")
                    except Exception as error:
                        self.sink.warn(f"Could not save login securely: {error}")
                return

            self._dismiss_alert_buttons()
            action = ask_login_recovery("Login failed. Check your email/password or retry after fixing the browser page.")
            if action == LOGIN_CLEAR:
                clear_credentials()
                stored = None
            elif action == LOGIN_DIFFERENT:
                stored = None
            elif action == LOGIN_CANCEL:
                raise RuntimeError("Login cancelled after failed attempt.")

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
        rows = [(element.text.strip(), element) for element in elements if element.text.strip()]
        names = [name for name, _element in rows]
        selected = ask_sub_book(names)
        if selected is None:
            raise RuntimeError("No sub-book selected.")

        rows[selected.index][1].click()
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
        book_dir = self._book_dir_for_title(title)
        book_dir.mkdir(parents=True, exist_ok=True)
        (book_dir / MANAGED_MARKER).write_text("managed by Digi2PDF\n", encoding="utf-8")
        self._clean_managed_book_dir(book_dir)

        action = ActionChains(self.browser)
        self._nudge_mouse(action)
        page_paths: list[Path] = []
        page = 1

        self.sink.start_book(title)
        self.sink.step(f"Capturing {title}")
        while True:
            page_path = book_dir / f"{page:04d}.png"
            if not self._capture_page_when_ready(
                page_path,
                crop_box,
                previous_path=page_paths[-1] if page_paths else None,
            ):
                page_path.unlink(missing_ok=True)
                break

            page_paths.append(page_path)
            self.sink.capture_progress(title, len(page_paths))
            self._next_page(book_type)
            self._nudge_mouse(action)
            sleep(self.options.delay_seconds)
            page += 1

        if not page_paths:
            raise RuntimeError(f"No readable pages captured for {title}.")

        pdf_path = book_dir / f"{book_dir.name}.pdf"
        save_images_as_pdf(page_paths, pdf_path)
        if self._ocr_enabled_for_title(title):
            self._apply_ocr_with_recovery(title, pdf_path, page_count=len(page_paths))
        self.sink.finish_book(title, pdf_path)

        if not self.options.keep_images:
            for page_path in page_paths:
                page_path.unlink(missing_ok=True)

    def _capture_page_when_ready(
        self,
        page_path: Path,
        crop_box: CropBox,
        *,
        previous_path: Path | None,
    ) -> bool:
        for attempt in range(self._page_change_attempts):
            self.browser.save_screenshot(str(page_path))
            crop_image(page_path, crop_box)

            if not image_has_page_content(page_path):
                sleep(min(self.options.delay_seconds, 1.0))
                continue

            if previous_path is None or not images_are_identical(previous_path, page_path):
                return True

            if attempt < self._page_change_attempts - 1:
                sleep(min(self.options.delay_seconds, 1.0))

        return False

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

    def _apply_ocr_with_recovery(self, title: str, pdf_path: Path, *, page_count: int) -> None:
        while True:
            try:
                self.sink.step("Adding OCR text layer")
                apply_ocr(
                    pdf_path,
                    page_count=page_count,
                    profile=self.options.ocr_profile,
                    jobs=recommended_ocr_jobs(),
                    title=title,
                    sink=self.sink,
                )
                return
            except (OcrUnavailableError, RuntimeError) as error:
                action = ask_ocr_failure_action(title, str(error))
                if action == OCR_RETRY:
                    continue
                if action == OCR_KEEP_PDF:
                    self.sink.warn(f"Saved {title} without OCR.")
                    return
                if action == OCR_FAIL:
                    raise RuntimeError(str(error)) from error

    def _save_books(self, choices: list[BookChoice], book_elements: list[object]) -> bool:
        ocr_by_title = {
            choice.title: self.options.ocr_by_book.get(choice.index, self.options.ocr_enabled)
            for choice in choices
        }
        worker_count = self._resolve_worker_count(len(choices))
        self.sink.start_dashboard([choice.title for choice in choices], self.options, ocr_by_title)
        self.sink.step(
            "Processing one book at a time."
            if worker_count == 1
            else f"Processing up to {worker_count} books in parallel."
        )
        success_count = 0
        failed: dict[int, str] = {}
        pending = choices[:]
        try:
            while pending:
                current_round = pending
                pending = []
                if worker_count == 1:
                    round_success = self._save_books_serial(current_round, book_elements, failed)
                else:
                    round_success = self._save_books_parallel(current_round, failed, worker_count)
                success_count += round_success

                if failed:
                    failed_titles = [
                        choice.title or f"book-{choice.index + 1}"
                        for choice in choices
                        if choice.index in failed
                    ]
                    if ask_retry_failed_books(failed_titles):
                        pending = [choice for choice in choices if choice.index in failed]
        finally:
            self.current_book_index = None
            self.sink.finish_dashboard()
        if success_count == 0:
            raise RuntimeError("No books were exported successfully.")
        if failed:
            details = "; ".join(
                f"{choice.title or f'book-{choice.index + 1}'}: {failed[choice.index]}"
                for choice in choices
                if choice.index in failed
            )
            if self.options.allow_partial:
                self.sink.warn(f"Finished with failed books: {details}")
                return True
            raise RuntimeError(f"Some books failed: {details}")
        return True

    def _save_books_serial(
        self,
        choices: list[BookChoice],
        book_elements: list[object],
        failed: dict[int, str],
    ) -> int:
        success_count = 0
        for choice in choices:
            title = choice.title or f"book-{choice.index + 1}"
            self.current_book_index = choice.index
            self._open_book(BookChoice(title=title, index=choice.index), book_elements[choice.index])
            try:
                self._save_current_book(title)
                failed.pop(choice.index, None)
                success_count += 1
            except Exception as error:
                self._capture_failure_context(title)
                failed[choice.index] = str(error)
                self._mark_book_failed(title, str(error))
            finally:
                if len(self.browser.window_handles) > 1:
                    self.browser.close()
                    self.browser.switch_to.window(self.browser.window_handles[0])
                sleep(self.options.delay_seconds)
        return success_count

    def _save_books_parallel(
        self,
        choices: list[BookChoice],
        failed: dict[int, str],
        worker_count: int,
    ) -> int:
        cookies = self.browser.get_cookies()
        success_count = 0
        with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="digi2pdf-book") as executor:
            futures = {
                executor.submit(self._save_book_with_new_browser, choice, cookies): choice
                for choice in choices
            }
            for future in as_completed(futures):
                choice = futures[future]
                try:
                    future.result()
                    failed.pop(choice.index, None)
                    success_count += 1
                except Exception as error:
                    failed[choice.index] = str(error)
                    self._mark_book_failed(choice.title, str(error))
        return success_count

    def _save_book_with_new_browser(
        self,
        choice: BookChoice,
        cookies: list[dict[str, object]],
    ) -> None:
        from digi2pdf.preflight import resolve_chrome_binary

        title = choice.title or f"book-{choice.index + 1}"
        with tempfile.TemporaryDirectory(prefix="digi2pdf-chrome-") as profile_dir:
            browser = create_chrome_driver(
                headless=self.options.headless,
                chrome_binary=resolve_chrome_binary(),
                user_data_dir=Path(profile_dir),
            )
            worker = Digi2PDFSession(
                browser,
                replace(self.options, worker_setting="1"),
                self.sink,
            )
            worker._used_book_dirs = self._used_book_dirs
            worker._directory_lock = self._directory_lock
            try:
                worker._open_overview_with_session(cookies)
                book_names, book_elements = worker._get_books()
                worker_index = worker._find_worker_book_index(choice, book_names)
                worker.current_book_index = choice.index
                worker._open_book(
                    BookChoice(title=title, index=worker_index),
                    book_elements[worker_index],
                )
                worker._save_current_book(title)
            except Exception:
                worker._capture_failure_context(title)
                raise
            finally:
                browser.quit()

    def _open_overview_with_session(self, cookies: list[dict[str, object]]) -> None:
        self.browser.get("https://digi4school.at")
        for cookie in cookies:
            clean_cookie = {
                key: value
                for key, value in cookie.items()
                if key
                in {
                    "name",
                    "value",
                    "path",
                    "domain",
                    "secure",
                    "httpOnly",
                    "expiry",
                    "sameSite",
                }
            }
            try:
                self.browser.add_cookie(clean_cookie)
            except Exception:
                continue

        self.browser.get("https://digi4school.at/overview")
        self.wait.until(
            EC.any_of(
                EC.visibility_of_element_located((By.XPATH, '//*[@id="ion-input-0"]')),
                EC.visibility_of_element_located((By.CLASS_NAME, "entry-heading")),
            )
        )
        if self._exists(By.ID, "ion-input-0") and not self._login_with_stored_credentials():
            raise RuntimeError(
                "Parallel export needs a reusable Digi4School session or saved login. "
                "Run Digi2PDF once, save the login, then retry multiple sessions."
            )

    def _login_with_stored_credentials(self) -> bool:
        stored = None if self.options.forget_login else load_credentials()
        if stored is None:
            return False

        self.sink.step("Submitting saved Digi4School login")
        email_field = self.browser.find_element(By.XPATH, '//*[@id="ion-input-0"]')
        password_field = self.browser.find_element(By.XPATH, '//*[@id="ion-input-1"]')
        email_field.clear()
        email_field.send_keys(stored.email)
        password_field.clear()
        password_field.send_keys(stored.password)

        shadow_host = self.browser.find_element(
            By.XPATH,
            '//*[@id="main-content"]/app-login/ion-content/div[1]/div/form/div[2]/ion-button[1]',
        )
        self.browser.execute_script(
            "arguments[0].shadowRoot.querySelector('button[type=\"submit\"]').click();",
            shadow_host,
        )
        sleep(self.options.delay_seconds + 1)
        if not self._exists(By.XPATH, '//*[@id="ion-input-0"]'):
            return True
        self._dismiss_alert_buttons()
        return False

    @staticmethod
    def _find_worker_book_index(choice: BookChoice, book_names: list[str]) -> int:
        if choice.index < len(book_names) and book_names[choice.index] == choice.title:
            return choice.index
        for index, name in enumerate(book_names):
            if name == choice.title:
                return index
        raise RuntimeError(f"Could not find selected book in worker browser: {choice.title}")

    def _resolve_worker_count(self, selected_count: int) -> int:
        if selected_count <= 1:
            return 1
        recommendation = recommend_workers(selected_count)
        setting = self.options.worker_setting
        if setting is None:
            workers = ask_worker_count(selected_count, recommendation)
        elif setting == "auto":
            workers = recommendation.recommended_workers
        else:
            workers = parse_manual_worker_count(setting, selected_books=selected_count)

        self.sink.step(recommendation.summary)
        return workers

    def _mark_book_failed(self, title: str, detail: str) -> None:
        fail_book = getattr(self.sink, "fail_book", None)
        if callable(fail_book):
            fail_book(title, detail)
        else:
            self.sink.warn(f"Skipped {title}: {detail}")

    def _ocr_enabled_for_title(self, title: str) -> bool:
        if not self.options.ocr_enabled:
            return False
        if self.current_book_index is None:
            return self.options.ocr_enabled
        return self.options.ocr_by_book.get(self.current_book_index, self.options.ocr_enabled)

    def _book_dir_for_title(self, title: str) -> Path:
        lock = getattr(self, "_directory_lock", None)
        if lock is None:
            return self._book_dir_for_title_unlocked(title)
        with lock:
            return self._book_dir_for_title_unlocked(title)

    def _book_dir_for_title_unlocked(self, title: str) -> Path:
        base = safe_filename(title)
        candidate = self.options.output_dir / base
        if candidate not in self._used_book_dirs and self._can_use_book_dir(candidate):
            self._used_book_dirs.add(candidate)
            return candidate

        suffix = 2
        while True:
            candidate = self.options.output_dir / f"{base}-{suffix}"
            if candidate not in self._used_book_dirs and self._can_use_book_dir(candidate):
                self._used_book_dirs.add(candidate)
                return candidate
            suffix += 1

    @staticmethod
    def _can_use_book_dir(candidate: Path) -> bool:
        if not candidate.exists():
            return True
        return (candidate / MANAGED_MARKER).exists()

    def _clean_managed_book_dir(self, book_dir: Path) -> None:
        if self.options.keep_images or not (book_dir / MANAGED_MARKER).exists():
            return
        for page_path in book_dir.glob("*.png"):
            page_path.unlink(missing_ok=True)
        pdf_path = book_dir / f"{book_dir.name}.pdf"
        pdf_path.unlink(missing_ok=True)
        ocr_path = book_dir / f"{book_dir.name}.ocr.pdf"
        ocr_path.unlink(missing_ok=True)

    def _capture_failure_context(self, title: str) -> None:
        diagnostics_dir = self.options.output_dir / "_diagnostics"
        try:
            diagnostics_dir.mkdir(parents=True, exist_ok=True)
            screenshot_path = diagnostics_dir / f"{safe_filename(title)}-failure.png"
            self.browser.save_screenshot(str(screenshot_path))
            self.sink.warn(f"Saved failure screenshot: {screenshot_path}")
        except Exception:
            return

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
        except (ElementClickInterceptedException, ElementNotInteractableException, TimeoutException):
            element = self.browser.find_element(locator_type, locator_value)
            self.browser.execute_script("arguments[0].click();", element)

    def _dismiss_alert_buttons(self) -> None:
        for button in self.browser.find_elements(By.CLASS_NAME, "alert-button"):
            try:
                self.browser.execute_script("arguments[0].click();", button)
                sleep(0.2)
            except Exception:
                continue

    @staticmethod
    def _nudge_mouse(action: ActionChains) -> None:
        action.move_by_offset(200, 200).perform()
        action.move_by_offset(-200, -200).perform()
