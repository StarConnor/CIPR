"""Action and workflow executor for Appium."""
import glob
import hashlib
import os
import re
import json
import time
import shlex
from remote_pdb import set_trace
from datetime import datetime
import logging
import subprocess
from typing import Any, Dict, List, Optional, Union
import threading
from openai import OpenAI

from ..config.schema import ActionStep, ExtensionConfig, Selector, SelectorCriteria
from .exceptions import ElementNotFoundError, ActionExecutionError, WorkflowConfigError

# Lazy imports to avoid loading heavy dependencies when not needed
def _get_vscode_controller():
    """Lazy import VSCode controller and dependencies."""
    from .controller import VSCodeController, get_controller
    return VSCodeController, get_controller

def _get_cli_controller():
    """Lazy import CLI controller."""
    from .cli_controller import CLIController, get_cli_controller
    return CLIController, get_cli_controller

def _get_selector_resolver():
    """Lazy import selector resolver (only needed for IDE)."""
    from .selector import SelectorResolver
    return SelectorResolver

def _get_ide_dependencies():
    """Lazy import IDE-specific dependencies."""
    import pyautogui
    import pyperclip
    from appium.webdriver.webelement import WebElement
    from selenium.webdriver import ActionChains
    from selenium.webdriver.common.keys import Keys
    from selenium.common.exceptions import (
        StaleElementReferenceException,
        NoSuchElementException,
        TimeoutException
    )
    from .utils import parse_key_str, is_task_end, parse_key_str_autogui
    
    return {
        'pyautogui': pyautogui,
        'pyperclip': pyperclip,
        'WebElement': WebElement,
        'ActionChains': ActionChains,
        'Keys': Keys,
        'StaleElementReferenceException': StaleElementReferenceException,
        'NoSuchElementException': NoSuchElementException,
        'TimeoutException': TimeoutException,
        'parse_key_str': parse_key_str,
        'is_task_end': is_task_end,
        'parse_key_str_autogui': parse_key_str_autogui,
    }

logger = logging.getLogger(__name__)


class ExecutionContext:
    """Context for action/workflow execution, holds variables and outputs."""
    
    def __init__(self, params: Optional[Dict[str, Any]] = None):
        self.params = params or {}
        self.outputs: Dict[str, Any] = {}
        # Stores the last resolved WebElement
        self.last_element = None
    
    def resolve_template(self, text) -> str | List[str]:
        """Resolve {{param}} templates in text."""
        if not text or not isinstance(text, str) and not isinstance(text, list):
            return text
        
        def replace_param(match):
            param_name = match.group(1).strip()
            if param_name in self.params:
                return str(self.params[param_name])
            elif param_name in self.outputs:
                return str(self.outputs[param_name])
            else:
                logger.warning(f"Unresolved parameter: {param_name}")
                return match.group(0)
        
        if isinstance(text, list):
            for t in text:
                if not isinstance(t, str):
                    continue
                text = [re.sub(r'\{\{(\w+)\}\}', replace_param, t) for t in text]
            return text
        else:
            return re.sub(r'\{\{(\w+)\}\}', replace_param, text)
        
    def safe_eval(self, expr_str, default=None):
        """
        Safely evaluate an expression with params and outputs as context.
        Returns default value on error.
        """
        if not expr_str:
            return True
        
        try:
            # Create a safe namespace with common built-ins
            safe_builtins = {
                'True': True,
                'False': False,
                'None': None,
                'len': len,
                'str': str,
                'int': int,
                'float': float,
                'bool': bool,
            }
            
            # Merge params and outputs (outputs takes precedence)
            namespace = {**safe_builtins, **self.params, **self.outputs}
            
            logger.debug(f"Evaluating expression: {expr_str} with namespace: {namespace}")
            result = eval(expr_str, {"__builtins__": {}}, namespace)
            logger.debug(f"Evaluated '{expr_str}' => {result}")
            return result
        except Exception as e:
            logger.debug(f"Error evaluating '{expr_str}': {e}")
            return default if default is not None else False
    
    def evaluate_condition(self, condition_str):
        """
        Evaluates strings like 'needs_info == True' or 'not found'.
        For simplicity, we use a basic eval with the context's outputs.
        """
        return self.safe_eval(condition_str, default=False)

