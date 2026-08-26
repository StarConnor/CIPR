"""
Tests for the VS Code Extension Automation Server API.

These tests verify the API endpoints work correctly.
Run with: pytest tests/test_api.py -v

For integration tests with actual VS Code, ensure VS Code is running.
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient

# Mock pywinauto before importing the server modules
import sys
sys.modules['pywinauto'] = MagicMock()
sys.modules['pywinauto.findwindows'] = MagicMock()
sys.modules['pywinauto.timings'] = MagicMock()
sys.modules['pywinauto.keyboard'] = MagicMock()

from automation_server.server import create_app
from automation_server.config import ExtensionConfig, config_loader
from automation_server.api.models import (
    DynamicWorkflowRequest, DynamicStepsRequest,
    InputRequest, ActionRequest, WorkflowRequest,
)


@pytest.fixture
def mock_controller():
    """Create a mock VS Code controller."""
    controller = MagicMock()
    controller.ensure_connected.return_value = True
    controller.is_visible.return_value = True
    controller.is_enabled.return_value = True
    controller.exists.return_value = True
    controller.get_text.return_value = "Test text"
    controller.count_children.return_value = 5
    controller.find_element.return_value = MagicMock()
    controller.find_elements.return_value = [MagicMock(), MagicMock()]
    return controller


@pytest.fixture
def sample_extension_config():
    """Create a sample extension config for testing."""
    return ExtensionConfig(
        name="test_extension",
        display_name="Test Extension",
        version="1.0",
        selectors={
            "activation": {
                "method": "child_window",
                "criteria": {"title": "Test", "control_type": "TabItem"}
            },
            "input": {
                "method": "child_window", 
                "criteria": {"control_type": "Edit"}
            },
            "send_button": {
                "method": "child_window",
                "criteria": {"title": "Send", "control_type": "Button"}
            },
        },
        actions={
            "click_send": {
                "description": "Click the send button",
                "steps": [{"type": "click", "target": "send_button"}]
            }
        },
        workflows={
            "send_message": {
                "description": "Send a message",
                "parameters": [{"name": "message", "type": "string", "required": True}],
                "steps": [
                    {"type": "input", "target": "input", "value": "{{message}}"},
                    {"type": "click", "target": "send_button"}
                ]
            }
        },
        state={
            "is_active": {"method": "is_visible", "target": "activation"}
        }
    )


@pytest.fixture
def app(mock_controller, sample_extension_config):
    """Create test application with mocked dependencies."""
    with patch('automation_server.core.controller.get_controller', return_value=mock_controller):
        with patch.object(config_loader, 'list_extensions', return_value={"test_extension": sample_extension_config}):
            with patch.object(config_loader, 'get_extension', return_value=sample_extension_config):
                app = create_app()
                yield app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for health check endpoint."""
    
    def test_health_check(self, client, mock_controller):
        """Test health endpoint returns correct status."""
        with patch('automation_server.api.routes.get_controller', return_value=mock_controller):
            response = client.get("/api/v1/health")
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert "vscode_connected" in data
            assert "extensions_loaded" in data


class TestExtensionsEndpoint:
    """Tests for extensions discovery endpoints."""
    
    def test_list_extensions(self, client, sample_extension_config):
        """Test listing registered extensions."""
        with patch.object(config_loader, 'list_extensions', return_value={"test_extension": sample_extension_config}):
            response = client.get("/api/v1/extensions")
            assert response.status_code == 200
            data = response.json()
            assert "extensions" in data
    
    def test_get_extension_info(self, client, sample_extension_config):
        """Test getting specific extension info."""
        with patch.object(config_loader, 'get_extension', return_value=sample_extension_config):
            response = client.get("/api/v1/extensions/test_extension")
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "test_extension"
            assert "selectors" in data
            assert "actions" in data
            assert "workflows" in data


