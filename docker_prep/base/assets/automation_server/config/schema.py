"""Pydantic models for extension config validation."""
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class SelectorCriteria(BaseModel):
    """Criteria for finding a UI element."""
    title: Optional[str] = None
    title_re: Optional[str] = None
    control_type: Optional[str] = None
    auto_id: Optional[str] = None
    class_name: Optional[str] = None
    index: Optional[int] = None
    enabled_only: Optional[bool] = None
    visible_only: Optional[bool] = None
    help: Optional[str] = None 
    xpath: Optional[str] = None


class Selector(BaseModel):
    """Definition of how to locate a UI element."""
    criteria: SelectorCriteria = Field(default_factory=SelectorCriteria)
    parent: Optional[str] = None  # Reference to another selector name
    wait_timeout: Optional[float] = None


class ActionStep(BaseModel):
    """A single step in an action or workflow."""
    type: str  # click, input, wait, clear, collect_text, activate, wait_for_element, read_exported_chat, set_output, start_program, close_program, focus_window, etc.
    id: Optional[str] = None
    target: Optional[Union[str, Selector, List[str]]] = None  # Selector name or inline selector
    value: Optional[Union[int, float, str, dict]] = None  # For input type
    condition: Optional[str] = None  # For wait type: visible, enabled, exists
    timeout: Optional[Union[float, str]] = None  # Can be number or template string
    duration: Optional[float] = None  # For wait duration
    output: Optional[str] = None  # Variable name for output
    button: Optional[str] = "left"  # For click: left, right, middle
    double: Optional[bool] = False  # For double click
    poll_interval: Optional[Union[float, str]] = None  # For wait_for_element: polling interval
    directory: Optional[str] = None  # For read_exported_chat: directory to search
    key: Optional[str] = None  # For set_output: output key name
    # For start_program step
    executable: Optional[str] = None  # Path to executable
    workspace: Optional[str] = None  # Workspace/folder to open
    wait_time: Optional[Union[float, str]] = None  # Wait time for program startup
    # For close_program step
    force: Optional[Union[bool, str]] = None  # Force kill the program
    # Optional step - continues workflow even if this step fails
    optional: Optional[bool] = False  # If True, step failure won't stop workflow
    # Interrupt buttons - clicked if found while waiting (for wait_for_element)
    interrupts: Optional[List[str]] = None  # List of selector names to click if found while waiting
    # Scroll target - element to scroll down while waiting (for wait_for_element)
    scroll_target: Optional[str] = None  # Selector name to scroll down during each poll
    x: Optional[int] = None
    y: Optional[int] = None
    when: Optional[str] = None
    matched: Optional[str] = None
    target_id: Optional[str] = None
    level: Optional[str] = None
    start_time: Optional[str] = None
    pattern: Optional[str] = None
    # CLI specific helpers
    command: Optional[List[str]] = None
    rows: Optional[int] = None
    cols: Optional[int] = None
    use_regex: Optional[bool] = None
    start_lineno: Optional[int] = None
    end_lineno: Optional[int] = None
    file_path: Optional[str] = None
    # CLI screen stability helpers (for detecting idle/completed TUI sessions)
    text_output: Optional[str] = None  # For cli_screen_stability: variable name for raw screen text
    stable_for_output: Optional[str] = None  # Variable name for seconds since last screen change
    changed_output: Optional[str] = None  # Variable name for whether screen changed in this poll
    state_key: Optional[str] = None  # Context key used to store previous screen hash/timestamp
    


class ActionDef(BaseModel):
    """Definition of a named action."""
    description: Optional[str] = None
    steps: List[ActionStep]


class WorkflowParameter(BaseModel):
    """Parameter definition for workflows."""
    name: str
    type: str = "string"  # string, int, bool
    required: bool = False
    default: Optional[Any] = None


class WorkflowDef(BaseModel):
    """Definition of a workflow (multi-step operation with parameters)."""
    description: Optional[str] = None
    parameters: List[WorkflowParameter] = Field(default_factory=list)
    steps: List[ActionStep]


class StateQuery(BaseModel):
    """Definition of how to query UI state."""
    method: str  # is_visible, get_text, count_children, exists, is_enabled
    target: str  # Selector name


class ExtensionConfig(BaseModel):
    """Complete extension configuration."""
    name: str
    pane_name: Optional[str] = None
    display_name: Optional[str] = None
    version: str = "1.0"
    driver: str = "ide"  # ide | cli
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = "gpt-4o-mini"
    
    # UI element selectors
    selectors: Dict[str, Selector] = Field(default_factory=dict)
    
    # Named actions
    actions: Dict[str, ActionDef] = Field(default_factory=dict)
    
    # Complex workflows
    workflows: Dict[str, WorkflowDef] = Field(default_factory=dict)
    
    # State queries
    state: Dict[str, StateQuery] = Field(default_factory=dict)


class ServerConfig(BaseModel):
    """Server-level configuration."""
    host: str = "0.0.0.0"
    port: int = 8000
    vscode_process_name: str = "Code.exe"
    vscode_window_title: Optional[str] = None  # Optional: specific window title pattern
    extensions_dir: str = "extensions"
    log_level: str = "INFO"
    default_timeout: float = 10.0
    retry_interval: float = 0.5
