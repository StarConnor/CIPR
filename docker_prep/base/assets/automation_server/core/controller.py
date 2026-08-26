"""
Core controller for Appium - wraps VS Code automation on Windows.
Requires: pip install Appium-Python-Client selenium pyperclip
"""
import os
import time
import re
import logging
import shutil
import subprocess
import pyperclip
import pyautogui
pyautogui.FAILSAFE = False
from typing import Any, Dict, List, Optional, Tuple, Union

from appium import webdriver
from appium.webdriver.webelement import WebElement
from appium.options.windows import WindowsOptions
from appium.webdriver.common.appiumby import AppiumBy
import selenium.webdriver.common.utils as selenium_utils
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, 
    NoSuchElementException, 
    StaleElementReferenceException
)
from .exceptions import ElementNotFoundError

logger = logging.getLogger(__name__)

def copy_src_to_dest(src_dir: str, dest_dir) -> None:
    # Validate source and prepare destination parent directory
    if not os.path.exists(src_dir):
        raise FileNotFoundError(f"Source directory not found: {src_dir}")
    dest_parent = os.path.dirname(dest_dir)
    if dest_parent:
        os.makedirs(dest_parent, exist_ok=True)

    if os.path.exists(dest_dir):
        attempt = 0
        max_attempts = 3
        while attempt < max_attempts:
            try:
                shutil.rmtree(dest_dir)
                break
            except Exception as e:
                attempt += 1
                if 'SSH' in str(e) and attempt < max_attempts:
                    logger.warning(f"Failed to remove existing tmp data dir due to SSH lock, retrying after delay: {e}")
                    time.sleep(8)
                    continue
                raise
        else:
            raise RuntimeError(f"Failed to remove existing tmp data dir after {max_attempts} attempts: {dest_dir}")
        logger.info(f"Removed existing tmp data dir: {dest_dir}")

    shutil.copytree(src_dir, dest_dir)
    logger.info(f"Copied data dir to tmp: {dest_dir}")
    subprocess.run(
        [
            "icacls",
            dest_dir,
            "/grant",
            "Users:(OI)(CI)F",
            "/T",
            "/C",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

class VSCodeController:
    """Controller for automating VS Code using Appium."""

    def __init__(
        self,
        command_executor: str = "http://127.0.0.1:4723",
        process_name: str = "Code.exe",
        window_title_regex: str = r".* - Visual Studio Code",
        timeout: float = 20.0,
        retry_interval: float = 2.0,
        proxy_url: Optional[str] = None
    ):
        self.command_executor = command_executor
        self.process_name = process_name
        self.window_title_regex = window_title_regex
        self.timeout = timeout
        
        self.driver = None
        self._wait = None
        # Cache the main window handle to avoid constant searching
        self._main_window_handle = None
        self.retry_interval = retry_interval
        self.proxy_url = proxy_url
    
    def is_connectable(self) -> bool:
        return selenium_utils.is_url_connectable(self.command_executor.split(":")[-1].strip("/"))

    def _setup_wait(self):
        """Initialize the WebDriverWait object."""
        if self.driver:
            time.sleep(1)
            self.page_source = self.driver.page_source
            self._wait = WebDriverWait(self.driver, self.timeout)

    def ensure_connected(self) -> bool:
        """Attempt to attach to an existing VS Code session if not already connected."""
        if self.driver:
            try:
                # Access a lightweight property to ensure the session is alive
                _ = self.driver.title
                return True
            except Exception:
                self.driver = None
        try:
            return self.start(attach_only=True)
        except Exception as exc:
            logger.error(f"ensure_connected failed: {exc}")
            return False

    def start(
        self,
        executable_path: Optional[str] = None,
        workspace_path: Optional[str] = None,
        attach_only: bool = False,
        timeout: Optional[int] = None,
        wait_time: Optional[int] = None,
        retrying: bool = False
    ) -> bool:
        """
        Start VS Code or attach to an existing instance via Root session.
        """
        try:
            options = WindowsOptions()
            options.load_capabilities({
                "appium:newCommandTimeout": 0,
            })
            
            # Strategy:
            # 1. If we want to launch, we try to launch the app.
            # 2. However, VS Code is single-instance. If it's already running, 
            #    launching it again just focuses the existing window.
            # 3. Therefore, the most robust method for VS Code is often to use "Root"
            #    automation and find the window.
            
            if attach_only:
                logger.info("Attaching to Root session to find existing VS Code...")
                options.app = "Root"
            else:
                # Determine path
                wrapper_path = "C:\\automation_server_appium\\launcher.bat"
                exe_path = executable_path or self._find_vscode_path()
                if not exe_path:
                    logger.error("VS Code executable not found.")
                    return False
                
                # If workspace is provided, we might need to use subprocess to launch arguments
                # because Appium 'appArguments' can be flaky with paths.
                data_dir = r"C:\automation_server_appium\data"
                ext_dir = r"C:\automation_server_appium\ext"
                tmp_data_dir = r"C:\automation_server_appium\tmp-data"
                tmp_ext_dir = r"C:\automation_server_appium\tmp-ext"
                if not retrying:
                    copy_src_to_dest(data_dir, tmp_data_dir)
                    copy_src_to_dest(ext_dir, tmp_ext_dir)
                if self.proxy_url:
                    logger.info(f"Using proxy url: {self.proxy_url}")
                    ide_args = f"--user-data-dir {tmp_data_dir} --extensions-dir {tmp_ext_dir} {workspace_path if workspace_path else ''} --proxy-server={self.proxy_url}  --disable-quic -n"
                    params = {
                        "appium:app": wrapper_path,
                        "appium:appArguments": f"{self.proxy_url} \"{exe_path}\" {ide_args}",
                    }
                else:
                    params = {
                        "appium:app": exe_path,
                        "appium:appArguments": f"--user-data-dir {tmp_data_dir} --extensions-dir {tmp_ext_dir} {workspace_path if workspace_path else ''} -n",
                    }
                if timeout:
                    params["appium:createSessionTimeout"] = f"{timeout * 1000}"
                if wait_time:
                    params["appium:launchTimeout"] = f"{wait_time}"
                options.load_capabilities(params)
            if workspace_path:
                logger.info(f"Launching VS Code with workspace: {workspace_path}")
                if not workspace_path.startswith("--remote"):
                    logger.info("Local path detected, ensuring directory exists...")
                    os.makedirs(workspace_path, exist_ok=True)
                else:
                    logger.info("Remote path detected, skipping os.makedirs")
            self.driver = webdriver.Remote(command_executor=self.command_executor, options=options)
            self._setup_wait()
            
            # Find and focus the main window
            return True

        except Exception as e:
            logger.error(f"Failed to start/connect to VS Code: {e}")
            if self.driver:
                self.driver.quit()
                self.driver = None
            return False

    def _find_vscode_path(self) -> Optional[str]:
        """Locate VS Code executable."""
        candidates = [
            r"C:\Program Files\Cursor\Cursor.exe",
            os.path.join(os.environ.get('LOCALAPPDATA', ''), r"Programs\Microsoft VS Code\Code.exe"),
            r"C:\Program Files\Microsoft VS Code\Code.exe",
            r"C:\Program Files (x86)\Microsoft VS Code\Code.exe",
            r"D:\Microsoft VS Code\Code.exe",
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        return None

    def _reconnect_to_specific_window(self, window_handle_hex: str):
        """
        Closes the Root session and starts a new session attached ONLY to the VS Code window.
        """
        if self.driver:
            self.driver.quit()
        
        options = WindowsOptions()
        options.set_capability("appTopLevelWindow", window_handle_hex)
        
        logger.info("Attaching Appium driver strictly to VS Code window...")
        self.driver = webdriver.Remote(command_executor=self.command_executor, options=options)
        self._setup_wait()

    def find_element(
        self,
        criteria: Dict[str, Any],
        timeout: Optional[float] = None
    ) -> WebElement:
        """
        Find a UI element using a unified criteria dictionary.
        Supports: 'auto_id', 'name', 'class_name', 'xpath'.
        """
        timeout = timeout if timeout else self.timeout
        wait = WebDriverWait(self.driver, timeout) if self.driver else None

        # Determine Locator Strategy
        locator = None
        if 'auto_id' in criteria:
            locator = (AppiumBy.ACCESSIBILITY_ID, criteria['auto_id'])
        elif 'name' in criteria:
            locator = (AppiumBy.NAME, criteria['name'])
        elif 'title' in criteria: # Backward compatibility
            locator = (AppiumBy.NAME, criteria['title'])
        elif 'class_name' in criteria:
            locator = (AppiumBy.CLASS_NAME, criteria['class_name'])
        elif 'xpath' in criteria:
            locator = (AppiumBy.XPATH, criteria['xpath'])
        
        if not locator:
            raise ValueError(f"No valid locator found in criteria: {criteria}")

        try:
            # We use a custom wait condition that ignores StaleElementReferenceException
            # during the search phase
            def _element_exists(d):
                return d.find_element(*locator)

            wait = WebDriverWait(self.driver, timeout, ignored_exceptions=(StaleElementReferenceException,))
            return wait.until(_element_exists)

        except TimeoutException:
            # Enhance error message with criteria for easier debugging
            msg = f"Element not found within {timeout}s. Criteria: {criteria}"
            raise ElementNotFoundError(msg)
    
    def find_elements(
        self,
        criteria: Dict[str, Any],
        timeout: Optional[float] = None
    ) -> List[WebElement]:
        """
        Find multiple UI elements using a unified criteria dictionary.
        Supports: 'auto_id', 'name', 'class_name', 'xpath'.
        """
        timeout = timeout if timeout else self.timeout
        locator = None
        if 'auto_id' in criteria:
            locator = (AppiumBy.ACCESSIBILITY_ID, criteria['auto_id'])
        elif 'name' in criteria:
            locator = (AppiumBy.NAME, criteria['name'])
        elif 'title' in criteria: # Backward compatibility
            locator = (AppiumBy.NAME, criteria['title'])
        elif 'class_name' in criteria:
            locator = (AppiumBy.CLASS_NAME, criteria['class_name'])
        elif 'xpath' in criteria:
            locator = (AppiumBy.XPATH, criteria['xpath'])
        
        if not locator:
            raise ValueError(f"No valid locator found in criteria: {criteria}")
        
        return self.driver.find_elements(*locator)

    def click(self, element, double: bool = False):
        """Robust click."""
        try:
            if double:
                # Appium Actions for double click
                actions = webdriver.ActionChains(self.driver)
                actions.double_click(element).perform()
            else:
                element.click()
        except Exception as e:
            logger.error(f"Click failed: {e}")
            raise

    def direct_input_text(self, text: str, clear_first: bool = True, submit: bool = True):
        pyautogui.hotkey("ctrl", "a")
        logger.info("direct_input_text: backpace")
        pyautogui.press('backspace')
        logger.info("direct_input_text: write")
        # pyautogui.write(text)
        lines = text.split('\n')
        for i, line in enumerate(lines):
            pyautogui.write(line)  # Type the text of the current line
            
            # If this is not the last line, press Shift+Enter for a new line
            if i < len(lines) - 1:
                pyautogui.hotkey('shift', 'enter')
        logger.info("direct_input_text: write")
        pyautogui.press('enter')
        # pyautogui.press('enter')

    def input_text(self, element, text: str, clear_first: bool = True, submit: bool = True):
        """
        Inputs text. Uses Clipboard paste for reliability with code/long text.
        """
        try:
            element.click() # Ensure focus
            
            if clear_first:
                # Ctrl + A, Delete
                # We use the element.send_keys for modifiers
                time.sleep(1)
                element.send_keys(Keys.CONTROL, 'a')
                element.send_keys(Keys.DELETE)
            
            time.sleep(1)
            # Use Pyperclip to copy to clipboard (Native Python is faster/safer than UI interaction)
            pyperclip.copy(text)
            time.sleep(1)
            
            # Paste (Ctrl + V)
            element.send_keys(Keys.CONTROL, 'v')
            time.sleep(1)
            # element.send_keys(text)
            
            if submit:
                element.send_keys(Keys.ENTER)
                
        except Exception as e:
            logger.error(f"Input text failed: {e}")
            raise
    
    # def hover(self, element: WebElement):
    #     """Execute a JavaScript script."""
    #     rect = element.rect
    #     x = rect['x']
    #     y = rect['y']
    #     self.driver.execute_script("windows:hover", {'startX': x-10, 'startY': y, 'endX': x, 'endY': y}) 

    def get_text(self, element) -> str:
        """Get text from an element."""
        try:
            # Name often contains the visible text in Windows Automation
            return element.text or element.get_attribute("Name") or ""
        except Exception:
            return ""

    def quit(self):
        if self.driver:
            self.driver.quit()
            self.driver = None


# --- Singleton / Global Helpers ---

vscode_controller: Optional[VSCodeController] = None

def get_controller(proxy_url=None) -> VSCodeController:
    global vscode_controller
    if vscode_controller is None:
        vscode_controller = VSCodeController(proxy_url=proxy_url)
    return vscode_controller

def init_controller(**kwargs) -> VSCodeController:
    global vscode_controller
    vscode_controller = VSCodeController(**kwargs)
    return vscode_controller
