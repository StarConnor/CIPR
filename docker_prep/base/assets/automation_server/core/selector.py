"""Element selector resolver - resolves config selectors to UI elements via Appium."""
from typing import Any, Dict, List, Optional, Union
import logging

from selenium.common.exceptions import StaleElementReferenceException, WebDriverException
from appium.webdriver.webelement import WebElement

from ..config.schema import Selector, SelectorCriteria, ExtensionConfig
from .controller import VSCodeController

logger = logging.getLogger(__name__)


class SelectorResolver:
    """Resolves selector definitions to actual UI elements."""
    
    def __init__(self, controller: VSCodeController, extension_config: ExtensionConfig):
        self.controller = controller
        self.config = extension_config
        self._element_cache: Dict[str, Any] = {}
        # Extract extension name for scoped searches
        self.extension_name = extension_config.pane_name
    
    def clear_cache(self):
        """Clear the element cache."""
        self._element_cache.clear()
    
    def _criteria_to_dict(self, criteria: SelectorCriteria) -> Dict[str, Any]:
        """
        Convert SelectorCriteria to a dict compatible with VSCodeController.find_element.
        """
        result = {}
        
        # Direct mappings
        if criteria.auto_id:
            result['auto_id'] = criteria.auto_id
        
        # 'title' in pywinauto usually maps to 'Name' in Accessibility
        if criteria.title:
            result['name'] = criteria.title
            
        # WinAppDriver maps standard tag names (Button, Group, etc.)
        if criteria.control_type:
            result['control_type'] = criteria.control_type
            
        if criteria.class_name:
            result['class_name'] = criteria.class_name
        
        if criteria.xpath:
            result['xpath'] = criteria.xpath
            
        # Handling Regex: WinAppDriver XPath 1.0 doesn't support regex natively.
        # If title_re is provided, we might fallback to searching by class or control type
        # and filtering, OR construct a 'contains' XPath if it looks simple.
        if criteria.title_re and not criteria.title:
            # Simple heuristic: if regex looks like ".*Word.*", treat as contains
            clean_re = criteria.title_re.replace(".*", "").replace("^", "").replace("$", "")
            if clean_re:
                # Construct an XPath that looks for Name containing the string
                # This is a robust fallback for "Welcome - VS Code" type titles
                result['xpath'] = f"//*[contains(@Name, '{clean_re}')]"
        
        return result
    
    def resolve_selector(
        self,
        selector: Union[str, Selector],
        use_cache: bool = True,
    ) -> WebElement:
        """
        Resolve a selector to a UI element (WebElement).
        """
        selector_name = None
        selector_def = None

        # 1. Resolve Definition
        if isinstance(selector, str):
            selector_name = selector
            
            # Check Cache
            if use_cache and selector_name in self._element_cache:
                element = self._element_cache[selector_name]
                if self._is_element_valid(element):
                    return element
                else:
                    # Remove invalid element
                    del self._element_cache[selector_name]
            
            # Look up config
            if selector_name not in self.config.selectors:
                raise ValueError(f"Unknown selector: {selector_name}")
            selector_def = self.config.selectors[selector_name]
        
        elif isinstance(selector, Selector):
            selector_def = selector
        else:
            raise ValueError(f"Invalid selector type: {type(selector)}")

        
        # 4. Build Criteria
        criteria_dict = self._criteria_to_dict(selector_def.criteria)
        
        # 5. Find Element
        # Controller's find_element handles waiting logic (default timeout)
        element = self.controller.find_element(
            criteria_dict,
            timeout=selector_def.wait_timeout
        )

        # 7. Cache
        if selector_name and use_cache and element:
            self._element_cache[selector_name] = element
        
        return element
    
    def resolve_all(self, selector_name: str) -> List[Any]:
        """Resolve a selector to all matching elements."""
        if selector_name not in self.config.selectors:
            raise ValueError(f"Unknown selector: {selector_name}")
        
        selector_def = self.config.selectors[selector_name]
        
        criteria = self._criteria_to_dict(selector_def.criteria)
        
        return self.controller.find_elements(criteria=criteria)

    def _is_element_valid(self, element) -> bool:
        """Check if a cached element is still attached to the DOM."""
        try:
            # Accessing a property (like is_displayed or id) checks staleness
            return element.is_displayed() or True 
        except (StaleElementReferenceException, WebDriverException):
            return False

    def element_exists(self, selector: Union[str, Selector]) -> bool:
        """Check if an element matching the selector exists."""
        try:
            # Use False for cache to check real-time existence
            self.resolve_selector(selector, use_cache=False)
            return True
        except Exception:
            return False
            
    def wait_for_selector(
        self,
        selector: Union[str, Selector],
        condition: str = "exists",
        timeout: Optional[float] = None,
    ) -> bool:
        """
        Wait for a selector to match a condition.
        Delegates to Controller's implicit wait in resolve_selector.
        """
        try:
            # The resolve_selector method uses the Controller's find_element,
            # which has a WebDriverWait inside it. 
            # If we successfully resolve it, it "exists".
            element = self.resolve_selector(selector, use_cache=False)
            return True
        except Exception:
            return False

    def find_element_by_selector_string(self, selector_str: str, timeout: float = 1.0):
        """Helper to find element by raw string name with custom timeout."""
        # This is used by the executor for interrupts (fast polling)
        # We temporarily patch the timeout in the definition if needed, or catch errors.
        if selector_str not in self.config.selectors:
            return None
        
        try:
            # We override the timeout in the controller call implicitly
            # by passing a separate timeout arg if we expose it,
            # but resolve_selector uses the config's timeout.
            # Workaround:
            selector_def = self.config.selectors[selector_str]
            original_timeout = selector_def.wait_timeout
            selector_def.wait_timeout = timeout
            
            el = self.resolve_selector(selector_str, use_cache=False)
            
            selector_def.wait_timeout = original_timeout
            return el
        except Exception:
            return None