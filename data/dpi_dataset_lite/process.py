import json

with open("dataset.json", 'r') as f:
    data = json.load(f)

i = 0
for sample in data:
    endpoint = sample['endpoint'] if 'endpoint' in sample else ""
    user_instruction = sample['user_instruction']
    if "{{ATTACKER_SERVER}}" in user_instruction:
        if "http://{{ATTACKER_SERVER}}" in user_instruction or "https://{{ATTACKER_SERVER}}" in user_instruction:
            user_instruction = user_instruction.replace("http://{{ATTACKER_SERVER}}", "{{ATTACKER_SERVER}}").replace("https://{{ATTACKER_SERVER}}", "{{ATTACKER_SERVER}}")
        if "{{ATTACKER_SERVER}}/" in user_instruction and user_instruction.split("{{ATTACKER_SERVER}}/")[-1].split()[0]:
            endpoint = user_instruction.split("{{ATTACKER_SERVER}}/")[-1].split()[0].rstrip('.,!?;:"`')
            if endpoint:
                sample['attacker_endpoint'] = endpoint
            else:
                i += 1
                print(f"Sample ID: {sample.get('id', 'N/A')}, No endpoint found in payload.")
        sample['user_instruction'] = user_instruction
            
    # prompt_injections = sample.get("prompt_injections", [])
    # script_to_fetch_from_attacker_server = sample.get("script_to_fetch_from_attacker_server", "")
    # success_check = sample.get("evaluation", {}).get("attack_success_check", [])
    # endpoint = ""
    # for check in success_check:
    #     if check.get("method", "") == "CHECK_NETWORK_LOG":
    #         endpoint = check.get("params", {}).get("pattern", "")
    # for injection in prompt_injections:
    #     payload = injection.get("payload_content", "")
    #     if "{{ATTACKER_SERVER}}/" in payload and payload.split("{{ATTACKER_SERVER}}/")[-1].split()[0]:
    #         endpoint = payload.split("{{ATTACKER_SERVER}}/")[-1].split()[0].rstrip('.,!?;:')
    #     if endpoint:
    #         # print(f"Sample ID: {sample.get('id', 'N/A')}, Endpoint: {endpoint}")
    #         sample['endpoint'] = endpoint
    #     else:
    #         attacker_server = "{{ATTACKER_SERVER}}" in payload
    #         i += 1 
    #         print(f"Sample ID: {attacker_server} | {sample.get('id', 'N/A')}, No endpoint found in payload.")
print(f"Total samples without endpoint: {i}")
with open("dataset_fixed.json", 'w') as f:
    json.dump(data, f, indent=2)