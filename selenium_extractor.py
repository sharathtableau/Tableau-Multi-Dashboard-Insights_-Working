import os
import io
import time
import logging
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

try:
    from webdriver_manager.chrome import ChromeDriverManager
    _WDM_AVAILABLE = True
except ImportError:
    _WDM_AVAILABLE = False


def _make_driver(download_dir: str) -> webdriver.Chrome:
    """Create a headless Chrome driver configured for file downloads."""
    opts = Options()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--window-size=1920,1080")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)
    opts.add_experimental_option("prefs", {
        "download.default_directory":  os.path.abspath(download_dir),
        "download.prompt_for_download": False,
        "download.directory_upgrade":   True,
        "safebrowsing.enabled":         True,
    })
    if _WDM_AVAILABLE:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=opts)
    else:
        driver = webdriver.Chrome(options=opts)
    driver.set_window_size(1920, 1080)
    return driver


class SeleniumExtractor:
    """
    Downloads Tableau dashboard crosstab data using a headless browser.

    Two auth strategies (tried in order):
      1. Token injection  — reuses the REST API token as a workgroup_session_id
                            cookie so no re-login is needed.
      2. Credentials login — full email/password login flow as fallback.
    """

    # ── XPath selectors shared across methods ─────────────────────────────────
    _DOWNLOAD_XPATH = (
        "//*[@id='download' "
        "or @data-tb-test-id='viz-viewer-toolbar-button-download' "
        "or @title='Download' "
        "or @aria-label='Download']"
    )
    _CROSSTAB_XPATH = "//*[contains(text(),'Crosstab') or @data-tb-test-id='download-crosstab-option']"
    _SHEET_THUMB_XPATH = "//div[starts-with(@data-tb-test-id,'sheet-thumbnail-')]"

    def __init__(self, username=None, password=None, download_dir="selenium_downloads",
                 token=None, server_url=None, site_name=None):
        self.username    = username
        self.password    = password
        self.token       = token        # REST API token == workgroup_session_id
        self.server_url  = (server_url or "").rstrip("/")
        self.site_name   = site_name or ""
        self.download_dir = os.path.abspath(download_dir)
        os.makedirs(self.download_dir, exist_ok=True)
        self.logger = logging.getLogger(__name__)
        # Pre-warmed driver state (populated by warm_session)
        self._warmed_driver = None
        self._warmed_wait   = None

    # ── Public: download a single matched sheet ────────────────────────────────
    def download_single_sheet(self, view_url: str, target_sheet: str) -> pd.DataFrame:
        """
        Navigate to *view_url* (a Tableau dashboard URL), open
        Download → Crosstab, select *target_sheet*, download the Excel,
        and return a clean pandas DataFrame.

        For Tableau Online the Download toolbar lives in the MAIN PAGE context,
        not inside the viz iframe — so we search there first.

        Raises RuntimeError if the sheet cannot be downloaded.
        """
        driver = _make_driver(self.download_dir)
        wait   = WebDriverWait(driver, 45)

        try:
            # ── Auth ──────────────────────────────────────────────────────────
            auth_ok = False
            if self.token and self.server_url:
                auth_ok = self._inject_token_auth(driver, wait, view_url)
            if not auth_ok and self.username and self.password:
                self._credential_login(driver, wait, view_url)

            # ── Wait for the page to settle (viz may be inside an iframe but
            #    the toolbar is always in the top-level / main-frame context) ─
            self._wait_for_viz_ready(driver)

            # ── Open Download → Crosstab dialog ──────────────────────────────
            # Stay in main page context; Tableau Online's toolbar is there.
            self._open_crosstab_dialog(driver, wait)

            # ── Pick the target sheet ─────────────────────────────────────────
            self._select_sheet(driver, wait, target_sheet)

            # ── Click Download ────────────────────────────────────────────────
            file_path = self._click_download_and_wait(driver, wait)

            # ── Parse the downloaded Excel ────────────────────────────────────
            df = self._parse_excel(file_path, target_sheet)
            return df

        except Exception as exc:
            self._save_debug(driver, "error")
            raise RuntimeError(f"Selenium download failed: {exc}") from exc
        finally:
            driver.quit()

    # ── Pre-warm: login + navigate in background ───────────────────────────────
    def warm_session(self, view_url: str) -> bool:
        """
        Create a headless Chrome driver, authenticate, and navigate to *view_url*
        so it is fully loaded by the time download_with_warmed_session() is called.

        Returns True on success, False if authentication failed.
        Stores the driver in self._warmed_driver for later reuse.
        """
        driver = _make_driver(self.download_dir)
        wait   = WebDriverWait(driver, 45)
        try:
            auth_ok = False
            if self.token and self.server_url:
                auth_ok = self._inject_token_auth(driver, wait, view_url)
            if not auth_ok and self.username and self.password:
                self._credential_login(driver, wait, view_url)
                auth_ok = True

            if not auth_ok:
                self.logger.warning("[Selenium][warm] Auth failed — discarding warm driver.")
                driver.quit()
                return False

            self._wait_for_viz_ready(driver)
            self._warmed_driver = driver
            self._warmed_wait   = wait
            self.logger.info("[Selenium][warm] Session pre-warmed and ready.")
            return True
        except Exception as exc:
            self.logger.warning(f"[Selenium][warm] warm_session failed: {exc}")
            try:
                driver.quit()
            except Exception:
                pass
            return False

    def download_with_warmed_session(self, target_sheet: str) -> pd.DataFrame:
        """
        Reuse the pre-warmed driver to open the Crosstab dialog,
        select *target_sheet*, download, and return a DataFrame.

        Falls back to a fresh full flow if the warmed driver is not available
        or has become stale.
        """
        driver = self._warmed_driver
        wait   = self._warmed_wait
        # Clear the cached driver immediately so it won't be accidentally reused
        self._warmed_driver = None
        self._warmed_wait   = None

        if driver is None:
            raise RuntimeError("No pre-warmed session available.")

        try:
            # Ensure we are back in the main page context (no stale iframe)
            driver.switch_to.default_content()

            # ── Open Download → Crosstab dialog ──────────────────────────────
            self._open_crosstab_dialog(driver, wait)

            # ── Pick the target sheet ─────────────────────────────────────────
            self._select_sheet(driver, wait, target_sheet)

            # ── Click Download ────────────────────────────────────────────────
            file_path = self._click_download_and_wait(driver, wait)

            # ── Parse Excel ───────────────────────────────────────────────────
            df = self._parse_excel(file_path, target_sheet)
            return df

        except Exception as exc:
            self._save_debug(driver, "warm_error")
            raise RuntimeError(f"Warmed-session download failed: {exc}") from exc
        finally:
            try:
                driver.quit()
            except Exception:
                pass

    def navigate_and_warm(self, view_url: str) -> bool:
        """
        Re-use the already-authenticated driver (self._warmed_driver) to navigate
        to a *different* view_url.  Avoids a full re-login — much faster (~5 s
        vs ~30 s) when the user switches to a second workbook/dashboard.

        Returns True on success, False if the driver is gone or navigation fails.
        """
        if self._warmed_driver is None:
            self.logger.warning("[Selenium][warm] navigate_and_warm: no alive driver; need full warm_session.")
            return False
        try:
            url = self._ensure_iid(view_url)
            self._warmed_driver.get(url)
            self._wait_for_viz_ready(self._warmed_driver)
            self.logger.info(f"[Selenium][warm] Re-navigated to: {view_url}")
            return True
        except Exception as exc:
            self.logger.warning(f"[Selenium][warm] navigate_and_warm failed: {exc}")
            try:
                self._warmed_driver.quit()
            except Exception:
                pass
            self._warmed_driver = None
            self._warmed_wait   = None
            return False

    def download_keep_alive(self, target_sheet: str) -> pd.DataFrame:
        """
        Download the crosstab for *target_sheet* using the pre-warmed driver and
        keep the browser session alive after the download completes.

        Unlike download_with_warmed_session(), this method does NOT quit the
        driver — self._warmed_driver stays populated so the same authenticated
        session can be reused for a second workbook without re-logging in.

        On error the driver IS quit and cleared (stale sessions are useless).
        """
        driver = self._warmed_driver
        wait   = self._warmed_wait

        if driver is None:
            raise RuntimeError("No pre-warmed session available.")

        try:
            # Back to main page context (no stale iframe from previous operation)
            driver.switch_to.default_content()

            self._open_crosstab_dialog(driver, wait)
            self._select_sheet(driver, wait, target_sheet)
            file_path = self._click_download_and_wait(driver, wait)
            df = self._parse_excel(file_path, target_sheet)

            # Driver intentionally NOT quit — stays in self._warmed_driver for reuse
            self.logger.info(f"[Selenium][keep-alive] Downloaded '{target_sheet}'; browser stays open.")
            return df

        except Exception as exc:
            self._save_debug(driver, "keep_alive_error")
            # On failure, kill the driver so stale sessions don't accumulate
            try:
                driver.quit()
            except Exception:
                pass
            self._warmed_driver = None
            self._warmed_wait   = None
            raise RuntimeError(f"Keep-alive download failed: {exc}") from exc

    def close_warmed_session(self):
        """Quit and discard the pre-warmed driver if it exists."""
        if self._warmed_driver is not None:
            try:
                self._warmed_driver.quit()
            except Exception:
                pass
            self._warmed_driver = None
            self._warmed_wait   = None
            self.logger.info("[Selenium][warm] Warmed session closed.")

    # ── Auth helpers ───────────────────────────────────────────────────────────
    def _inject_token_auth(self, driver, wait, view_url: str) -> bool:
        """
        Inject workgroup_session_id cookie then navigate to the view.
        Returns True if the viz loaded successfully (no login redirect).
        """
        try:
            domain = self.server_url.replace("https://", "").replace("http://", "").split("/")[0]
            # Must visit the domain first before setting cookies
            driver.get(self.server_url)
            # Wait for the page to load (up to 8 s) rather than sleeping blindly
            try:
                WebDriverWait(driver, 8).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
            except Exception:
                pass

            driver.add_cookie({"name": "workgroup_session_id", "value": self.token,
                                "domain": domain, "path": "/"})
            driver.add_cookie({"name": "XSRF-TOKEN",           "value": self.token,
                                "domain": domain, "path": "/"})

            url = self._ensure_iid(view_url)
            driver.get(url)

            # Wait until either the viz loads OR we land on the login page (max 12 s)
            try:
                WebDriverWait(driver, 12).until(
                    lambda d: "login" in d.current_url.lower()
                              or d.find_elements(By.ID, "email")
                              or d.find_elements(By.XPATH, self._DOWNLOAD_XPATH)
                              or (d.execute_script("return document.readyState") == "complete"
                                  and "views/" in d.current_url.lower())
                )
            except Exception:
                pass

            # If we land on a login page, token auth failed
            if "login" in driver.current_url.lower() or \
               self._element_present(driver, By.ID, "email", timeout=2):
                self.logger.warning("[Selenium] Token injection did not bypass login; falling back to credentials.")
                return False

            self.logger.info("[Selenium] Token injection succeeded.")
            return True
        except Exception as e:
            self.logger.warning(f"[Selenium] Token injection error: {e}")
            return False

    def _credential_login(self, driver, wait, view_url: str):
        """Full email + password login flow for Tableau Online."""
        url = self._ensure_iid(view_url)
        self.logger.info(f"[Selenium] Navigating for credential login: {url}")
        driver.get(url)

        self.logger.info("[Selenium] Entering email…")
        email_el = wait.until(EC.presence_of_element_located((By.ID, "email")))
        email_el.clear()
        email_el.send_keys(self.username)
        # Wait for the submit/next button or just press Enter
        time.sleep(0.3)
        email_el.send_keys(Keys.RETURN)

        self.logger.info("[Selenium] Entering password…")
        pwd_el = wait.until(EC.presence_of_element_located((By.ID, "password")))
        pwd_el.clear()
        pwd_el.send_keys(self.password)
        time.sleep(0.3)
        pwd_el.send_keys(Keys.RETURN)

        self.logger.info("[Selenium] Login submitted, waiting for dashboard…")
        # Instead of sleeping 20 s, poll for the Download button or URL change
        try:
            WebDriverWait(driver, 40).until(
                lambda d: "login" not in d.current_url.lower()
                          and (d.find_elements(By.XPATH, self._DOWNLOAD_XPATH)
                               or "views/" in d.current_url.lower())
            )
            self.logger.info("[Selenium] Dashboard loaded after credential login.")
        except Exception:
            self.logger.warning("[Selenium] Timed out waiting for dashboard after login; continuing anyway.")
        self._save_debug(driver, "after_login")

    # ── Viz ready (no iframe switch) ──────────────────────────────────────────
    def _wait_for_viz_ready(self, driver, timeout: int = 30):
        """
        Wait for the Tableau viz page to finish loading without switching
        into any iframe.  The Download toolbar on Tableau Online lives in the
        MAIN PAGE context; switching into the viz iframe makes it invisible.
        Uses WebDriverWait (event-driven) for most of the wait to avoid fixed sleeps.
        """
        self._save_debug(driver, "before_viz_ready")
        try:
            WebDriverWait(driver, timeout).until(
                lambda d: bool(d.find_elements(By.XPATH, self._DOWNLOAD_XPATH))
                          or (
                              "login" not in d.current_url.lower()
                              and bool(d.find_element(By.TAG_NAME, "body").text.strip())
                          )
            )
            if driver.find_elements(By.XPATH, self._DOWNLOAD_XPATH):
                self.logger.info("[Selenium] Download button detected in main page — viz is ready.")
            else:
                self.logger.info("[Selenium] Page body loaded; proceeding.")
        except Exception:
            self.logger.warning("[Selenium] _wait_for_viz_ready timed out; continuing anyway.")
        self._save_debug(driver, "after_viz_ready")

    # ── Legacy helper kept for download_crosstab (backward compat) ────────────
    def _switch_to_viz_frame(self, driver, wait):
        """
        Kept for the multi-sheet download_crosstab path.
        For Tableau Online single-sheet use _wait_for_viz_ready instead.
        """
        self._save_debug(driver, "before_iframe")
        try:
            iframe = wait.until(EC.presence_of_element_located((
                By.XPATH,
                "//iframe[contains(@title,'Data Visualization') or contains(@src,'views/') or contains(@src,'viz')]"
            )))
            driver.switch_to.frame(iframe)
            self.logger.info("[Selenium] Switched to viz iframe.")
            time.sleep(3)
        except Exception:
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            if iframes:
                driver.switch_to.frame(iframes[0])
                self.logger.info("[Selenium] Switched to first iframe (fallback).")
                time.sleep(3)
            else:
                self.logger.info("[Selenium] No iframe found; assuming top-level context.")
        self._save_debug(driver, "after_iframe")

    # ── Crosstab dialog ────────────────────────────────────────────────────────
    def _open_crosstab_dialog(self, driver, wait):
        """
        Click the Download toolbar button then the Crosstab option.

        Tableau Online: toolbar is in the MAIN PAGE context.
        If the button is not found at the top level (e.g. embedded iframe use),
        fall back to searching inside iframes.
        """
        self.logger.info("[Selenium] Looking for Download toolbar button in main page…")
        dl_btn = None

        # Try main page first (Tableau Online direct view)
        try:
            driver.switch_to.default_content()
            dl_btn = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.XPATH, self._DOWNLOAD_XPATH))
            )
            self.logger.info("[Selenium] Found Download button in main page context.")
        except Exception:
            self.logger.info("[Selenium] Download button not in main page; trying iframes…")

        # Fall back: try each iframe
        if dl_btn is None:
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            for idx, fr in enumerate(iframes):
                try:
                    driver.switch_to.default_content()
                    driver.switch_to.frame(fr)
                    els = driver.find_elements(By.XPATH, self._DOWNLOAD_XPATH)
                    if els:
                        dl_btn = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, self._DOWNLOAD_XPATH))
                        )
                        self.logger.info(f"[Selenium] Found Download button in iframe[{idx}].")
                        break
                except Exception:
                    pass

        if dl_btn is None:
            raise RuntimeError("Download toolbar button not found in main page or any iframe.")

        dl_btn.click()
        # Wait for the dropdown menu to appear instead of sleeping blindly
        try:
            WebDriverWait(driver, 6).until(
                EC.presence_of_element_located((By.XPATH, self._CROSSTAB_XPATH))
            )
        except Exception:
            time.sleep(1)  # small fallback if XPath takes a moment

        self.logger.info("[Selenium] Clicking Crosstab option…")
        ct_opt = wait.until(EC.element_to_be_clickable((By.XPATH, self._CROSSTAB_XPATH)))
        ct_opt.click()
        # Wait for the Crosstab dialog to render (sheet thumbnails to appear)
        try:
            WebDriverWait(driver, 8).until(
                lambda d: bool(d.find_elements(By.XPATH, self._SHEET_THUMB_XPATH))
                          or bool(d.find_elements(By.XPATH,
                              "//div[contains(@class,'sheet') or contains(@class,'thumbnail')]"
                              "[not(@style='display:none')]"))
            )
        except Exception:
            time.sleep(1.5)  # small fallback

    # ── Sheet selection ────────────────────────────────────────────────────────
    def _select_sheet(self, driver, wait, target_sheet: str):
        """
        Find and click the thumbnail for *target_sheet* in the Crosstab dialog.

        Tries multiple selectors in order:
          1. data-tb-test-id="sheet-thumbnail-*"  (original Tableau attribute)
          2. Any clickable element whose visible text matches the sheet name
             (Tableau Online's dialog renders sheet names as visible text labels)
          3. First thumbnail fallback (with a warning)

        After clicking the thumbnail, selects Excel format if available.
        Raises RuntimeError if no thumbnails at all are found within the timeout.
        """
        def _norm(s): return ''.join(str(s).strip().lower().split())
        target_norm = _norm(target_sheet)

        # ── Attempt 1: original data-tb-test-id thumbnails ───────────────────
        thumbnails = driver.find_elements(By.XPATH, self._SHEET_THUMB_XPATH)

        # ── Attempt 2: visible-text based — broader search for sheet cards ───
        # Tableau Online (2022+) uses a dialog where each sheet is a card div
        # whose text label matches the sheet name exactly.
        if not thumbnails:
            self.logger.info("[Selenium] data-tb-test-id thumbnails not found; "
                             "trying text-based sheet search…")
            thumbnails = driver.find_elements(
                By.XPATH,
                "//div[contains(@class,'sheet') or contains(@class,'thumbnail') "
                "or contains(@class,'card') or contains(@class,'item')]"
                "[not(@style='display:none')]"
            )

        # If still nothing, wait (event-driven) up to 5 s and retry
        if not thumbnails:
            try:
                WebDriverWait(driver, 5).until(
                    lambda d: bool(d.find_elements(By.XPATH, self._SHEET_THUMB_XPATH))
                              or bool(d.find_elements(
                                  By.XPATH, "//*[contains(@class,'sheet') or contains(@class,'thumbnail')]"))
                )
            except Exception:
                pass
            thumbnails = driver.find_elements(By.XPATH, self._SHEET_THUMB_XPATH)
            if not thumbnails:
                thumbnails = driver.find_elements(
                    By.XPATH, "//*[contains(@class,'sheet') or contains(@class,'thumbnail')]"
                )

        if not thumbnails:
            raise RuntimeError("No sheet thumbnails found in the Crosstab dialog.")

        self.logger.info(f"[Selenium] {len(thumbnails)} sheet thumbnail candidates found.")

        matched_thumb = None

        # ── Pass 1: match by title attribute or data-tb-test-id ──────────────
        for thumb in thumbnails:
            title = _norm(thumb.get_attribute("title") or "")
            label = _norm(thumb.get_attribute("data-tb-test-id") or "")
            if title == target_norm or target_norm in title:
                matched_thumb = thumb
                self.logger.info(f"[Selenium] Matched by title='{thumb.get_attribute('title')}'")
                break
            if target_norm in label:
                matched_thumb = thumb
                self.logger.info(f"[Selenium] Matched by data-tb-test-id='{thumb.get_attribute('data-tb-test-id')}'")
                break

        # ── Pass 2: match by visible inner text ───────────────────────────────
        if matched_thumb is None:
            for thumb in thumbnails:
                try:
                    inner_text = _norm(thumb.text or "")
                    if target_norm == inner_text or target_norm in inner_text:
                        matched_thumb = thumb
                        self.logger.info(f"[Selenium] Matched by visible text: '{thumb.text.strip()}'")
                        break
                except Exception:
                    pass

        # ── Pass 3: search for any element containing the exact sheet name ───
        if matched_thumb is None:
            try:
                # Direct text-contains XPath (case-sensitive but reliable)
                matched_thumb = driver.find_element(
                    By.XPATH,
                    f"//*[normalize-space(text())='{target_sheet}' "
                    f"or normalize-space(.)='{target_sheet}']"
                )
                self.logger.info(f"[Selenium] Matched by XPath text='{target_sheet}'")
            except Exception:
                pass

        # ── Fallback: first thumbnail (wrong sheet but at least downloads) ────
        if matched_thumb is None:
            matched_thumb = thumbnails[0]
            fallback_title = (matched_thumb.get_attribute("title")
                              or matched_thumb.text or "unknown")
            self.logger.warning(
                f"[Selenium] Could NOT match sheet '{target_sheet}'; "
                f"falling back to first card: '{fallback_title.strip()}'"
            )

        # ── Check if already selected (default sheet may already be checked) ───
        # Clicking an already-selected item can DESELECT it in some Tableau builds
        # (toggle behaviour). Skip the click if the sheet appears already active.
        already_selected = False
        try:
            # Tableau renders a checkmark overlay on the selected thumbnail
            chk_els = matched_thumb.find_elements(
                By.XPATH,
                ".//*[contains(@class,'check') or contains(@class,'viz-selected') "
                "or contains(@class,'selected-check') or contains(@class,'selected-icon')]"
            )
            if chk_els:
                already_selected = True
            # Also check aria attributes
            if (matched_thumb.get_attribute('aria-selected') == 'true'
                    or matched_thumb.get_attribute('aria-checked') == 'true'):
                already_selected = True
            # Check for a CSS class that marks selection on the card itself
            classes = matched_thumb.get_attribute('class') or ''
            if any(c in classes for c in ('selected', 'active', 'checked', 'highlighted')):
                already_selected = True
        except Exception:
            pass

        # ── Click the matched thumbnail (only if not already selected) ────────
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", matched_thumb)
        if already_selected:
            self.logger.info(f"[Selenium] Sheet '{target_sheet}' is already selected in dialog; skipping click.")
        else:
            try:
                # Try clicking the text label inside the card first
                inner = matched_thumb.find_element(
                    By.XPATH,
                    ".//span[contains(@class,'thumbnail-title') or contains(@class,'name') "
                    "or contains(@class,'label') or contains(@class,'title')]"
                )
                ActionChains(driver).move_to_element(inner).click().perform()
            except Exception:
                ActionChains(driver).move_to_element(matched_thumb).click().perform()

        # Wait for the Download button to become enabled (sheet is now selected)
        try:
            _DL_BTN_XP = (
                "//button["
                "contains(translate(text(),'DOWNLOAD','download'),'download') "
                "or @data-tb-test-id='crosstab-options-dialog-download-button']"
            )
            WebDriverWait(driver, 4).until(
                lambda d: bool(d.find_elements(By.XPATH, _DL_BTN_XP))
            )
        except Exception:
            time.sleep(0.5)

        # ── Prefer Excel format ───────────────────────────────────────────────
        _EXCEL_XPATH = (
            "//label[@data-tb-test-id='crosstab-options-dialog-radio-excel-Label' "
            "or contains(translate(text(),'EXCEL','excel'),'excel')]"
        )
        try:
            excel_lbl = driver.find_element(By.XPATH, _EXCEL_XPATH)
            excel_lbl.click()
        except Exception:
            pass  # CSV is fine if Excel radio not found

    # ── Download + wait ────────────────────────────────────────────────────────
    def _click_download_and_wait(self, driver, wait, timeout: int = 60) -> str:
        """Click the final Download button and return the path of the downloaded file."""
        # The dialog's Download button — try several label variants
        _DL_BTN_XPATH = (
            "//button["
            "contains(translate(text(),'DOWNLOAD','download'),'download') "
            "or @data-tb-test-id='crosstab-options-dialog-download-button' "
            "or contains(@class,'download') and not(contains(@id,'toolbar'))"
            "]"
        )
        dl_btn = wait.until(EC.presence_of_element_located((By.XPATH, _DL_BTN_XPATH)))
        if dl_btn.get_attribute("disabled"):
            raise RuntimeError("Download button is disabled for this sheet.")

        existing = set(os.listdir(self.download_dir))
        dl_btn.click()
        self.logger.info("[Selenium] Download button clicked, waiting for file…")

        deadline = time.time() + timeout
        while time.time() < deadline:
            current  = set(os.listdir(self.download_dir))
            new_done = [
                f for f in (current - existing)
                if not f.endswith(".crdownload") and not f.startswith(".~")
                   and not f.startswith("debug_") and not f.startswith("error_")
            ]
            if new_done:
                path = os.path.join(self.download_dir, new_done[0])
                self.logger.info(f"[Selenium] File downloaded: {path}")
                return path
            time.sleep(0.5)   # poll every 0.5 s instead of 2 s for faster detection

        raise RuntimeError(f"Timed out waiting for download after {timeout}s.")

    # ── Excel → DataFrame ─────────────────────────────────────────────────────
    def _parse_excel(self, file_path: str, sheet_hint: str = "") -> pd.DataFrame:
        """Read a Tableau crosstab Excel file into a clean DataFrame."""
        try:
            df_raw = pd.read_excel(file_path, header=None)
            self.logger.info(f"[Selenium] Raw Excel: {df_raw.shape}, first row: {list(df_raw.iloc[0])}")

            first_row = df_raw.iloc[0]
            string_count = sum(1 for v in first_row if isinstance(v, str) and str(v).strip())

            if string_count > 0:
                df = pd.read_excel(file_path, header=0)
                new_cols, counter = [], 1
                for col in df.columns:
                    cs = str(col)
                    if cs.startswith("Unnamed:"):
                        samples = df[col].dropna().head(5)
                        new_cols.append(
                            f"Value_{counter}" if len(samples) > 0 and
                            all(isinstance(v, (int, float)) for v in samples) else f"Column_{counter}"
                        )
                        counter += 1
                    else:
                        new_cols.append(cs)
                df.columns = new_cols
            else:
                df = df_raw.copy()
                df.columns = [f"Column_{i+1}" for i in range(len(df.columns))]

            df = df.fillna("")
            self.logger.info(f"[Selenium] Parsed: {len(df)} rows, cols: {list(df.columns)}")
            return df
        finally:
            try:
                os.remove(file_path)
            except Exception:
                pass

    # ── Backward-compat: download all sheets ──────────────────────────────────
    def download_crosstab(self, view_url: str):
        """
        Original multi-sheet download method kept for backward compatibility.
        Returns list of (sheet_name, file_path) tuples.
        """
        driver = _make_driver(self.download_dir)
        wait   = WebDriverWait(driver, 45)
        downloaded_files = []

        try:
            auth_ok = False
            if self.token and self.server_url:
                auth_ok = self._inject_token_auth(driver, wait, view_url)
            if not auth_ok and self.username and self.password:
                self._credential_login(driver, wait, view_url)

            self._switch_to_viz_frame(driver, wait)

            # First pass: count sheets
            self._open_crosstab_dialog(driver, wait)
            thumbnails = driver.find_elements(By.XPATH, self._SHEET_THUMB_XPATH)
            num_sheets = len(thumbnails)
            self.logger.info(f"[Selenium] {num_sheets} sheets found for bulk download.")
            ActionChains(driver).send_keys(Keys.ESCAPE).perform()
            time.sleep(2)

            # Download each sheet
            for i in range(num_sheets):
                self._open_crosstab_dialog(driver, wait)
                thumbs = wait.until(EC.presence_of_all_elements_located((By.XPATH, self._SHEET_THUMB_XPATH)))
                if i >= len(thumbs):
                    continue
                thumb     = thumbs[i]
                sname     = thumb.get_attribute("title") or f"Sheet_{i+1}"
                if i > 0:
                    driver.execute_script("arguments[0].scrollIntoView({block:'center'});", thumb)
                    time.sleep(0.5)
                    try:
                        inner = thumb.find_element(By.XPATH, ".//span[contains(@class,'thumbnail-title')]")
                        ActionChains(driver).move_to_element(inner).click().perform()
                    except Exception:
                        ActionChains(driver).move_to_element(thumb).click().perform()
                    time.sleep(1)
                try:
                    excel_lbl = driver.find_element(By.XPATH, "//label[@data-tb-test-id='crosstab-options-dialog-radio-excel-Label']")
                    excel_lbl.click()
                    time.sleep(1)
                except Exception:
                    pass
                try:
                    path = self._click_download_and_wait(driver, wait)
                    downloaded_files.append((sname, path))
                except Exception as e:
                    self.logger.warning(f"[Selenium] Failed sheet '{sname}': {e}")
                    ActionChains(driver).send_keys(Keys.ESCAPE).perform()
                    time.sleep(2)
                time.sleep(2)

            return downloaded_files

        except Exception as exc:
            self._save_debug(driver, "error")
            raise
        finally:
            driver.quit()

    def process_downloads(self, downloaded_files):
        """Parse downloaded Excel files into a combined CSV string."""
        combined_csv = ""
        for sheet_name, file_path in downloaded_files:
            try:
                df = self._parse_excel(file_path, sheet_name)
                combined_csv += f"=== Sheet: {sheet_name} ===\n{df.to_csv(index=False)}\n"
            except Exception as e:
                self.logger.error(f"[Selenium] Parse failed for '{sheet_name}': {e}")
                combined_csv += f"=== Sheet: {sheet_name} (Error: {e}) ===\n\n"
        return combined_csv

    # ── Utilities ──────────────────────────────────────────────────────────────
    @staticmethod
    def _ensure_iid(url: str) -> str:
        if ":iid=" not in url:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}:iid=1"
        return url

    def _element_present(self, driver, by, value, timeout=5) -> bool:
        try:
            WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, value)))
            return True
        except Exception:
            return False

    def _save_debug(self, driver, label: str):
        try:
            path = os.path.join(self.download_dir, f"debug_{label}.png")
            driver.save_screenshot(path)
            self.logger.debug(f"[Selenium] Debug screenshot: {path}")
        except Exception:
            pass
