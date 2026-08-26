import asyncio
import websockets
import requests
import json
import base64
import os
import time

# --- Configuration ---
SERVER_URL = "http://localhost:8083"  # Adjust if your port is different
API_ENDPOINT = f"{SERVER_URL}/api/v1/coding-agent/tasks"
SINGLE_SAMPLE_ENDPOINT = f"{SERVER_URL}/api/v1/coding-agent/tasks/single-sample"
WS_ENDPOINT = f"ws://localhost:8083/ws"

# --- Task Parameters ---
# These match the form fields in your FastAPI endpoint
PAYLOAD = {
    "software": "cline",
    "llm_name": "gpt-4o-mini",
    # "dataset_name": "mydataset_binary_classification",
    # "dataset_name": "swebench",
    "dataset_name": "redcode",
    # "attack_method_name": "input_aishelljack+workspace_aishelljack",
    "attack_method_name": "",
    "mcp_server_config": "",
    "use_proxy": "true",
    "user": "zfk",
    "skip_completed": True
}

def start_task():
    """Sends the POST request to start the Docker container and Agent."""
    print(f"🚀 Sending request to {API_ENDPOINT}...")
    try:
        response = requests.post(API_ENDPOINT, data=PAYLOAD)
        response.raise_for_status()
        resp_json = response.json()
        
        if resp_json['code'] == 0:
            task_id = resp_json['data']['task_id']
            print(f"✅ Task started successfully! Task ID: {task_id}")
            return task_id
        else:
            print(f"❌ Error starting task: {resp_json['message']}")
            return None
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return None

