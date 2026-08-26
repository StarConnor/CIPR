"""
Integration test script for the VS Code Extension Automation Server.

This script tests the API endpoints against a running server.
Make sure the server is running before executing this script:
    python -m automation_server

Usage:
    python test_integration.py [--base-url http://localhost:8000]
"""
import argparse
import json
import sys
import time

try:
    import requests
except ImportError:
    print("Please install requests: pip install requests")
    sys.exit(1)


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_test(name: str, passed: bool, details: str = ""):
    """Print test result with color."""
    status = f"{Colors.GREEN}PASS{Colors.RESET}" if passed else f"{Colors.RED}FAIL{Colors.RESET}"
    print(f"  [{status}] {name}")
    if details and not passed:
        print(f"         {Colors.YELLOW}{details}{Colors.RESET}")


def print_section(name: str):
    """Print section header."""
    print(f"\n{Colors.BOLD}{Colors.BLUE}=== {name} ==={Colors.RESET}")


class APITester:
    """Test runner for the automation server API."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}/api/v1"
        self.passed = 0
        self.failed = 0
    
    def test(self, name: str, condition: bool, details: str = ""):
        """Record and print a test result."""
        if condition:
            self.passed += 1
        else:
            self.failed += 1
        print_test(name, condition, details)
    
    def run_all_tests(self):
        """Run all API tests."""
        print(f"{Colors.BOLD}Testing API at: {self.api_url}{Colors.RESET}")
        
        # Test server connectivity
        print_section("Server Connectivity")
        self.test_root_endpoint()
        self.test_health_endpoint()
        
        # Test extension discovery
        print_section("Extension Discovery")
        self.test_list_extensions()
        
        # Test extension registration
        print_section("Extension Registration")
        self.test_register_extension()
        self.test_register_extension_duplicate()
        self.test_use_registered_extension()
        self.test_unregister_extension()
        
        # Test dynamic YAML execution
        print_section("Dynamic YAML Execution")
        self.test_yaml_workflow()
        self.test_yaml_with_params()
        self.test_yaml_invalid()
        
        # Test dynamic steps execution
        print_section("Dynamic Steps Execution")
        self.test_steps_simple()
        self.test_steps_with_params()
        
        # Print summary
        print_section("Summary")
        total = self.passed + self.failed
        print(f"  Passed: {Colors.GREEN}{self.passed}{Colors.RESET}/{total}")
        print(f"  Failed: {Colors.RED}{self.failed}{Colors.RESET}/{total}")
        
        return self.failed == 0
    
    def test_root_endpoint(self):
        """Test root endpoint."""
        try:
            resp = requests.get(self.base_url, timeout=5)
            self.test("Root endpoint accessible", resp.status_code == 200)
        except requests.exceptions.ConnectionError:
            self.test("Root endpoint accessible", False, "Connection refused - is server running?")
            return False
        except Exception as e:
            self.test("Root endpoint accessible", False, str(e))
            return False
        return True
    
    def test_health_endpoint(self):
        """Test health check endpoint."""
        try:
            resp = requests.get(f"{self.api_url}/health", timeout=5)
            data = resp.json()
            self.test("Health endpoint returns 200", resp.status_code == 200)
            self.test("Health has status field", "status" in data)
            self.test("Health has vscode_connected field", "vscode_connected" in data)
            
            if data.get("vscode_connected"):
                print(f"         {Colors.GREEN}VS Code is connected!{Colors.RESET}")
            else:
                print(f"         {Colors.YELLOW}VS Code not connected (some tests may fail){Colors.RESET}")
                
        except Exception as e:
            self.test("Health endpoint", False, str(e))
    
    def test_list_extensions(self):
        """Test extensions list endpoint."""
        try:
            resp = requests.get(f"{self.api_url}/extensions", timeout=5)
            data = resp.json()
            self.test("Extensions endpoint returns 200", resp.status_code == 200)
            self.test("Extensions response has list", "extensions" in data)
            
            if data.get("extensions"):
                ext_names = [e["name"] for e in data["extensions"]]
                print(f"         Loaded extensions: {ext_names}")
                
        except Exception as e:
            self.test("Extensions endpoint", False, str(e))
    
    def test_register_extension(self):
        """Test registering an extension via YAML."""
        yaml_config = """
