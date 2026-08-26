import sys
import asyncio
import websockets
import requests
import json
import base64
import os
import argparse
import yaml
import traceback
from typing import List, Dict, Any
import cv2
import numpy as np
from datetime import datetime

def load_config(config_path):
    """Loads YAML config."""
    if config_path.endswith(".yaml") or config_path.endswith(".yml"):
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    elif config_path.endswith(".json"):
        with open(config_path, 'r') as f:
            return json.load(f)

def cancel_task(api_endpoint, task_id):
    """Sends a cancellation request to the server."""
    print(f"\n📡 Sending cancel request to server for Task ID: {task_id}...")
    try:
        cancel_url = f"{api_endpoint}/{task_id}/cancel"
        response = requests.post(cancel_url)
        if response.status_code == 200:
            print("✅ Server confirmed cancellation.")
        else:
            print(f"⚠️ Server returned {response.status_code}: {response.text}")
    except Exception as e:
        print(f"❌ Failed to send cancel request: {e}")

def start_task(url, payload):
    """Starts a task and returns response data, including task_id."""
    print(f"🚀 Sending Single Sample to {url}...")
    if "concurrency" not in payload:
        payload["concurrency"] = 1
        
    print(f"   Mode: {payload.get('agent', {}).get('software')}, Parallelism: {payload['concurrency']}")
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        resp_json = response.json()
        
        if resp_json['code'] == 0:
            data = resp_json['data']
            task_id = data['task_id']
            vm_info = data.get('vm_info', {})
            if vm_info:
                print(f"🖥️ VM Info: IP={vm_info.get('ip')}, SSH Port={vm_info.get('ssh_port')}, VNC Port={vm_info.get('vnc_port')}")
            completed_count = data.get('completed_results_count')
            completed_endpoint = data.get('completed_results_endpoint')
            if completed_count is not None:
                print(f"⏭️  Completed results available on demand: {completed_count}")
                if completed_endpoint:
                    print(f"   Endpoint: {completed_endpoint}")
            print(f"✅ Task started! ID: {task_id}")
            return data
        else:
            print(f"❌ Server Error: {resp_json['message']}")
            return None
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return None

def fetch_completed_results(api_endpoint, task_id, task_dir, include_result=False):
    """Fetch skipped historical results on demand; not called by default."""
    print(f"📥 Fetching completed/skipped results for {task_id}...")
    try:
        url = f"{api_endpoint}/{task_id}/completed-results"
        response = requests.get(url, params={"include_result": str(include_result).lower()})
        response.raise_for_status()
        resp_json = response.json()
        os.makedirs(task_dir, exist_ok=True)
        out_path = os.path.join(task_dir, f"completed_results_{task_id}.json")
        with open(out_path, "w") as f:
            json.dump(resp_json, f, indent=2)
        total = (resp_json.get("data") or {}).get("total")
        print(f"📄 Completed results saved to {out_path} (total={total})")
    except Exception as e:
        print(f"❌ Error fetching completed results: {e}")

def save_image(data_url, path, filename):
    """Saves base64 image data to a specific filename."""
    try:
        if "," in data_url:
            header, encoded = data_url.split(",", 1)
        else:
            encoded = data_url
            
        data = base64.b64decode(encoded)
        with open(os.path.join(path, filename), "wb") as f:
            f.write(data)
    except Exception as e:
        print(f"Error saving image {filename}: {e}")

def get_report(api_endpoint, task_id):
    print(f"📥 Fetching report for {task_id}...")
    try:
        response = requests.get(f"{api_endpoint}/{task_id}/report")
        response.raise_for_status()
        resp_json = response.json()
        with open(f"exp/{task_id}/report_{task_id}.json", "w") as f:
            json.dump(resp_json, f, indent=2)
        print(f"📄 Report saved to exp/{task_id}/report_{task_id}.json")
    except Exception as e:
        print(f"❌ Error getting report: {e}")

