# VS Code Extension Automation Server

A config-driven server for automating VS Code extensions using pywinauto.

## Features

- **Config-driven**: Define extension controls in YAML files
- **RESTful API**: Control extensions via HTTP endpoints
- **Reusable**: Add new extensions by creating config files
- **Flexible**: Supports actions, workflows, and state queries

## Quick Start

### 1. Install Dependencies

```bash
cd automation_server
pip install -r requirements.txt
```

### 2. Configure Extensions

Create YAML config files in the `extensions/` directory. See `extensions/cline.yaml` for an example.

### 3. Run the Server

```bash
# Run as module
python -m automation_server

# Or with options
python -m automation_server --host 0.0.0.0 --port 8000 --extensions-dir extensions
```

### 4. Access the API

- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/api/v1/health

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Health check |
| `/api/v1/extensions` | GET | List registered extensions |
| `/api/v1/extensions/register` | POST | Register extension from YAML |
| `/api/v1/extensions/{name}` | GET | Get extension info |
| `/api/v1/extensions/{name}` | DELETE | Unregister extension |
| `/api/v1/extensions/{name}/activate` | POST | Open extension pane |
| `/api/v1/extensions/{name}/input` | POST | Send text input |
| `/api/v1/extensions/{name}/action` | POST | Execute named action |
| `/api/v1/extensions/{name}/workflow` | POST | Execute workflow |
| `/api/v1/extensions/{name}/state` | GET | Get UI state |
| `/api/v1/extensions/{name}/history` | GET | Get conversation history |
| `/api/v1/execute/yaml` | POST | Execute inline YAML workflow |
| `/api/v1/execute/steps` | POST | Execute inline steps |

## Example Usage

### Python Client

```python
import requests

BASE_URL = "http://localhost:8000/api/v1"

# ============ Dynamic Extension Registration ============
# Register an extension from YAML (can be done from client)
yaml_config = """
name: my_cline
display_name: Cline AI
version: "1.0"

selectors:
  activation:
    method: child_window
    criteria:
      title: "Cline"
      control_type: "TabItem"
  input:
    method: child_window
    criteria:
      control_type: "Edit"
  send_button:
    method: child_window
    criteria:
      title: "Send"
      control_type: "Button"

actions:
  click_send:
    steps:
      - type: click
        target: send_button

workflows:
  send_message:
    parameters:
      - name: message
        required: true
    steps:
      - type: input
        target: input
        value: "{{message}}"
      - type: click
        target: send_button
      - type: wait
        duration: 1
"""

# Register the extension
resp = requests.post(f"{BASE_URL}/extensions/register", json={
    "yaml_config": yaml_config,
    "overwrite": True  # Replace if already exists
})
print(resp.json())
# {"success": true, "name": "my_cline", "message": "Extension 'my_cline' registered successfully", ...}

# ============ Use Registered Extension ============
# Now use standard endpoints with your registered extension

# Activate extension
requests.post(f"{BASE_URL}/extensions/my_cline/activate")

# Send a message
requests.post(f"{BASE_URL}/extensions/my_cline/input", json={
    "text": "Create a hello world script",
    "submit": True
})

# Execute workflow with parameters
requests.post(f"{BASE_URL}/extensions/my_cline/workflow", json={
    "workflow": "send_message",
    "params": {"message": "Fix the bug in main.py"}
})

# Get state
state = requests.get(f"{BASE_URL}/extensions/my_cline/state").json()
print(state)

# Unregister when done
requests.delete(f"{BASE_URL}/extensions/my_cline")
```

### cURL

```bash
# Health check
curl http://localhost:8000/api/v1/health

# List extensions
curl http://localhost:8000/api/v1/extensions

# Activate Cline
curl -X POST http://localhost:8000/api/v1/extensions/cline/activate

# Send input
curl -X POST http://localhost:8000/api/v1/extensions/cline/input \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello Cline!", "submit": true}'

# Execute action
curl -X POST http://localhost:8000/api/v1/extensions/cline/action \
  -H "Content-Type: application/json" \
  -d '{"action": "accept_suggestion"}'
```

## Extension Configuration

### Selectors

Define UI elements using pywinauto criteria:

```yaml
selectors:
  activation:
    method: child_window
    criteria:
      title: "Cline"
      control_type: "TabItem"
    wait_timeout: 10
```

### Actions

Simple named operations:

```yaml
actions:
  accept_suggestion:
    description: "Accept the AI suggestion"
    steps:
      - type: click
        target: accept_button
```

### Workflows

Multi-step operations with parameters:

```yaml
workflows:
  send_message:
    parameters:
      - name: message
        type: string
        required: true
    steps:
      - type: activate
      - type: input
        target: input
        value: "{{message}}"
      - type: click
        target: send_button
```

### State Queries

Query UI state:

```yaml
state:
  is_active:
    method: is_visible
    target: pane
  message_count:
    method: count_children
    target: history_container
```

## Finding Control Identifiers

Use pywinauto to discover UI elements:

```python
from pywinauto import Application

app = Application(backend="uia").connect(path="Code.exe")
app.top_window().print_control_identifiers(depth=5)
```

Or use the debug endpoint:

```bash
curl http://localhost:8000/api/v1/debug/identifiers?depth=3
```

## Project Structure

```
automation_server/
├── __init__.py
├── __main__.py
├── server.py              # FastAPI application
├── server_config.yaml     # Server configuration
├── requirements.txt
├── config/
│   ├── __init__.py
│   ├── schema.py          # Pydantic models
│   └── loader.py          # YAML loader
├── core/
│   ├── __init__.py
│   ├── controller.py      # pywinauto wrapper
│   ├── selector.py        # Element resolver
│   └── executor.py        # Action executor
├── api/
│   ├── __init__.py
│   ├── models.py          # Request/Response models
│   └── routes.py          # API endpoints
└── extensions/
    └── cline.yaml         # Cline extension config
```

## Adding New Extensions

1. Create `extensions/your_extension.yaml`
2. Define selectors for UI elements
3. Define actions and workflows
4. Restart server or call `/api/v1/extensions/{name}/reload`

## Tips

1. **Finding Selectors**: Use `print_control_identifiers()` to discover UI elements
2. **Webviews**: Web-based extension UIs may have limited automation support
3. **Timing**: Adjust wait times based on your system performance
4. **Debugging**: Check server logs and use debug endpoints

## License

MIT
