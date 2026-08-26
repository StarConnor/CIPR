"""API request/response models."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ============ Request Models ============

class InputRequest(BaseModel):
    """Request to send input to an extension."""
    text: str
    submit: bool = False  # Whether to also click send button
    clear_first: bool = True


class ActionRequest(BaseModel):
    """Request to execute a named action."""
    action: str
    params: Dict[str, Any] = Field(default_factory=dict)


class WorkflowRequest(BaseModel):
    """Request to execute a workflow."""
    workflow: str
    params: Dict[str, Any] = Field(default_factory=dict)
    screenshot_time: Optional[float] = None  # Time to take screenshot at during workflow
    debug_port: int = -1
    log_level: str = "INFO"  # Logging level for streaming logs: DEBUG, INFO, WARNING, ERROR
    stream_screenshots: bool = True  # Whether to produce screenshot SSE events during workflow execution
    stream_logs: bool = True  # Whether to produce log SSE events during workflow execution
    proxy_url: Optional[str] = None  # Proxy URL for the workflow execution environment
    max_jumps: int = 1000


class RawCommandRequest(BaseModel):
    """Request to execute raw pywinauto commands."""
    commands: List[Dict[str, Any]]


class SelectorRequest(BaseModel):
    """Request using a selector."""
    selector: str
    action: Optional[str] = None  # click, input, get_text, etc.
    value: Optional[str] = None
    timeout: Optional[float] = None


class RegisterExtensionRequest(BaseModel):
    """Request to register an extension from YAML."""
    yaml_config: str  # YAML string defining the extension
    overwrite: bool = False  # Whether to overwrite if extension already exists


# ============ Response Models ============

class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    vscode_connected: bool
    extensions_loaded: int


class ExtensionInfo(BaseModel):
    """Information about a loaded extension."""
    name: str
    display_name: Optional[str]
    version: str
    selectors: List[str]
    actions: List[str]
    workflows: List[str]
    state_queries: List[str]


class ExtensionListResponse(BaseModel):
    """List of registered extensions."""
    extensions: List[ExtensionInfo]


class ActionResponse(BaseModel):
    """Response from action execution."""
    success: bool
    action: str
    outputs: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class WorkflowResponse(BaseModel):
    """Response from workflow execution."""
    success: bool
    workflow: str
    outputs: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class StateResponse(BaseModel):
    """Response containing state information."""
    success: bool
    state: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class HistoryItem(BaseModel):
    """A single history item."""
    index: int
    text: str
    type: Optional[str] = None  # user, assistant, system, etc.


class HistoryResponse(BaseModel):
    """Response containing history."""
    success: bool
    messages: List[HistoryItem] = Field(default_factory=list)
    total_count: int = 0
    error: Optional[str] = None


class InputResponse(BaseModel):
    """Response from input operation."""
    success: bool
    error: Optional[str] = None


class ActivateResponse(BaseModel):
    """Response from activation."""
    success: bool
    extension: str
    error: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response."""
    success: bool = False
    error: str
    detail: Optional[str] = None


# ============ Extension Registration ============

class RegisterExtensionResponse(BaseModel):
    """Response from extension registration."""
    success: bool
    name: str
    message: str
    selectors: List[str] = Field(default_factory=list)
    actions: List[str] = Field(default_factory=list)
    workflows: List[str] = Field(default_factory=list)
    error: Optional[str] = None


class UnregisterExtensionResponse(BaseModel):
    """Response from extension unregistration."""
    success: bool
    name: str
    message: str
    error: Optional[str] = None


# ============ Dynamic YAML Execution ============

class DynamicWorkflowRequest(BaseModel):
    """Request to execute a workflow defined inline via YAML."""
    yaml_config: str  # YAML string defining selectors, actions, workflows
    workflow: Optional[str] = None  # Workflow name to execute (if defined in yaml)
    action: Optional[str] = None  # Action name to execute (if defined in yaml)
    params: Dict[str, Any] = Field(default_factory=dict)


class DynamicStepsRequest(BaseModel):
    """Request to execute steps defined inline."""
    steps: List[Dict[str, Any]]  # List of step definitions
    selectors: Dict[str, Any] = Field(default_factory=dict)  # Optional selector definitions
    params: Dict[str, Any] = Field(default_factory=dict)


class DynamicExecutionResponse(BaseModel):
    """Response from dynamic execution."""
    success: bool
    outputs: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None