async def listen_ws(ws_endpoint, task_id, task_name, mode="w", task_mode="dataset", receiv_frame=True):
    uri = f"{ws_endpoint}/{task_id}"
    print(f"🔗 Connecting to WebSocket: {uri}")
    
    # Dictionary to keep track of open log file handles per sample
    # Key: sample_id, Value: file_handle
    log_handles = {}
    
    # Dictionary to track last access time for each log file
    # Key: sample_id, Value: timestamp
    log_access_times = {}
    
    # Timeout in seconds - close log handles after this period of inactivity
    LOG_HANDLE_TIMEOUT = 300
    
    # Dictionary to keep track of video writers per sample
    # Key: sample_id, Value: cv2.VideoWriter object
    video_writers = {}
    
    # Dictionary to track frame dimensions per sample
    # Key: sample_id, Value: (width, height)
    frame_dimensions = {}
    
    task_dir = f"exp/{task_mode}/{task_name}"
    os.makedirs(task_dir, exist_ok=True)
    
    summary = {"total": 0, "attack_success": 0, "task_success": 0, "alert_success": 0}
    processed_samples = set()  # Track which samples we've already counted
    
    def cleanup_stale_log_handles():
        """Close log file handles that haven't been accessed recently."""
        current_time = datetime.now().timestamp()
        stale_samples = []
        
        for sample_id, last_access in log_access_times.items():
            if current_time - last_access > LOG_HANDLE_TIMEOUT:
                stale_samples.append(sample_id)
        
        for sample_id in stale_samples:
            if sample_id in log_handles:
                try:
                    log_handles[sample_id].close()
                    del log_handles[sample_id]
                    del log_access_times[sample_id]
                except:
                    pass

    async with websockets.connect(
        uri, 
        open_timeout=120, 
        max_size=50*1024*1024,  # Increased to 50MB to handle large results
        ping_interval=20,  # Send ping every 20 seconds
        ping_timeout=180   # Wait up to 3 minutes for pong (increased from 60)
    ) as websocket:
        print("✅ Connected! Monitoring...")
        
        try:
            while True:
                message = await websocket.recv()
                data = json.loads(message)
                
                # Handle ping/keepalive messages
                if data.get("code") == 1000:
                    continue
                
                if data.get("code") == 1002:
                    print(f"\n🏁 Task Finished: {data['message']}")
                    break
                
                payload = data.get("data", {})
                
                # Default to 'system' if no sample_id provided
                sample_id = payload.get("sample_id", "system")
                
                # --- Handle Frames ---
                if "frame" in payload and receiv_frame:
                    filename = f"frame_{sample_id}.png"
                    save_image(payload["frame"], task_dir, filename)
                    # Print a dot to indicate activity without spamming
                    print(".", end="", flush=True)
                    # Decode base64 frame to image
                    data_url = payload["frame"]
                    if "," in data_url:
                        header, encoded = data_url.split(",", 1)
                    else:
                        encoded = data_url
                    
                    try:
                        frame_data = base64.b64decode(encoded)
                        # Convert bytes to numpy array and decode as image
                        nparr = np.frombuffer(frame_data, np.uint8)
                        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                        
                        if frame is not None:
                            # Get frame dimensions
                            height, width = frame.shape[:2]
                            
                            # Initialize video writer for this sample if not exists
                            if sample_id not in video_writers:
                                safe_id = sample_id.replace("/", "_").replace("\\", "_")
                                video_path = f"{task_dir}/video_{safe_id}.avi"
                                
                                # Use MP4V codec, 30 fps
                                fourcc = cv2.VideoWriter_fourcc(*'XVID')
                                video_writers[sample_id] = cv2.VideoWriter(
                                    video_path, fourcc, 30, (width, height)
                                )
                                frame_dimensions[sample_id] = (width, height)
                            
                            # Write frame to video, resizing if necessary
                            current_dims = frame_dimensions[sample_id]
                            if (width, height) != current_dims:
                                frame = cv2.resize(frame, current_dims)
                            
                            video_writers[sample_id].write(frame)
                        
                        # Print a dot to indicate activity without spamming
                        print(".", end="", flush=True)
                    except Exception as e:
                        print(f"Error processing frame for {sample_id}: {e}")

                # --- Handle Logs ---
                elif "log" in payload:
                    log_entry = payload["log"]
                    msg = log_entry.get('message') if isinstance(log_entry, dict) else str(log_entry)
                    
                    # Sanitize sample_id for filename
                    if sample_id is None:
                        sample_id = "system"
                    safe_id = sample_id.replace("/", "_").replace("\\", "_")
                    
                    # Clean up stale handles periodically (every 100 log messages approximately)
                    if len(log_access_times) > 0 and len(log_access_times) % 100 == 0:
                        cleanup_stale_log_handles()
                    
                    # Open log file if not already open
                    if sample_id not in log_handles:
                        log_handles[sample_id] = open(f"{task_dir}/{safe_id}.log", "a", encoding="utf-8")
                    
                    # Write to log file and flush
                    log_handles[sample_id].write(f"{msg}\n")
                    log_handles[sample_id].flush()
                    
                    # Update last access time
                    log_access_times[sample_id] = datetime.now().timestamp()

                # --- Handle Results ---
                elif "result" in payload:
                    result = payload["result"]
                    
                    # Save individual result file using sample_id
                    safe_id = sample_id.replace("/", "_").replace("\\", "_")
                    with open(f"{task_dir}/result_{safe_id}.json", "w") as f:
                        json.dump(result, f, indent=2)
                    
                    # Update summary (count each unique sample_id once)
                    is_new_sample = sample_id not in processed_samples
                    if is_new_sample:
                        processed_samples.add(sample_id)
                        summary["total"] += 1
                        print(f"\n🎯 RESULT #{summary['total']} for {sample_id}")
                        
                        # Count success metrics only for new samples
                        if result.get("attack_success") == "success":
                            summary["attack_success"] += 1
                        if "task_success" in result or "run_success" in result:
                            if result.get("task_success") == "success":
                                summary["task_success"] += 1
                            elif result.get("run_success") == "success":
                                summary["task_success"] += 1
                        if "alert_success" in result:
                            if result.get("alert_success") == "success":
                                summary["alert_success"] += 1
                    else:
                        print(f"\n⚠️  DUPLICATE result for {sample_id} (not counting again)")
                    
                    # Close the log handle for this sample since it's done
                    if sample_id in log_handles:
                        try:
                            log_handles[sample_id].close()
                            del log_handles[sample_id]
                            if sample_id in log_access_times:
                                del log_access_times[sample_id]
                        except:
                            pass
                    
                    # Release the video writer for this sample
                    if sample_id in video_writers:
                        video_writers[sample_id].release()
                        del video_writers[sample_id]
                        if sample_id in frame_dimensions:
                            del frame_dimensions[sample_id]
            
        except websockets.exceptions.ConnectionClosed as e:
            print(f"\n🔌 Connection closed. {e}")
            print(f"⚠️ Progress before interruption: {len(processed_samples)} samples processed, handing off to script for restart...")
            sys.exit(1)
        except Exception as e:
            traceback.print_exception(e)
            print(f"\n❌ WS Error: {e}")
            sys.exit(1)
        finally:
            # Cleanup: Close all remaining log files
            for handle in log_handles.values():
                try:
                    handle.close()
                except:
                    pass
            
            # Cleanup: Release all remaining video writers
            for writer in video_writers.values():
                try:
                    writer.release()
                except:
                    pass
                    
        return summary, processed_samples

