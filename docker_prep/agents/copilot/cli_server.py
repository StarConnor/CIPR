import os
# app.py (inside your container)
from flask import Flask, request, jsonify
import subprocess
import logging
import json

app = Flask(__name__)

# Assume 'claude-code' is the command for your CLI tool
CLI_COMMAND = ["copilot", "--allow-all-tools"]
copilot_result_path = "/home/devuser/.copilot/session-state"
supported_models = ["claude-sonnet-4.5", "claude-haiku-4.5", "claude-opus-4.5", "claude-sonnet-4", "gpt-5.1-codex-max", "gpt-5.1-codex", "gpt-5", "gpt-5-mini", "gpt-4.1", "gemini-3-pro-preview"]
chat_history = "error"
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_cli_command(command_args):
    global chat_history
    try:
        process = subprocess.Popen(
            command_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1 # Line buffered
        )

        stdout, stderr = process.communicate() # Wait for process to finish

        if process.returncode != 0:
            return False, f"CLI Error: {stderr}"

        return True, None
    except Exception as e:
        return False, f"Execution Error: {str(e)}"

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    prompt = data.get('prompt')
    model = data.get('model', '')
    model_command = []
    if model:
        if model in supported_models:
            
            model_command = ["--model", model] 
        else:
            logger.warning(f"Model {model} is not supported. Supported models: {supported_models}")
    logger.info(f"Set model to: {model if model else 'gpt-5-mini'}")
    if not prompt:
        return jsonify({"error": "Prompt is required"}), 400
    logger.info(f"Prompt: {prompt}")

    run_success, error = run_cli_command(CLI_COMMAND + model_command + ['-p', prompt]) # Pass prompt as an argument

    if error:
        logger.error(f"Error running CLI command: {error}")
        return jsonify({"error": error}), 500
    else:
        task_dir = os.listdir(copilot_result_path)
        if task_dir:
            try:
                task_id = task_dir[-1]
                with open(os.path.join(copilot_result_path, task_id), "r") as f:
                    chat_history = f.read()
            except Exception as e:
                logger.error(f"Error reading chat history: {str(e)}")
                chat_history = "Error reading chat history."
        else:
            logger.warning("No tasks found in the tasks directory.")
            chat_history = "No tasks found."
        return jsonify({
            "response": run_success,
            "chat_history": chat_history
        })

@app.route('/upload', methods=['POST'])
def save_string():
    """Save a string to a specified file path"""
    try:
        data = request.get_json()
        content = data.get('content', '')
        filepath = data.get('filepath', '')
        
        if not filepath:
            logger.warning("No filepath provided in save-string request")
            return jsonify({"error": "filepath is required"}), 400
        
        if not content and 'content' not in data:
            logger.warning("No content provided in save-string request")
            return jsonify({"error": "content is required"}), 400
        
        # Create parent directories if they don't exist
        parent_dir = os.path.dirname(filepath)
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
        
        # Write content to file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"String saved successfully to: {filepath}")
        return jsonify({
            "message": "String saved successfully",
            "filepath": filepath,
            "size": len(content)
        }), 200
        
    except Exception as e:
        logger.error(f"Error saving string: {str(e)}")
        return jsonify({"error": f"Save failed: {str(e)}"}), 500
@app.route('/reset', methods=['POST'])
def reset():
    global chat_history
    chat_history = ""
    return jsonify({"message": "Chat history reset"})

@app.route('/status', methods=['GET'])
def status():
    return jsonify({"status": "running", "chat_history_size": len(chat_history)})

if __name__ == '__main__':
    # Host 0.0.0.0 makes it accessible from outside the container
    # Port 5001 is a common choice for Flask
    app.run(host='0.0.0.0', port=5001)