class TestDynamicYamlEndpoint:
    """Tests for dynamic YAML execution endpoint."""
    
    def test_execute_yaml_workflow(self, client, mock_controller):
        """Test executing a workflow from inline YAML."""
        yaml_config = """
name: dynamic_test
version: "1.0"

selectors:
  test_button:
    method: child_window
    criteria:
      title: "Test Button"
      control_type: "Button"

workflows:
  click_button:
    steps:
      - type: click
        target: test_button
      - type: wait
        duration: 0.1
"""
        with patch('automation_server.api.routes.get_controller', return_value=mock_controller):
            response = client.post("/api/v1/execute/yaml", json={
                "yaml_config": yaml_config,
                "workflow": "click_button",
                "params": {}
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] == True
    
    def test_execute_yaml_action(self, client, mock_controller):
        """Test executing an action from inline YAML."""
        yaml_config = """
name: dynamic_action_test
version: "1.0"

selectors:
  my_element:
    method: child_window
    criteria:
      control_type: "Button"

actions:
  simple_click:
    steps:
      - type: click
        target: my_element
"""
        with patch('automation_server.api.routes.get_controller', return_value=mock_controller):
            response = client.post("/api/v1/execute/yaml", json={
                "yaml_config": yaml_config,
                "action": "simple_click",
                "params": {}
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] == True
    
    def test_execute_yaml_with_params(self, client, mock_controller):
        """Test executing YAML workflow with parameters."""
        yaml_config = """
name: param_test
version: "1.0"

selectors:
  input_field:
    method: child_window
    criteria:
      control_type: "Edit"

workflows:
  type_message:
    parameters:
      - name: message
        type: string
        required: true
    steps:
      - type: input
        target: input_field
        value: "{{message}}"
"""
        with patch('automation_server.api.routes.get_controller', return_value=mock_controller):
            response = client.post("/api/v1/execute/yaml", json={
                "yaml_config": yaml_config,
                "workflow": "type_message",
                "params": {"message": "Hello from test!"}
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] == True
    
    def test_execute_yaml_invalid_yaml(self, client, mock_controller):
        """Test that invalid YAML returns error."""
        with patch('automation_server.api.routes.get_controller', return_value=mock_controller):
            response = client.post("/api/v1/execute/yaml", json={
                "yaml_config": "invalid: yaml: content: [",
                "workflow": "test",
                "params": {}
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] == False
            assert "error" in data
    
    def test_execute_yaml_missing_workflow(self, client, mock_controller):
        """Test that missing workflow returns error."""
        yaml_config = """
name: test
version: "1.0"
selectors: {}
"""
        with patch('automation_server.api.routes.get_controller', return_value=mock_controller):
            response = client.post("/api/v1/execute/yaml", json={
                "yaml_config": yaml_config,
                "workflow": "nonexistent",
                "params": {}
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] == False
            assert "not found" in data["error"]


class TestDynamicStepsEndpoint:
    """Tests for dynamic steps execution endpoint."""
    
    def test_execute_steps_simple(self, client, mock_controller):
        """Test executing simple steps directly."""
        with patch('automation_server.api.routes.get_controller', return_value=mock_controller):
            response = client.post("/api/v1/execute/steps", json={
                "selectors": {
                    "my_button": {
                        "method": "child_window",
                        "criteria": {"control_type": "Button"}
                    }
                },
                "steps": [
                    {"type": "click", "target": "my_button"},
                    {"type": "wait", "duration": 0.1}
                ],
                "params": {}
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] == True
    
    def test_execute_steps_with_params(self, client, mock_controller):
        """Test executing steps with parameter substitution."""
        with patch('automation_server.api.routes.get_controller', return_value=mock_controller):
            response = client.post("/api/v1/execute/steps", json={
                "selectors": {
                    "text_field": {
                        "method": "child_window",
                        "criteria": {"control_type": "Edit"}
                    }
                },
                "steps": [
                    {"type": "input", "target": "text_field", "value": "{{my_text}}"}
                ],
                "params": {"my_text": "Dynamic text input!"}
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] == True


class TestActionEndpoint:
    """Tests for action execution endpoint."""
    
    def test_execute_action(self, client, mock_controller, sample_extension_config):
        """Test executing a named action."""
        with patch('automation_server.api.routes.get_controller', return_value=mock_controller):
            with patch.object(config_loader, 'get_extension', return_value=sample_extension_config):
                response = client.post("/api/v1/extensions/test_extension/action", json={
                    "action": "click_send",
                    "params": {}
                })
                
                assert response.status_code == 200
                data = response.json()
                assert "success" in data


class TestWorkflowEndpoint:
    """Tests for workflow execution endpoint."""
    
    def test_execute_workflow(self, client, mock_controller, sample_extension_config):
        """Test executing a workflow."""
        with patch('automation_server.api.routes.get_controller', return_value=mock_controller):
            with patch.object(config_loader, 'get_extension', return_value=sample_extension_config):
                response = client.post("/api/v1/extensions/test_extension/workflow", json={
                    "workflow": "send_message",
                    "params": {"message": "Test message"}
                })
                
                assert response.status_code == 200
                data = response.json()
                assert "success" in data


class TestInputEndpoint:
    """Tests for input endpoint."""
    
    def test_send_input(self, client, mock_controller, sample_extension_config):
        """Test sending input to extension."""
        with patch('automation_server.api.routes.get_controller', return_value=mock_controller):
            with patch.object(config_loader, 'get_extension', return_value=sample_extension_config):
                response = client.post("/api/v1/extensions/test_extension/input", json={
                    "text": "Hello world",
                    "submit": False,
                    "clear_first": True
                })
                
                assert response.status_code == 200
                data = response.json()
                assert "success" in data


# ============ Integration Test Examples ============

class TestIntegration:
    """
    Integration tests that require actual VS Code running.
    
    These are marked with pytest.mark.integration and skipped by default.
    Run with: pytest tests/test_api.py -v -m integration
    """
    
    @pytest.mark.integration
    @pytest.mark.skip(reason="Requires VS Code to be running")
    def test_real_vscode_connection(self):
        """Test real connection to VS Code."""
        import requests
        response = requests.get("http://localhost:8000/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["vscode_connected"] == True
    
    @pytest.mark.integration
    @pytest.mark.skip(reason="Requires VS Code to be running")
    def test_real_dynamic_yaml_execution(self):
        """Test real YAML execution against VS Code."""
        import requests
        
        yaml_config = """
name: integration_test
version: "1.0"

selectors:
  sidebar:
    method: child_window
    criteria:
      control_type: "TabItem"
      title: "Explorer"

workflows:
  check_explorer:
    steps:
      - type: wait
        duration: 0.5
"""
        response = requests.post(
            "http://localhost:8000/api/v1/execute/yaml",
            json={
                "yaml_config": yaml_config,
                "workflow": "check_explorer",
                "params": {}
            }
        )
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