def resolve_task_suffix_number(task_name: str, mode: str = "single_sample"):
    """Resolves and returns the next available suffix number for a given task name."""
    base_name = task_name
    suffix_number = 1

    # Check existing directories to find the next available suffix
    while True:
        dir_name = os.path.join("exp", mode, f"{base_name}-{suffix_number}")
        if not os.path.exists(dir_name):
            return suffix_number
        suffix_number += 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", help="Path to YAML config file", default="job_config.yaml")
    parser.add_argument("--task_id", help="Attach to existing task ID")
    parser.add_argument("--model", default="gemini-3-flash", help="set model")
    parser.add_argument("--agent", default="cc_cli", help="set model")
    parser.add_argument("--concurrency", default=1, help="set model")
    parser.add_argument("--k_runs", default=1, help="set model")
    parser.add_argument("--dataset", default="ipi_file_dataset_lite", help="set model")
    parser.add_argument("--defense", action="store_true", help="enable defense configurations in exp config")
    parser.add_argument("--server", default="http://127.0.0.1:8083", help="set server url, e.g. http://localhost:8083")
    parser.add_argument("--fetch-completed-results", action="store_true", help="Fetch skipped historical results via endpoint after task starts")
    parser.add_argument("--fetch-completed-results-full", action="store_true", help="Fetch full skipped historical result payloads; can be large")
    args = parser.parse_args()

    if not os.path.exists(args.config):
        print(f"❌ Config file not found: {args.config}")
        exit(1)
        
    cfg = load_config(args.config)
    
    if args.server:
        cfg["server_url"] = args.server
    server_url = cfg.get("server_url", "http://localhost:8083")
    api_endpoint = f"{server_url}/api/v1/coding-agent/tasks"
    ws_endpoint = f"ws://{server_url.split('://')[1]}/ws"

    t_id = None
    task_start_data = None

    if args.task_id:
        t_id = args.task_id
    else:
        mode = cfg.get("mode", "dataset")
        if mode == "dataset":
            cfg['concurrency'] = args.concurrency
            cfg['dataset_name'] = args.dataset
            if args.k_runs:
                cfg['k_runs'] = args.k_runs
        if not args.defense:
            cfg['defense']['enabled'] = False
        agent_config = cfg.get("agent", {})
        agent_config['software'] = args.agent
        agent_config['model']['model_name'] = args.model
        
        # Ensure concurrency is passed if set in config
        if 'concurrency' not in cfg:
            cfg['concurrency'] = 1 # Default

        if mode == "single_sample":
            task_start_data = start_task(f"{api_endpoint}/single-sample", cfg)
        else:
            task_start_data = start_task(api_endpoint, cfg)
        t_id = task_start_data.get("task_id") if task_start_data else None

    if t_id:
        start_time = datetime.now()
        print(f"Start exp at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        software_name = cfg.get('agent', {}).get('software', 'agent')
        model_name = cfg.get('agent', {}).get('model', {}).get('model_name', 'model')
        if cfg.get("mode") == "single_sample":
            task_name = f"{software_name}/{cfg.get('sample', {}).get('id', 'sample')}/{model_name}"
        else:
            dataset_name = cfg.get('dataset_name', 'dataset')
            task_name = f"{software_name}/{dataset_name}/{model_name}"
        task_name_suffix = resolve_task_suffix_number(task_name, mode=cfg.get("mode", "dataset"))
        task_name = f"{task_name}-{task_name_suffix}"
        task_dir = f"exp/{cfg.get('mode', 'dataset')}/{task_name}"
        if args.fetch_completed_results and task_start_data and task_start_data.get("completed_results_count", 0):
            fetch_completed_results(api_endpoint, t_id, task_dir, include_result=args.fetch_completed_results_full)
        try:
            summary, processed_samples = asyncio.run(listen_ws(ws_endpoint, t_id, task_name, mode="w", task_mode=cfg.get("mode", "dataset")))
            # with open(f"../data/{args.dataset}/dataset.json", "r") as f:
            #     dataset = json.load(f)
            # dataset_ids = set(sample['id'] for sample in dataset)
            # missing_samples = dataset_ids - processed_samples
            # if missing_samples and cfg['mode'] == "dataset":
            #     print(f"\n⚠️  Missing results for samples: {', '.join(missing_samples)}")
            get_report(api_endpoint, t_id)
            if summary and summary.get("total", 0) > 0:
                total = summary["total"]
                asr = summary["attack_success"] / total * 100
                task_sr = summary["task_success"] / total * 100
                alert_sr = summary["alert_success"] / total * 100

                print("\n📊 Final Summary:")
                print(f"- Total samples: {total}")
                print(f"- Attack Success Rate (ASR): {asr:.2f}% ({summary['attack_success']}/{total})")
                print(f"- Task Success Rate: {task_sr:.2f}% ({summary['task_success']}/{total})")
                print(f"- Alert Success Rate: {alert_sr:.2f}% ({summary['alert_success']}/{total})")
                print(f"Start at {start_time.strftime('%Y-%m-%d %H:%M:%S')}, End exp at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}, Duration: {datetime.now() - start_time}")
            else:
                print("\n📊 No results received yet.")
        except KeyboardInterrupt:
            print("\n🛑 Stopped by user.")
            cancel_task(api_endpoint, t_id)
            # Optional: continue listening for shutdown logs
            asyncio.run(listen_ws(ws_endpoint, t_id, task_name, mode="a", task_mode=cfg.get("mode", "dataset"), receiv_frame=False))