name: test_registered_ext
display_name: Test Registered Extension
version: "1.0"

selectors:
  activation:
    method: child_window
    criteria:
      title: "Test"
      control_type: "TabItem"
  input:
    method: child_window
    criteria:
      control_type: "Edit"

actions:
  test_action:
    steps:
      - type: wait
        duration: 0.05

workflows:
  test_workflow:
    parameters:
      - name: message
        required: true
    steps:
      - type: wait
        duration: 0.05
"""
        try:
            resp = requests.post(
                f"{self.api_url}/extensions/register",
                json={
                    "yaml_config": yaml_config,
                    "overwrite": True
                },
                timeout=10
            )
            data = resp.json()
            self.test("Register extension returns 200", resp.status_code == 200)
            self.test("Register extension succeeds", data.get("success") == True,
                     data.get("error", ""))
            self.test("Registered extension has correct name", 
                     data.get("name") == "test_registered_ext")
            self.test("Registered extension has selectors",
                     "activation" in data.get("selectors", []))
            self.test("Registered extension has actions",
                     "test_action" in data.get("actions", []))
            self.test("Registered extension has workflows",
                     "test_workflow" in data.get("workflows", []))
            
            if data.get("success"):
                print(f"         {Colors.GREEN}Extension 'test_registered_ext' registered!{Colors.RESET}")
                
        except Exception as e:
            self.test("Register extension", False, str(e))
    
    def test_register_extension_duplicate(self):
        """Test that duplicate registration fails without overwrite."""
        yaml_config = """
name: test_registered_ext
version: "1.0"
"""
        try:
            # First, ensure extension exists
            requests.post(
                f"{self.api_url}/extensions/register",
                json={"yaml_config": yaml_config, "overwrite": True},
                timeout=10
            )
            
            # Try to register again without overwrite
            resp = requests.post(
                f"{self.api_url}/extensions/register",
                json={"yaml_config": yaml_config, "overwrite": False},
                timeout=10
            )
            data = resp.json()
            self.test("Duplicate registration fails", data.get("success") == False)
            self.test("Error mentions already exists", 
                     "already exists" in data.get("error", "").lower())
                
        except Exception as e:
            self.test("Duplicate registration handling", False, str(e))
    
    def test_use_registered_extension(self):
        """Test using a registered extension through standard endpoints."""
        try:
            # Get extension info
            resp = requests.get(
                f"{self.api_url}/extensions/test_registered_ext",
                timeout=5
            )
            data = resp.json()
            self.test("Get registered extension info", resp.status_code == 200)
            self.test("Extension info has name", data.get("name") == "test_registered_ext")
            
            # Execute action on registered extension
            resp = requests.post(
                f"{self.api_url}/extensions/test_registered_ext/action",
                json={"action": "test_action", "params": {}},
                timeout=10
            )
            data = resp.json()
            self.test("Execute action on registered extension", 
                     data.get("success") == True, data.get("error", ""))
            
            # Execute workflow on registered extension
            resp = requests.post(
                f"{self.api_url}/extensions/test_registered_ext/workflow",
                json={"workflow": "test_workflow", "params": {"message": "test"}},
                timeout=10
            )
            data = resp.json()
            self.test("Execute workflow on registered extension",
                     data.get("success") == True, data.get("error", ""))
                
        except Exception as e:
            self.test("Use registered extension", False, str(e))
    
    def test_unregister_extension(self):
        """Test unregistering an extension."""
        try:
            # Unregister the test extension
            resp = requests.delete(
                f"{self.api_url}/extensions/test_registered_ext",
                timeout=10
            )
            data = resp.json()
            self.test("Unregister extension succeeds", data.get("success") == True,
                     data.get("error", ""))
            
            # Verify it's gone
            resp = requests.get(
                f"{self.api_url}/extensions/test_registered_ext",
                timeout=5
            )
            self.test("Unregistered extension returns 404", resp.status_code == 404)
            
            if data.get("success"):
                print(f"         {Colors.GREEN}Extension 'test_registered_ext' unregistered!{Colors.RESET}")
                
        except Exception as e:
            self.test("Unregister extension", False, str(e))
    
    def test_yaml_workflow(self):
        """Test YAML workflow execution."""
        yaml_config = """
