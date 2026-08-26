class AutomationError(Exception):
    """Base class for all automation errors."""
    pass

class WorkflowConfigError(AutomationError):
    """Issues with workflow definition or parameters (400 Bad Request equivalent)."""
    pass

class ElementNotFoundError(AutomationError):
    """UI Element could not be found after timeout."""
    pass

class ActionExecutionError(AutomationError):
    """Interaction with the element failed (e.g., click intercepted, stale)."""
    pass