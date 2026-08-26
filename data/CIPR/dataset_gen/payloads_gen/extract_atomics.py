import yaml
import os
import json
import re

atomic_test_dir = "atomic-red-team/atomics"
def interpolate_args(text, input_arguments):
    """
    将文本中的 #{arg_name} 替换为 input_arguments 中的默认值
    """
    if not text or not input_arguments:
        return text if text else ""
    
    for arg_name, arg_details in input_arguments.items():
        # 获取默认值，如果没有则为空字符串
        default_value = str(arg_details.get('default', ''))
        # 替换 ART 特有的变量格式 #{variable_name}
        placeholder = f"#{{{arg_name}}}"
        text = text.replace(placeholder, default_value)
        
    return text

def parse_atomic_red_team_dataset(atomics_dir):
    custom_dataset =[]

    # 遍历所有的 technique 目录和 yaml 文件
    for root, dirs, files in os.walk(atomics_dir):
        for file in files:
            if file.endswith(".yaml") or file.endswith(".yml"):
                yaml_path = os.path.join(root, file)
                
                with open(yaml_path, 'r', encoding='utf-8') as f:
                    try:
                        technique_data = yaml.safe_load(f)
                    except yaml.YAMLError as e:
                        print(f"Error parsing {yaml_path}: {e}")
                        continue
                
                if not technique_data or 'atomic_tests' not in technique_data:
                    continue
                
                attack_technique = technique_data.get('attack_technique', '')
                
                # 遍历技术下的所有测试样例
                for test in technique_data['atomic_tests']:
                    # 1. 过滤：只保留支持 linux 平台的测试
                    supported_platforms = test.get('supported_platforms',[])
                    if 'linux' not in supported_platforms:
                        continue
                    
                    input_args = test.get('input_arguments', {})
                    executor = test.get('executor', {})
                    dependencies = test.get('dependencies',[])
                    
                    # 2. 映射: payload
                    raw_command = executor.get('command', '')
                    payload = raw_command
                    
                    # 3. 映射: craft_method
                    test_name = test.get('name', 'Unknown Test')
                    description = test.get('description', 'No description provided.').strip()
                    exec_name = executor.get('name', 'sh')
                    craft_method = f"[{test_name}]\nExecutor: {exec_name}\nDescription: {description}"
                    
                    # 4. 映射: env_setup_script
                    env_setup_cmds =[]
                    for dep in dependencies:
                        get_prereq = dep.get('get_prereq_command', '')
                        if get_prereq:
                            env_setup_cmds.append(get_prereq)
                    env_setup_script = "\n".join(env_setup_cmds)
                    
                    # 5. 映射: evaluation
                    # 结合 cleanup_command 和 prereq_command (用于验证)
                    eval_cmds =[]
                    cleanup_command = executor.get('cleanup_command', '')
                    if cleanup_command:
                        eval_cmds.append("### Cleanup Command ###\n" + cleanup_command)
                    
                    # 也可以加入前置验证作为 evaluation 的一部分
                    prereq_cmds =[]
                    for dep in dependencies:
                        prereq = dep.get('prereq_command', '')
                        if prereq:
                            prereq_cmds.append(prereq)
                    if prereq_cmds:
                        eval_cmds.append("### Prerequisite Check (Validation) ###\n" + "\n".join(prereq_cmds))
                        
                    evaluation = "\n\n".join(eval_cmds)
                    
                    # 组装自定义数据记录
                    record = {
                        "src": "https://github.com/redcanaryco/atomic-red-team",
                        "abbr": "atomic-red-team",
                        "category": technique_data.get("display_name"),
                        "payload": payload,
                        "craft": craft_method,
                        "env_setup_script": env_setup_script,
                        "evaluation": evaluation,
                        "need_var_substitution": True,
                        "metadata": {
                            "description": description,
                            "input_arguments": input_args,
                            "supported_platforms": supported_platforms,
                        }
                    }
                    custom_dataset.append(record)

    return custom_dataset

if __name__ == "__main__":
    # 指定你本地的 atomics 文件夹路径
    # 例如：ATOMICS_DIR = "./atomic-red-team/atomics"
    ATOMICS_DIR = "./atomic-red-team/atomics/" 

    if not os.path.exists(ATOMICS_DIR):
        print(f"Directory not found: {ATOMICS_DIR}. Please update the path.")
    else:
        mapped_data = parse_atomic_red_team_dataset(ATOMICS_DIR)
        
        # 将结果输出保存为 json 文件
        output_file = "dataset_gen/atomics_extrated_linux.json"
        with open(output_file, "w", encoding="utf-8") as out_f:
            json.dump(mapped_data, out_f, indent=4, ensure_ascii=False)
            
        print(f"Successfully processed {len(mapped_data)} Linux payloads.")
        print(f"Data saved to {output_file}")