def start_single_sample(sample_config):
    """Sends POST request to run a single sample."""
    print(f"🚀 Sending single sample request to {SINGLE_SAMPLE_ENDPOINT}...")
    try:
        response = requests.post(
            SINGLE_SAMPLE_ENDPOINT,
            json=sample_config,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        resp_json = response.json()
        
        if resp_json['code'] == 0:
            task_id = resp_json['data']['task_id']
            sample_id = resp_json['data']['sample_id']
            print(f"✅ Single sample task started successfully!")
            print(f"   Task ID: {task_id}")
            print(f"   Sample ID: {sample_id}")
            return task_id
        else:
            print(f"❌ Error starting task: {resp_json['message']}")
            return None
    except Exception as e:
        print(f"❌ Request failed: {e}")
        import traceback
        traceback.print_exc()
        return None

def get_report(task_id):
    print(f"Sending request to get task report for task ID: {task_id}")
    try:
        response = requests.get(f"{API_ENDPOINT}/{task_id}/report")
        response.raise_for_status()
        resp_json = response.json()
        with open(f"logs/report_{task_id}.json", "w") as f:
            json.dump(resp_json, f, indent=2)
    except Exception as e:
        print(f"❌ Error getting task report: {e}")

def save_image(data_url, path):
    """Decodes base64 data URL and saves it to a file."""
    try:
        # data_url format: "data:image/png;base64,iVBOR..."
        header, encoded = data_url.split(",", 1)
        data = base64.b64decode(encoded)
        with open(os.path.join(path, "latest_frame.png"), "wb") as f:
            f.write(data)
    except Exception as e:
        print(f"Error saving image: {e}")

async def listen_ws(task_id):
    """Connects to WebSocket and listens for frames and results."""
    uri = f"{WS_ENDPOINT}/{task_id}"
    print(f"🔗 Connecting to WebSocket: {uri}")
    
    async with websockets.connect(uri) as websocket:
        print("✅ Connected! Waiting for updates...")
        os.makedirs(f"exp/{task_id}", exist_ok=True)
        
        # Open a log file for this task
        log_file = open(f"exp/{task_id}/task.log", "w")
        
        id = 0
        while True:
            try:
                message = await websocket.recv()
                data = json.loads(message)
                
                # 1. Handle Task Completion/Termination
                if data.get("code") == 1002:
                    print(f"\n🏁 Task Finished: {data['message']}")
                    break
                
                payload = data.get("data", {})
                
                # 2. Handle Screenshot Frame
                if "frame" in payload:
                    # Save image so you can view it locally
                    save_image(payload["frame"], f"exp/{task_id}")
                    # Print a progress dot to keep console clean
                    print(".", end="", flush=True)
                
                # 3. Handle Log Message
                elif "log" in payload:
                    log_message = payload["log"]
                    print(f"\n[LOG] {log_message}", flush=True)
                
                # 4. Handle Red Team Result
                elif "result" in payload:
                    print("\n\n🎯 RESULT RECEIVED:")
                    print(json.dumps(payload["result"], indent=2))
                    
                    # Optionally save result to disk
                    with open(f"exp/{task_id}/result_{task_id}_{id}.json", "w") as f:
                        json.dump(payload["result"], f, indent=2)
                    id += 1
                    print(f"📄 Result saved to result_{task_id}.json")
                
                # 4. Handle Log Messages
                elif "log" in payload:
                    log_entry = payload["log"]
                    # Write to log file
                    log_file.write(f"{log_entry['message']}\n")
                    log_file.flush()
                    
                    # Optionally print to console (can be commented out for cleaner output)
                    # print(f"[{log_entry['level']}] {log_entry['message']}")

            except websockets.exceptions.ConnectionClosed:
                print("\n🔌 Connection closed by server.")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                break
        
        log_file.close()

if __name__ == "__main__":
    # 1. Start the task via REST API
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", action="store_true", help="Start a new task")
    parser.add_argument("--single-sample", action="store_true", help="Run a single sample")
    parser.add_argument("--task_id", help="Connect to an existing task ID")
    parser.add_argument("--dataset_name", help="Specify the dataset name", default="redcode")
    parser.add_argument("--software", help="Specify the software name", default="copilot")
    parser.add_argument("--attack_method_name", help="Specify the attack method name", default="input_aishelljack+workspace_aishelljack")
    parser.add_argument("--model", help="Specify the model_name", default="deepseek-v3.2")
    parser.add_argument("--user", help="Specify the user name", default="default")
    parser.add_argument("--force-redo", action="store_true", help="Skip completed experiments")
    
    # Single sample specific arguments
    parser.add_argument("--sample-id", help="Sample ID for single sample mode", default="test-001")
    parser.add_argument("--input", help="Input prompt for single sample", default="Create a Python script that prints 'Hello, World!'")
    parser.add_argument("--target", help="Target output for single sample", default=None)
    parser.add_argument("--prep-script", help="Container preparation script", default=None)
    
    args = parser.parse_args()
    
    PAYLOAD['dataset_name'] = args.dataset_name
    PAYLOAD['attack_method_name'] = args.attack_method_name
    PAYLOAD['software'] = args.software
    PAYLOAD['llm_name'] = args.model
    PAYLOAD['user'] = args.user
    PAYLOAD['skip_completed'] = not args.force_redo
    
    if args.single_sample:
        # Build single sample configuration
        sample_config = {
            "sample": {
                "id": args.sample_id,
                "input": args.input,
                "target": args.target,
                "metadata": {
                    "test_type": "manual",
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
                },
            },
            "software": args.software,
            "llm_name": args.model,
            "file_attacks": [],
            "use_proxy": PAYLOAD['use_proxy'] == "true",
            "mcp_server_config": None,
            "container_preparation_script": args.prep_script
        }
        
        print("\n📋 Single Sample Configuration:")
        print(json.dumps(sample_config, indent=2))
        print()
        
        t_id = start_single_sample(sample_config)
    elif args.start:
        t_id = start_task()
    elif args.task_id:
        t_id = args.task_id
    else:
        print("Either --start, --single-sample, or --task_id must be specified")
        exit(1)
    
    # 2. If successful, listen via WebSocket
    if t_id:
        try:
            asyncio.run(listen_ws(t_id))
            get_report(t_id)
        except KeyboardInterrupt:
            print("\nStopped by user.")