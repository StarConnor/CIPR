import requests
import json
import base64
import os
import sys

# Configuration
SERVER_URL = "http://localhost:5001/stream"
OUTPUT_IMAGE = "terminal_view.png"

# The command you want the agent to execute
PROMPT = "Create a simple hello world python script and run it"

def test_stream():
    print(f"[*] Connecting to {SERVER_URL}...")
    print(f"[*] Output image will be saved to: {os.path.abspath(OUTPUT_IMAGE)}")

    try:
        response = requests.post(
            SERVER_URL,
            json={
                "prompt": PROMPT, 
                "model": "gemini-3-flash-preview", # Optional
                "mode": "oneshot" # Optional
            },
            stream=True
        )
        response.raise_for_status()

        # Iterate over the raw stream
        for line in response.iter_lines():
            if not line:
                continue

            decoded_line = line.decode('utf-8')

            # We are looking for lines starting with "data: " (SSE format)
            if decoded_line.startswith('data: '):
                json_str = decoded_line[6:] # Strip "data: "
                
                try:
                    payload = json.loads(json_str)
                    event_type = payload.get('type')
                    
                    if event_type == 'log':
                        # Print logs to console to mirror the terminal
                        log_data = payload.get('data', {})
                        message = log_data.get('message', '')
                        print(message, end='', flush=True)

                    elif event_type == 'screenshot':
                        # Decode and save the screenshot
                        b64_data = payload.get('data')
                        if b64_data:
                            img_bytes = base64.b64decode(b64_data)
                            with open(OUTPUT_IMAGE, "wb") as f:
                                f.write(img_bytes)
                            # Print a small dot to indicate a frame update without cluttering logs
                            # sys.stderr.write('.') 
                            # sys.stderr.flush()

                    elif event_type == 'complete':
                        print("\n\n[+] Execution Completed.")
                        chat_history = payload.get('outputs', {}).get('chat_history', '').get('content', '')
                        with open("chat_history.txt", "w") as log_file:
                            log_file.write(chat_history)
                        print("[+] Chat history saved to chat_history.txt")
                        # print(f"Full Log Length: {len(full_log)}")
                        break

                    elif event_type == 'error':
                        print(f"\n[!] Error from server: {payload.get('error')}")
                        break

                except json.JSONDecodeError:
                    print(f"\n[!] Failed to parse JSON: {json_str}")

    except requests.exceptions.RequestException as e:
        print(f"\n[!] Connection failed: {e}")
    except KeyboardInterrupt:
        print("\n[*] Stopped by user.")

if __name__ == "__main__":
    test_stream()