name: test_workflow
version: "1.0"

selectors:
  dummy:
    method: child_window
    criteria:
      control_type: "Button"
      title: "NonexistentButton12345"

workflows:
  wait_only:
    description: "Just wait, no UI interaction"
    steps:
      - type: wait
        duration: 0.1
"""
        try:
            resp = requests.post(
                f"{self.api_url}/execute/yaml",
                json={
                    "yaml_config": yaml_config,
                    "workflow": "wait_only",
                    "params": {}
                },
                timeout=10
            )
            data = resp.json()
            self.test("YAML workflow endpoint returns 200", resp.status_code == 200)
            self.test("YAML workflow executes successfully", data.get("success") == True, 
                     data.get("error", ""))
                
        except Exception as e:
            self.test("YAML workflow execution", False, str(e))
    
    def test_yaml_with_params(self):
        """Test YAML workflow with parameters."""
        yaml_config = """
name: param_test
version: "1.0"

workflows:
  log_message:
    parameters:
      - name: message
        type: string
        required: true
      - name: count
        type: int
        default: 1
    steps:
      - type: wait
        duration: 0.05
"""
        try:
            resp = requests.post(
                f"{self.api_url}/execute/yaml",
                json={
                    "yaml_config": yaml_config,
                    "workflow": "log_message",
                    "params": {
                        "message": "Hello from test!",
                        "count": 3
                    }
                },
                timeout=10
            )
            data = resp.json()
            self.test("YAML with params returns 200", resp.status_code == 200)
            self.test("YAML with params succeeds", data.get("success") == True,
                     data.get("error", ""))
                
        except Exception as e:
            self.test("YAML with params", False, str(e))
    
    def test_yaml_invalid(self):
        """Test YAML error handling."""
        try:
            # Test invalid YAML syntax
            resp = requests.post(
                f"{self.api_url}/execute/yaml",
                json={
                    "yaml_config": "invalid: yaml: [syntax",
                    "workflow": "test",
                    "params": {}
                },
                timeout=10
            )
            data = resp.json()
            self.test("Invalid YAML returns error", data.get("success") == False)
            
            # Test missing workflow
            resp = requests.post(
                f"{self.api_url}/execute/yaml",
                json={
                    "yaml_config": "name: test\nversion: '1.0'",
                    "workflow": "nonexistent",
                    "params": {}
                },
                timeout=10
            )
            data = resp.json()
            self.test("Missing workflow returns error", data.get("success") == False)
                
        except Exception as e:
            self.test("YAML error handling", False, str(e))
    
    def test_steps_simple(self):
        """Test direct steps execution."""
        try:
            resp = requests.post(
                f"{self.api_url}/execute/steps",
                json={
                    "selectors": {},
                    "steps": [
                        {"type": "wait", "duration": 0.1}
                    ],
                    "params": {}
                },
                timeout=10
            )
            data = resp.json()
            self.test("Steps endpoint returns 200", resp.status_code == 200)
            self.test("Steps execution succeeds", data.get("success") == True,
                     data.get("error", ""))
                
        except Exception as e:
            self.test("Steps execution", False, str(e))
    
    def test_steps_with_params(self):
        """Test steps with parameter substitution."""
        try:
            resp = requests.post(
                f"{self.api_url}/execute/steps",
                json={
                    "selectors": {},
                    "steps": [
                        {"type": "wait", "duration": 0.05}
                    ],
                    "params": {"test_param": "test_value"}
                },
                timeout=10
            )
            data = resp.json()
            self.test("Steps with params returns 200", resp.status_code == 200)
            self.test("Steps with params succeeds", data.get("success") == True,
                     data.get("error", ""))
                
        except Exception as e:
            self.test("Steps with params", False, str(e))


def main():
    parser = argparse.ArgumentParser(description="Test the automation server API")
    parser.add_argument(
        "--base-url", 
        default="http://localhost:8000",
        help="Base URL of the automation server"
    )
    args = parser.parse_args()
    
    print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}  VS Code Extension Automation Server - API Tests{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*60}{Colors.RESET}")
    
    tester = APITester(args.base_url)
    success = tester.run_all_tests()
    
    print()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
