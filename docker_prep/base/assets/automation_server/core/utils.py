from typing import List
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.keys import Keys

MODIFIER_KEYS = {
    "^": Keys.CONTROL,
    "+": Keys.SHIFT,
    "%": Keys.ALT,
    "#": Keys.META,
}

NAMED_KEYS = {
    "BACKSPACE": Keys.BACKSPACE,
    "BS": Keys.BACKSPACE,
    "BKSP": Keys.BACKSPACE,
    "ENTER": Keys.ENTER,
    "TAB": Keys.TAB,
    "ESC": Keys.ESCAPE,
    "DELETE": Keys.DELETE,
    "LEFT": Keys.LEFT,
    "RIGHT": Keys.RIGHT,
    "UP": Keys.UP,
    "DOWN": Keys.DOWN,
}

MODIFIER_KEYS_AUTOGUI = {
    "^": "ctrl",
    "+": "shift",
    "%": "alt",
    "#": "win",
}

NAMED_KEYS_AUTOGUI = {
    "BACKSPACE": "backspace",
    "ENTER": "enter",
    "TAB": "tab",
    "ESC": "esc",
    "DELETE": "delete",
    "LEFT": "left",
    "RIGHT": "right",
    "UP": "up",
    "DOWN": "down",
}


import re

TOKEN_RE = re.compile(r"\{([^}]+)\}|(.)")

def parse_key_str(val: str):
    keys_list = []

    for match in TOKEN_RE.finditer(val):
        named_key, char = match.groups()

        # Case 1: named key like {BACKSPACE}
        if named_key:
            key_name = named_key.upper()
            if key_name not in NAMED_KEYS:
                raise ValueError(f"Unknown named key: {{{named_key}}}")
            keys_list.append(NAMED_KEYS[key_name])

        # Case 2: modifier like ^ + %
        elif char in MODIFIER_KEYS:
            keys_list.append(MODIFIER_KEYS[char])

        # Case 3: literal character
        else:
            keys_list.append(char)

    return keys_list

def parse_key_str_autogui(val: str):
    keys_list = []

    for match in TOKEN_RE.finditer(val):
        named_key, char = match.groups()

        # Case 1: named key like {BACKSPACE}
        if named_key:
            key_name = named_key.upper()
            if key_name not in NAMED_KEYS_AUTOGUI:
                raise ValueError(f"Unknown named key: {{{named_key}}}")
            keys_list.append(NAMED_KEYS_AUTOGUI[key_name])

        # Case 2: modifier like ^ + %
        elif char in MODIFIER_KEYS_AUTOGUI:
            keys_list.append(MODIFIER_KEYS_AUTOGUI[char])

        # Case 3: literal character
        else:
            keys_list.append(char)

    return keys_list


request_indicators = [
    "please provide",
    "could you clarify",
    "which file",
    "can you tell me",
    "i need more information",
    "waiting for your input"
]

def is_task_end(elements: List[WebElement]) -> bool:
    for element in elements:
        text = element.text.lower()
        for indicator in request_indicators:
            if indicator in text:
                return False
    return True
