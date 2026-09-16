"""
Module for submitting Google Form responses using Playwright browser automation.
Ideal for multi-page forms, forms requiring sign-in or visual verification.
"""

import time
import os
import logging
from typing import Dict, List, Any, Optional
from playwright.sync_api import sync_playwright, Page, TimeoutError as PlaywrightTimeoutError
from src.direct_submitter import SubmissionResult

logger = logging.getLogger("BrowserSubmitter")


class BrowserSubmitter:
    def __init__(
        self,
        form_url: str,
        headless: bool = True,
        slow_mo: int = 100,
        timeout: int = 30000,
        screenshot_dir: Optional[str] = None
    ):
        self.form_url = form_url
        self.headless = headless
        self.slow_mo = slow_mo
        self.timeout = timeout
        self.screenshot_dir = screenshot_dir

        if self.screenshot_dir:
            os.makedirs(self.screenshot_dir, exist_ok=True)

    def _fill_text_field(self, page: Page, selector: str, value: str) -> bool:
        try:
            elem = page.locator(selector).first
            if elem.is_visible(timeout=2000):
                elem.fill(value)
                return True
        except Exception:
            pass
        return False

    def _select_radio_or_checkbox(self, page: Page, value: str) -> bool:
        """Find radio or checkbox containing the given label/value and click it."""
        try:
            # 1. By aria-label or data-value
            loc = page.locator(f'[role="radio"][data-value="{value}"], [role="checkbox"][data-value="{value}"]').first
            if loc.is_visible(timeout=1500):
                loc.click()
                return True

            # 2. By text content inside label or option container
            loc_text = page.locator(f'div[role="radio"]:has-text("{value}"), div[role="checkbox"]:has-text("{value}")').first
            if loc_text.is_visible(timeout=1500):
                loc_text.click()
                return True

            # 3. Label tag containing text
            label_loc = page.locator(f'label:has-text("{value}")').first
            if label_loc.is_visible(timeout=1500):
                label_loc.click()
                return True
        except Exception as e:
            logger.debug(f"Could not click choice '{value}': {e}")
        return False

    def _fill_dropdown(self, page: Page, value: str) -> bool:
        try:
            # Click dropdown trigger
            dropdown = page.locator('div[role="listbox"]').first
            if dropdown.is_visible(timeout=2000):
                dropdown.click()
                page.wait_for_timeout(500)
                # Select option
                option = page.locator(f'div[role="option"]:has-text("{value}")').first
                if option.is_visible(timeout=2000):
                    option.click()
                    return True
        except Exception:
            pass
        return False

    def _fill_fields_on_page(self, page: Page, data: Dict[str, Any]) -> None:
        """Fill visible fields on the current page."""
        for key, val in data.items():
            if val is None:
                continue
            val_str = str(val).strip()
            if not val_str:
                continue

            # 1. If key is entry.XXXX
            if key.startswith("entry."):
                # Check for direct radio input in DOM (e.g. Grid or standard radio)
                try:
                    radio_input = page.locator(f'input[type="radio"][name="{key}"][value="{val_str}"]').first
                    if radio_input.is_visible(timeout=500):
                        radio_input.check(force=True)
                        continue
                except Exception:
                    pass

                # Check for standard text / textarea
                input_sel = f'input[name="{key}"], textarea[name="{key}"]'
                if self._fill_text_field(page, input_sel, val_str):
                    continue

            # 2. Check for Grid Row / RadioGroup by question or row title
            # If key or row title contains specific row info
            if " - " in key or "." in key:
                row_label = key.split(" - ")[-1].strip() if " - " in key else key.strip()
                try:
                    row_loc = page.locator(f'div[role="radiogroup"][aria-label*="{row_label}"]').first
                    if row_loc.is_visible(timeout=500):
                        # Find radio button matching value inside this row
                        cell = row_loc.locator(
                            f'div[role="radio"][data-value="{val_str}"], '
                            f'div[role="radio"][aria-label*="{val_str}"]'
                        ).first
                        if cell.is_visible(timeout=1000):
                            cell.click()
                            continue
                except Exception:
                    pass

            # 3. Radio / Checkboxes by value/text
            if isinstance(val, (list, tuple)):
                for item in val:
                    self._select_radio_or_checkbox(page, str(item))
            else:
                if not self._select_radio_or_checkbox(page, val_str):
                    self._fill_dropdown(page, val_str)

    def fill_and_submit_page(self, page: Page, data: Dict[str, Any]) -> bool:
        """Fill all fields matching data values and navigate through sections until submission."""
        max_steps = 10
        for step in range(max_steps):
            page.wait_for_timeout(500)
            # Fill fields on current page
            self._fill_fields_on_page(page, data)

            # Check for Submit button
            submit_btn = page.locator(
                'div[role="button"]:has-text("ส่ง"), '
                'div[role="button"]:has-text("Submit"), '
                'button:has-text("ส่ง"), '
                'button:has-text("Submit")'
            ).first

            # Check for Next / ถัดไป button
            next_btn = page.locator(
                'div[role="button"]:has-text("ถัดไป"), '
                'div[role="button"]:has-text("Next"), '
                'button:has-text("ถัดไป"), '
                'button:has-text("Next")'
            ).first

            # If Submit button is visible on this page, click it
            if submit_btn.is_visible(timeout=1500):
                submit_btn.click()
                page.wait_for_load_state("networkidle", timeout=self.timeout)
                return True

            # If Next button is visible, click to go to the next section
            if next_btn.is_visible(timeout=1500):
                next_btn.click()
                page.wait_for_load_state("networkidle", timeout=self.timeout)
            else:
                # Neither Next nor Submit button found
                break

        return False

    def submit_single(self, data: Dict[str, Any], index: int = 1) -> SubmissionResult:
        start_t = time.time()
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless, slow_mo=self.slow_mo)
            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            try:
                page.goto(self.form_url, timeout=self.timeout, wait_until="networkidle")

                success = self.fill_and_submit_page(page, data)
                elapsed = time.time() - start_t

                # Check for confirmation
                is_confirmed = False
                confirm_indicators = [
                    "เราได้บันทึกคำตอบของคุณไว้แล้ว",
                    "Your response has been recorded",
                    "freebirdFormviewerViewResponseConfirmationMessage",
                    "ส่งคำตอบเพิ่มอีก",
                    "Submit another response"
                ]
                content = page.content()
                for ind in confirm_indicators:
                    if ind in content:
                        is_confirmed = True
                        break

                if self.screenshot_dir:
                    scr_path = os.path.join(self.screenshot_dir, f"submission_{index}_{'success' if is_confirmed else 'fail'}.png")
                    page.screenshot(path=scr_path)

                browser.close()

                if is_confirmed or success:
                    return SubmissionResult(
                        index=index,
                        success=True,
                        status_code=200,
                        response_time=elapsed,
                        payload=data
                    )
                else:
                    return SubmissionResult(
                        index=index,
                        success=False,
                        status_code=400,
                        response_time=elapsed,
                        error_msg="Form submitted but confirmation message was not detected.",
                        payload=data
                    )

            except Exception as e:
                elapsed = time.time() - start_t
                if self.screenshot_dir:
                    scr_path = os.path.join(self.screenshot_dir, f"submission_{index}_error.png")
                    try:
                        page.screenshot(path=scr_path)
                    except Exception:
                        pass
                browser.close()
                return SubmissionResult(
                    index=index,
                    success=False,
                    status_code=0,
                    response_time=elapsed,
                    error_msg=str(e),
                    payload=data
                )