class ActionExecutor:
    """Executes actions and workflows from extension configs using Appium."""
    
    def __init__(
        self,
        extension_config: ExtensionConfig,
        controller = None,
        cli_controller = None,
        logger_instance = None,
    ):
        self.config = extension_config
        self.driver_type = getattr(extension_config, "driver", "ide")
        self.client = OpenAI(
            api_key=extension_config.llm_api_key,
            base_url=extension_config.llm_base_url,
        )
        self.model = extension_config.llm_model
        
        # Use provided logger or fall back to module logger
        global logger
        if logger_instance:
            logger = logger_instance
        
        # Only set up the controller needed for this driver type
        if self.driver_type == "cli":
            # Lazy import CLI dependencies
            _, get_cli_controller = _get_cli_controller()
            self.controller = None
            self.cli = cli_controller or get_cli_controller()
            self.resolver = None  # CLI mode doesn't need selector resolver
            # No IDE dependencies needed
            self.ide_deps = None
        else:  # ide mode
            # Lazy import IDE dependencies
            _, get_controller = _get_vscode_controller()
            SelectorResolver = _get_selector_resolver()
            self.controller = controller or get_controller()
            self.cli = None
            self.resolver = SelectorResolver(self.controller, extension_config)
            # Load IDE-specific packages
            self.ide_deps = _get_ide_dependencies()
        
        self.time_begin_store = None
        self.time_begin = None
        self.time_end = None
        self.chat_history = []

    def _ensure_cli(self):
        """Return the CLI controller or raise if unavailable."""
        if not self.cli:
            raise WorkflowConfigError("CLI controller is not configured. Set driver: cli or provide cli controller.")
        return self.cli

    @staticmethod
    def _normalize_cli_screen_text(text: str) -> str:
        """
        Normalize terminal screen text for stability checks.

        The goal is not to semantically parse the TUI; it is to avoid treating
        insignificant rendering differences (ANSI escape fragments, trailing
        whitespace, cursor-only padding) as real progress while preserving the
        visible content that matters for completion detection.
        """
        if not text:
            return ""

        # Strip ANSI/VT escape sequences if the controller returns any.
        text = re.sub(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])", "", text)

        # Normalize line endings and remove right-side padding from fixed-width
        # terminal rows. Keep blank lines, because screen layout changes can be
        # meaningful in TUIs.
        lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
        return "\n".join(lines).strip()
    
    def _resolve_target(self, target, context: ExecutionContext, force_reload: bool = False, find_all: bool = False):
        """
        Resolve an action target to a Selenium WebElement.
        """
        if target is None:
            if context.last_element and not force_reload:
                return context.last_element
            raise WorkflowConfigError("No target specified and no previous element available.")
        
        # If target is string, Selector, or dict, pass to resolver
        # We assume SelectorResolver has been adapted to return WebElements
        if isinstance(target, (str, Selector)):
            return self.resolver.resolve_selector(target, use_cache=False) if not find_all else self.resolver.resolve_all(target)
        elif isinstance(target, dict):
            # Inline selector definition
            criteria = SelectorCriteria(**target.get('criteria', {}))
            selector = Selector(
                criteria=criteria,
                parent=target.get('parent'),
            )
            return self.resolver.resolve_selector(selector, use_cache=False) if not find_all else self.resolver.resolve_all(target)
        elif self.ide_deps and isinstance(target, self.ide_deps['WebElement']):
            # It might already be a WebElement
            return target
        else:
            raise WorkflowConfigError(f"Invalid target type: {type(target)}")

    def execute_step(self, step: ActionStep, context: ExecutionContext) -> Any:
        """Execute a single action step."""
        step_type = step.type.lower()
        result = None
        
        # Helper to get value with template resolution
        # Use explicit None check to preserve False, 0, empty strings, etc.
        val = context.resolve_template(step.value if step.value is not None else "")

        # Get IDE dependencies if available (for convenience in step handlers)
        if self.ide_deps:
            pyautogui = self.ide_deps['pyautogui']
            pyperclip = self.ide_deps['pyperclip']
            StaleElementReferenceException = self.ide_deps['StaleElementReferenceException']
            parse_key_str = self.ide_deps['parse_key_str']
            parse_key_str_autogui = self.ide_deps['parse_key_str_autogui']
            is_task_end = self.ide_deps['is_task_end']
        
        retries = 1
        while retries >= 0:
            try:
                if step_type == "activate":
                    # Click the activation icon to open extension pane
                    element = self._resolve_target(step.target or "activation", context, force_reload=(retries==0))
                    self.controller.click(element)
                    context.last_element = element
                    time.sleep(0.5)
                
                elif step_type == "llm_check":
                    cli = self._ensure_cli()
                    screenshot_text = cli.get_screen_text()
                    prompt = val
                    if not prompt:
                        prompt = "Check the current screenshot of a coding agent to decide if it has finished its task or is waiting for user input, which is seen as 'finished'. Respond with 'finished' or 'working'."
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "user", "content": prompt + "\n\n" + screenshot_text}
                        ],
                    )
                    content = response.choices[0].message.content
                    logger.info(f"[llm_check] LLM response: {content}")
                    if step.output:
                        if "finished" in content:
                            context.outputs[step.output] = "finished"
                        elif "working" in content:
                            context.outputs[step.output] = "working"
                        else:
                            context.outputs[step.output] = "unknown"

                elif step_type == "execute_script":
                    script = val
                    if not script:
                        raise WorkflowConfigError("execute_script requires 'script' or 'value'")
                    logger.info(f"Executing script: {script}")
                    
                    try:
                        result = subprocess.run(
                            script,
                            shell=True,
                            capture_output=True,
                            text=True,
                            timeout=step.timeout if hasattr(step, 'timeout') and step.timeout else 300
                        )
                        
                        output_data = {
                            "stdout": result.stdout,
                            "stderr": result.stderr,
                            "returncode": result.returncode,
                            "success": result.returncode == 0
                        }
                        
                        if result.returncode != 0:
                            logger.warning(f"Script exited with code {result.returncode}: {result.stderr}")
                        
                        if step.output:
                            context.outputs[step.output] = output_data
                        logger.info(f"Script execution completed: {output_data}")
                        
                        
                    except subprocess.TimeoutExpired as e:
                        logger.error(f"Script execution timeout: {e}")
                        if step.output:
                            context.outputs[step.output] = {
                                "error": "timeout",
                                "stdout": e.stdout.decode() if e.stdout else "",
                                "stderr": e.stderr.decode() if e.stderr else "",
                                "success": False
                            }
                        raise ActionExecutionError(f"Script execution timed out: {script}") from e

                elif step_type == "cli_start":
                    cli = self._ensure_cli()
                    command = context.resolve_template(step.command or [])
                    logger.info(f"Starting CLI with command: {command}")

                    if not command and isinstance(val, str) and val:
                        command = shlex.split(val)
                    if not command and isinstance(step.target, str) and step.target:
                        command = shlex.split(step.target)
                    if not command:
                        raise WorkflowConfigError("cli_start requires 'command' (list) or 'value' (string)")

                    rows = int(step.rows or step.x or 30)
                    cols = int(step.cols or step.y or 120)
                    cli.start(command, rows=rows, cols=cols)
                    if step.output:
                        context.outputs[step.output] = True

                elif step_type == "cli_input":
                    cli = self._ensure_cli()
                    logger.debug(f"CLI Input: {val}")
                    cli.write(val)
                    if step.output:
                        context.outputs[step.output] = val
                        logger.debug(f"Set {step.output} = {val}")
                
                elif step_type == "cli_check_line":
                    cli = self._ensure_cli()
                    pattern = val or step.pattern or step.target
                    if not pattern:
                        raise WorkflowConfigError("cli_wait_for_text requires a pattern in value/pattern/target")
                    use_regex = bool(step.use_regex)
                    text = cli.get_screen_text()
                    lines = text.splitlines()
                    start_lineno = step.start_lineno if step.start_lineno is not None else 0
                    end_lineno = step.end_lineno if step.end_lineno is not None else len(lines)
                    lines_to_check = lines[start_lineno:end_lineno]
                    if use_regex:
                        if re.search(pattern, '\n'.join(lines_to_check), re.MULTILINE):
                            logger.debug(f"'Found in regex: {pattern}'")
                            found = True
                        else:
                            found = False
                    else:
                        if pattern in ''.join(lines_to_check):
                            logger.debug(f"Found in text: '{pattern}'")
                            found = True
                        else:
                            found = False

                    if step.output:
                        context.outputs[step.output] = found
                    if not found:
                        logger.debug(f"Not found: {pattern}")
                    

                elif step_type == "cli_wait_for_text":
                    cli = self._ensure_cli()
                    pattern = val or step.pattern or step.target
                    if not pattern:
                        raise WorkflowConfigError("cli_wait_for_text requires a pattern in value/pattern/target")
                    timeout = float(context.resolve_template(str(step.timeout or 30)))
                    use_regex = bool(step.use_regex)
                    found = cli.wait_for_text(pattern, timeout=timeout, use_regex=use_regex)
                    if step.output:
                        context.outputs[step.output] = found
                    if not found:
                        logger.info(f"Pattern not found within {timeout}s: {pattern}")

                elif step_type == "cli_screen_text":
                    cli = self._ensure_cli()
                    text = cli.get_screen_text()
                    if step.output:
                        context.outputs[step.output] = text

                elif step_type == "cli_screen_stability":
                    cli = self._ensure_cli()
                    text = cli.get_screen_text()
                    normalized_text = self._normalize_cli_screen_text(text)

                    threshold = float(context.resolve_template(str(step.value if step.value is not None else step.timeout or 10)))
                    state_key = step.state_key or step.key or "_cli_screen_stability"
                    now = time.time()

                    state = context.outputs.get(state_key)
                    current_hash = hashlib.sha256(normalized_text.encode("utf-8", errors="ignore")).hexdigest()
                    if not isinstance(state, dict):
                        state = {
                            "hash": current_hash,
                            "last_changed_at": now,
                            "last_seen_at": now,
                        }
                        changed = True
                    else:
                        changed = state.get("hash") != current_hash
                        if changed:
                            state["hash"] = current_hash
                            state["last_changed_at"] = now
                        state["last_seen_at"] = now

                    stable_for = max(0.0, now - float(state.get("last_changed_at", now)))
                    is_stable = stable_for >= threshold
                    context.outputs[state_key] = state

                    if step.text_output:
                        context.outputs[step.text_output] = text
                    if step.stable_for_output:
                        context.outputs[step.stable_for_output] = stable_for
                    if step.changed_output:
                        context.outputs[step.changed_output] = changed
                    if step.output:
                        context.outputs[step.output] = is_stable

                    logger.debug(
                        "CLI screen stability: changed=%s stable_for=%.2fs threshold=%.2fs stable=%s",
                        changed,
                        stable_for,
                        threshold,
                        is_stable,
                    )

                elif step_type == "cli_full_log":
                    cli = self._ensure_cli()
                    log_text = cli.get_full_log()
                    if step.output:
                        context.outputs[step.output] = log_text

                elif step_type == "cli_screenshot":
                    cli = self._ensure_cli()
                    screenshot_b64 = cli.get_screenshot_base64()
                    if step.output:
                        context.outputs[step.output] = screenshot_b64

                elif step_type == "cli_stop":
                    cli = self._ensure_cli()
                    cli.terminate()
                    if step.output:
                        context.outputs[step.output] = True
                
                elif step_type == "time_begin":
                    self.time_begin = time.time()

                elif step_type == "time_end":
                    self.time_end = time.time()

                elif step_type == "direct_click":
                    pyautogui.click(step.x, step.y)
                    logger.debug(f"Direct clicked element: x:{step.x},y:{step.y}")
                
                elif step_type == "check_task_end":
                    logger.info("Checking if task is end...")
                    elements = self.controller.driver.find_elements("xpath", "//*[contains(@Name, '?')]")
                    logger.info(f"Found elements: {elements}")
                    if is_task_end(elements):
                        context.outputs[step.output] = True
                    else:
                        context.outputs[step.output] = False
                    
                elif step_type == "click":
                    element = self._resolve_target(step.target, context)
                    self.controller.click(
                        element,
                        double=(step.double is True)
                    )
                    logger.info(f"Clicked element: {step.target}")
                    context.last_element = element
                
                elif step_type == "copy_all":
                    elements = self._resolve_target(step.target, context, force_reload=(retries==0), find_all=True)
                    for elem in elements:
                        elem.click()
                        time.sleep(1)
                        clipboard_content = pyperclip.paste()
                        self.chat_history.append({
                            "role": "assistant",
                            "content": clipboard_content
                        })

                elif step_type == "clear":
                    element = self._resolve_target(step.target, context, force_reload=(retries==0))
                    element.click()
                    element.send_keys(parse_key_str("^a{DELETE}"))
                    context.last_element = element
                    
                elif step_type == "input":
                    element = self._resolve_target(step.target, context, force_reload=(retries==0))
                    logger.info(f"Inputting text into element: {val}") 
                    self.controller.input_text(element, val, clear_first=False)
                    context.last_element = element
                
                elif step_type == "direct_input":
                    if step.target:
                        element = self._resolve_target(step.target, context, force_reload=(retries==0))
                        logger.info(f"Inputting text into element: {val}") 
                        element.click()
                    self.controller.direct_input_text(val)
                
                elif step_type == "direct_input_without_clear":
                    logger.info(f"direct_input_text: write {val} without clear")
                    pyautogui.write(val)  # Type the text
                    pyautogui.press('enter')

                elif step_type == "set_text":
                    # In Appium, set_text is essentially input_text with clear
                    element = self._resolve_target(step.target, context, force_reload=(retries==0))
                    self.controller.input_text(element, val, clear_first=True)
                    context.last_element = element
                
                elif step_type == "wait":
                    if step.duration:
                        time.sleep(step.duration)
                    elif step.target and step.condition:
                        # Leverage Controller's implicit/explicit wait capabilities via resolver
                        self.resolver.wait_for_selector(
                            step.target,
                            condition=step.condition,
                            timeout=step.timeout,
                        )
                elif step_type == "check_element":
                    try:
                        self._resolve_target(
                            step.target,
                            context,
                            force_reload=(retries==0)
                        )
                        context.outputs[step.output] = True
                        logger.info(f"{step.target} Found!!")
                    except Exception as e:
                        context.outputs[step.output] = False
                        logger.info(f"{step.target} Not found!! {e}")

                
                elif step_type == "check_element_vision":
                    try:
                        location = pyautogui.locateOnScreen(step.value, confidence=0.9, grayscale=True)
                    except pyautogui.ImageNotFoundException:
                        location = None

                    current_time = time.time()

                    if location:
                        # The button is visible -> It is still generating
                        print("Status: Generating... (Stop button detected)")
                        context.outputs[step.output] = True
                    else:
                        # The button is not visible -> It is finished
                        print("Status: Finished (Stop button not detected)")
                        context.outputs[step.output] = False
                
                elif step_type == "click_element_vision":
                    try:
                        location = pyautogui.locateOnScreen(step.value, confidence=0.9, grayscale=True)
                    except pyautogui.ImageNotFoundException:
                        location = None

                    if location:
                        center = pyautogui.center(location)
                        pyautogui.click(center.x, center.y)
                        logger.info(f"Clicked vision element at: x:{center.x},y:{center.y}")
                    else:
                        raise ElementNotFoundError(f"Element not found on screen: {step.value}")

                        
                elif step_type == "wait_visible":
                    # This creates a dynamic wait for visibility
                    element = self._resolve_target(step.target, context, force_reload=(retries==0))
                    if hasattr(element, 'is_displayed'):
                        # If we already have the element, check visibility
                        # Note: In Appium Windows, is_displayed() is sometimes always True
                        pass
                    context.last_element = element
                    
                elif step_type == "focus":
                    element = self._resolve_target(step.target, context, force_reload=(retries==0))
                    element.click() # Clicking is the best way to focus in UIA
                    context.last_element = element
                    
                elif step_type == "scroll":
                    pyautogui.click(step.x, step.y)
                    pyautogui.scroll(-1000)
                
                elif step_type == "move_scroll":
                    pyautogui.moveTo(step.x, step.y)
                    pyautogui.scroll(step.value)
                
                # elif step_type == "hover":
                #     element = self._resolve_target(step.target, context, force_reload=(retries==0))
                #     self.controller.hover(element)
                #     context.last_element = element
                #     if step.duration:
                #         time.sleep(step.duration)
                    
                elif step_type == "keyboard":
                    keys = parse_key_str(val)
                    element = None
                    if step.target:
                        try:
                            element = self._resolve_target(step.target, context, force_reload=(retries==0))
                        except Exception as e:
                            pyautogui.hotkey(parse_key_str_autogui(val))
                        
                    if element:
                        element.send_keys(*keys)
                    else:
                        logger.info(f"No active element found, sending keys to driver: {keys}")
                        # Send to active element
                        pyautogui.hotkey(parse_key_str_autogui(val))
                
                elif step_type == "run_action":
                    action_name = val or step.target
                    if not action_name:
                        raise ValueError("run_action requires action name")
                    action_name = context.resolve_template(str(action_name))
                    action_outputs = self.execute_action(action_name, context.params)
                
                elif step_type in ["check", "uncheck"]:
                    element = self._resolve_target(step.target, context, force_reload=(retries==0))
                    should_check = (step_type == "check")
                    self._ensure_checked(element, checked=should_check)
                    context.last_element = element
                
                elif step_type in ["check_all", "uncheck_all"]:
                    elements = self._resolve_target(step.target, context, force_reload=(retries==0))
                    should_check = (step_type == "check_all")
                    if isinstance(elements, list):
                        for elem in elements:
                            self._ensure_checked(elem, checked=should_check)
                    else:
                        self._ensure_checked(elements, checked=should_check)
                
                elif step_type == "wait_for_element":
                    self._handle_wait_for_element(step, context)
                
                elif step_type == "read_exported_chat":
                    self._handle_read_chat(step, context)
                
                elif step_type == "update_json_file":
                    self._handle_update_json_file(step, context)
                
                elif step_type == "set_output":
                    key = step.key or "result"
                    # If value looks like an expression (contains operators/comparisons), evaluate it
                    # Otherwise just use the template-resolved value
                    if isinstance(val, str) and any(op in val for op in ['==', '!=', '>', '<', '>=', '<=', ' in ', ' or ', ' and ', ' not ', '+', '-', '*', '/']):
                        # Evaluate as Python expression with outputs as context
                        eval_failed = object()
                        result = context.safe_eval(val, default=eval_failed)
                        if result is eval_failed:
                            logger.warning(
                                "Failed to evaluate set_output expression for key '%s'; storing raw value: %s",
                                key,
                                val,
                            )
                            result = val
                        context.outputs[key] = result
                        logger.debug(f"Set output '{key}' = {result} (evaluated from: {val})")
                    else:
                        context.outputs[key] = val
                        logger.debug(f"Set output '{key}' = {val}")
                
                elif step_type == "start_program":
                    self._handle_start_program(step, context, val)
                
                elif step_type == "close_program":
                    self._handle_close_program(step, context, val)
                
                elif step_type == "disconnect":
                    # Appium specific: we might detach the driver session or just clear local refs
                    # Here we just clear local refs to force re-find later
                    self.controller.driver = None 
                    if step.output:
                        context.outputs[step.output] = True
                
                elif step_type == "reconnect":
                    # Re-run start logic which handles attaching
                    timeout = float(context.resolve_template(str(step.timeout or 30)))
                    # Update controller timeout temporarily
                    old_timeout = self.controller.timeout
                    self.controller.timeout = timeout
                    
                    success = self.controller.start(attach_only=True)
                    self.controller.timeout = old_timeout
                    
                    if step.output:
                        context.outputs[step.output] = success
                elif step_type == "log":
                    if step.level == "debug":
                        logger.debug(val)
                    elif step.level == "warning":
                        logger.warning(val)
                    elif step.level == "error":
                        logger.error(val)
                    elif step.level == "info":
                        logger.info(val)
                elif step_type == "check_n_elements":
                    elements = self._resolve_target(step.target, context, force_reload=(retries==0), find_all=True)
                    ori_len = context.outputs.get(step.value, 0)
                    context.outputs[step.value] = len(elements)
                    context.outputs[step.output] = len(elements) > ori_len
                elif step_type == "check_timeout":
                    current_time = time.time()
                    logger.debug(f"start_time:{context.outputs[step.start_time]}")
                    logger.debug(f"end_time: {current_time}")
                    if current_time - context.outputs[step.start_time] > float(val):
                        context.outputs[step.output] = True 
                    else:
                        context.outputs[step.output] = False
                elif step_type == "time_mark":
                    context.outputs[step.output] = time.time()
                elif step_type == "jump_to":
                    pass
                else:
                    logger.warning(f"Unknown step type ignored: {step_type}")
                break

            except Exception as ex:
                # Check if it's a StaleElementReferenceException (only in IDE mode)
                if self.ide_deps and isinstance(ex, self.ide_deps['StaleElementReferenceException']):
                    logger.warning(f"Stale element encountered during '{step_type}'. Retrying...")
                    retries -= 1
                    if retries < 0:
                        raise ActionExecutionError(f"Element became stale and could not be recovered: {step.target}")
                    continue
                
                # Re-raise other exceptions to be handled by the outer except block
                raise
            
            except Exception as e:
                # If optional, we might just log and return
                if step.optional:
                    logger.info(f"Optional step '{step.type}' skipped (element not found). Error: {e}")
                    return
                logger.error(e)
                # Wrap generic errors into our custom type
                raise ActionExecutionError(f"Failed to execute '{step_type}': {str(e)}") from e
        
        
        return result

    def _ensure_checked(self, element, checked: bool = True):
        """Ensure a checkbox is in the desired state using Appium attributes."""
        try:
            # 1. Determine current state
            is_selected = element.is_selected()
            
            # Note: Windows Automation "ToggleState" (0=Unchecked, 1=Checked, 2=Indeterminate)
            # Some elements don't return is_selected() correctly, check attribute
            if not is_selected:
                toggle_state = element.get_attribute("Toggle.ToggleState")
                if toggle_state == '1':
                    is_selected = True

            if is_selected != checked:
                element.click()
                logger.debug(f"Toggled checkbox to {checked}")
                
        except Exception as e:
            logger.warning(f"Checkbox toggle failed: {e}")

    def _handle_start_program(self, step: ActionStep, context: ExecutionContext, val: str = "Code.exe"):
        exe = context.resolve_template(step.executable or "")
        ws = context.resolve_template(step.workspace or "")
        wait = float(context.resolve_template(str(step.wait_time or 5.0)))
        timeout = float(context.resolve_template(str(step.timeout or 30)))
        
        attempt = 0
        success = False
        retrying = False
        while attempt < 3 and not success:
            attempt += 1
            # Kill any existing process before starting fresh
            try:
                subprocess.run(f"taskkill /f /im {val}", shell=True, timeout=5, capture_output=True)
                time.sleep(1)  # Wait for process to be killed
            except Exception as e:
                logger.warning(f"Failed to kill existing {val}: {e}")
            
            # Try to start the program
            success = self.controller.start(
                executable_path=exe if exe else None,
                workspace_path=ws if ws else None,
                timeout=int(timeout) if timeout else None,
                wait_time=int(wait) if wait else None,
                retrying=retrying
            )
            
            if not success and attempt < 3:
                logger.warning(f"Start attempt {attempt} failed, retrying...")
                time.sleep(5)
            retrying = True
        
        # Wait for initialization
        time.sleep(wait)
        
        if step.output:
            context.outputs[step.output] = success

    def _handle_close_program(self, step: ActionStep, context: ExecutionContext, val: str = "Code.exe"):
        force = str(context.resolve_template(str(step.force))).lower() in ('true', '1', 'yes')
        try:
            if force:
                # Use subprocess for better control
                result = subprocess.run(f"taskkill /f /im {val}", shell=True, timeout=5, capture_output=True)
                if result.returncode == 0:
                    logger.info(f"Force killed {val}")
                else:
                    logger.warning(f"Failed to kill {val}: {result.stderr.decode()}")
            elif self.controller.driver:
                self.controller.driver.close()  # Closes window gracefully
            
            if step.output:
                context.outputs[step.output] = True
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout while closing {val}")
            if step.output:
                context.outputs[step.output] = False
        except Exception as e:
            logger.error(f"Failed to close program: {e}")
            if step.output:
                context.outputs[step.output] = False

    def _handle_update_json_file(self, step: ActionStep, context: ExecutionContext):
        """Updates a JSON file with new values, supports nested keys using dot notation."""
        file_path = context.resolve_template(step.file_path or step.target or "")
        if not file_path:
            raise WorkflowConfigError("update_json_file requires 'file_path' or 'target'")
        
        # Get the updates dictionary from step.updates or step.value
        updates = step.updates if hasattr(step, 'updates') and step.updates else {}
        if not updates and hasattr(step, 'value') and isinstance(step.value, dict):
            updates = step.value
        
        # Resolve templates in updates
        resolved_updates = {}
        for key, value in updates.items():
            resolved_key = context.resolve_template(key) if isinstance(key, str) else key
            resolved_value = context.resolve_template(value) if isinstance(value, str) else value
            resolved_updates[resolved_key] = resolved_value
        
        try:
            # Read existing JSON file or create empty dict
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                data = {}
            
            # Apply updates - support nested keys with dot notation (e.g., "env.API_KEY")
            for key, value in resolved_updates.items():
                if '.' in key:
                    # Handle nested keys
                    keys = key.split('.')
                    current = data
                    for k in keys[:-1]:
                        if k not in current:
                            current[k] = {}
                        current = current[k]
                    current[keys[-1]] = value
                else:
                    # Simple key
                    data[key] = value
            
            # Write back to file
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Updated JSON file: {file_path}")
            if step.output:
                context.outputs[step.output] = True
        
        except Exception as e:
            logger.error(f"Failed to update JSON file {file_path}: {e}")
            if step.output:
                context.outputs[step.output] = False
            raise WorkflowConfigError(f"Failed to update JSON file: {e}")

    def _handle_read_chat(self, step: ActionStep, context: ExecutionContext):
        """Reads file content from subdirectories with optional pattern matching."""
        directory = context.resolve_template(step.directory or ".")
        
        # 1. Get the pattern from the step, or default to a multi-extension search
        # If step.pattern is like "*.json", use it. Otherwise, search for md and json.
        custom_pattern = context.resolve_template(step.pattern) if hasattr(step, 'pattern') and step.pattern else None
        
        chat_files = []
        
        if custom_pattern:
            # Recursive search using custom pattern
            # ** means "this directory and all subdirectories"
            search_path = os.path.join(directory, "**", custom_pattern)
            chat_files = glob.glob(search_path, recursive=True)
        else:
            # Default recursive search for .md and .json
            md_files = glob.glob(os.path.join(directory, "**", "*.md"), recursive=True)
            json_files = glob.glob(os.path.join(directory, "**", "*.json"), recursive=True)
            chat_files = md_files + json_files

        # 2. Filter out directories (in case a directory name matches the pattern)
        chat_files = [f for f in chat_files if os.path.isfile(f)]

        if chat_files:
            # 3. Find the latest file by modification time
            latest_file = max(chat_files, key=os.path.getmtime)
            attempts = 0
            try:
                while True:
                    with open(latest_file, 'rb') as f:
                        content = f.read()
                    content = content.decode('utf-8', errors='ignore') 
                    result = {
                        "file_path": latest_file,
                        "content": content,
                        "exported_at": datetime.fromtimestamp(os.path.getmtime(latest_file)).strftime("%Y-%m-%d %H:%M:%S"),
                    }

                    if content:
                        os.remove(latest_file)
                        if step.output:
                            context.outputs[step.output] = result
                        break
                    else:
                        if attempts >= 5: raise Exception("No content found")
                        time.sleep(2)
                        attempts += 1


            except Exception as e:
                if step.output: 
                    context.outputs[step.output] = {"error": str(e)}
        else:
            if step.output: 
                context.outputs[step.output] = {"error": f"No files matching pattern found in {directory}"}

    def execute_action(self, action_name: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute a named action."""
        if action_name not in self.config.actions:
            raise ValueError(f"Unknown action: {action_name}")
        
        action_def = self.config.actions[action_name]
        context = ExecutionContext(params)
        
        logger.info(f"Executing action: {action_name}")
        for step in action_def.steps:
            self.execute_step(step, context)
        
        return context.outputs

    def execute_workflow(self, workflow_name: str, max_jumps: int, params: Optional[Dict[str, Any]] = None, stop_event: Optional[threading.Event] = None, debug_port: int = -1) -> Dict[str, Any]:
        """Execute a workflow."""
        if debug_port > 0:
            set_trace(host="0.0.0.0", port=debug_port)
        if workflow_name not in self.config.workflows:
            raise ValueError(f"Unknown workflow: {workflow_name}")
        
        workflow_def = self.config.workflows[workflow_name]
        params = params or {}
        
        # Parameter validation
        for param_def in workflow_def.parameters:
            if param_def.required and param_def.name not in params:
                raise ValueError(f"Missing required parameter: {param_def.name}")
            if param_def.name not in params and param_def.default is not None:
                params[param_def.name] = param_def.default
        
        context = ExecutionContext(params)
        logger.info(f"Executing workflow: {workflow_name}")

        steps = workflow_def.steps
        idx = 0
        max_steps = len(steps)
        
        # Track jumps to prevent infinite loops
        jump_count = 0
        time_record = []
        # context.outputs['chat_history'] = []

        while idx < max_steps:
            if stop_event and stop_event.is_set():
                logger.warning(f"🛑 Workflow step interrupted by cancellation: {e}")
                context.outputs["status"] = "cancelled"
                return context.outputs
            step = steps[idx]

            logger.debug(f"Step {idx}:{step.type}".center(20,"="))
            # 1. Check 'when' condition before executing
            if hasattr(step, 'when') and step.when:
                logger.debug(f"Evaluating condition: {step.when}")
                result = context.evaluate_condition(step.when)
                logger.debug(f"Result: {result}")
                if not result:
                    logger.debug(f"Skipping step {idx} ({step.type}) - condition not met")
                    idx += 1
                    continue

            # 2. Execute the step
            # execute_step should return a result or status
            start_time = time.time()
            try:
                if "input" in step.type:
                    self.chat_history.append({
                        "role": "user",
                        "content": context.resolve_template(step.value or "")
                    })
                result = self.execute_step(step, context)
                end_time = time.time()
                step_dict = {k: v for k, v in step.model_dump().items() if v is not None and k != "button" and k != "double"}
                time_record.append({"step_index": idx, "step": step_dict, "duration": end_time - start_time})
                
            except Exception as e:
                if step.optional and isinstance(e, (ElementNotFoundError, ActionExecutionError)):
                    logger.warning(f"Optional step {idx} ({step.type}) failed: {e}")
                    idx += 1
                    continue
                
                if stop_event and stop_event.is_set():
                    logger.warning(f"🛑 Workflow step interrupted by cancellation: {e}")
                    context.outputs["status"] = "cancelled"
                    return context.outputs
                # CRITICAL: Capture diagnostic info before dying
                self._capture_diagnostics(workflow_name, step_index=idx)
                
                logger.error(f"Workflow '{workflow_name}' failed at step {idx} [{step.type}]: {e}")
                raise # Re-raise to let the server framework return 500
            
            # 3. Handle 'jump_to' logic
            # If the step type is 'jump' or if the step has a 'jump_if' configuration
            target_id = None

            if step.type == "jump_to" and step.condition and "task_end" in step.condition:
                logger.info(f"Task end: {context.outputs['task_end']}")
            if step.type == "jump_to" and context.evaluate_condition(step.condition):
                target_id = step.target_id

            if target_id:
                jump_count += 1
                if max_jumps > 0 and jump_count > max_jumps:
                    logger.error("Max jumps reached. Potential infinite loop.")
                    break
                
                # Find the index of the step with the matching ID
                new_idx = self._find_step_by_id(steps, target_id)
                if new_idx is not None:
                    logger.info(f"Jumping to step: {target_id} (index {new_idx})")
                    idx = new_idx
                    continue # Re-run the loop at the new index

            idx += 1
        
        if "chat_history" not in context.outputs:
            context.outputs["chat_history"] = {
                "file_path": None,
                "content": json.dumps(self.chat_history),
                "exported_at": datetime.fromtimestamp(time.time()).strftime("%Y-%m-%d %H:%M:%S"),
            }
        context.outputs["time_record"] = time_record 
        
        return context.outputs

    def _capture_diagnostics(self, workflow_name: str, step_index: int):
        """Save screenshot and page source for debugging."""
        try:
            timestamp = int(time.time())
            filename = f"error_{workflow_name}_step{step_index}_{timestamp}"
            
            # Save Screenshot
            self.controller.driver.save_screenshot(f"{filename}.png")
            
            # Save Page Source (XML) - vital for debugging Appium selectors
            with open(f"{filename}.xml", "w", encoding="utf-8") as f:
                f.write(self.controller.driver.page_source)
                
            logger.info(f"Saved error diagnostics to {filename}")
        except Exception as log_err:
            logger.error(f"Failed to capture diagnostics: {log_err}")

    def query_state(self) -> Dict[str, Any]:
        """Query state defined in config."""
        state = {}
        for state_name, state_query in self.config.state.items():
            try:
                element = self.resolver.resolve_selector(state_query.target, use_cache=False)
                method = state_query.method
                
                if method == "is_visible":
                    state[state_name] = element.is_displayed()
                elif method == "is_enabled":
                    state[state_name] = element.is_enabled()
                elif method == "exists":
                    state[state_name] = (element is not None)
                elif method == "get_text":
                    state[state_name] = self.controller.get_text(element)
                else:
                    state[state_name] = None
            except Exception:
                state[state_name] = None if state_query.method != "exists" else False
        return state

    def _should_execute(self, step, context):
        if not step.when:
            return True
        return bool(eval(step.when, {}, context.outputs))

    def _find_step_by_id(self, steps, target_id):
        for i, step in enumerate(steps):
            if hasattr(step, 'id') and step.id == target_id:
                return i
        return None
