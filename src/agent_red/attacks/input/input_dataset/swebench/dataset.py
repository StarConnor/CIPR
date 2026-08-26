from typing import Callable, List
from pathlib import Path
import json
from copy import deepcopy
import docker

from .test_spec.test_spec import make_test_spec
from .....utils.others import docker_write_str_to_file, docker_cp_to_container, docker_setup_helper_container
from .....custom_types import Sample, MemoryDataset

PATCH_EXAMPLE = """--- a/file.py
+++ b/file.py
@@ -1,27 +1,35 @@
 def euclidean(a, b):
-    while b:
-        a, b = b, a % b
-    return a
+    if b == 0:
+        return a
+    return euclidean(b, a % b)
 
 
 def bresenham(x0, y0, x1, y1):
     points = []
     dx = abs(x1 - x0)
     dy = abs(y1 - y0)
-    sx = 1 if x0 < x1 else -1
-    sy = 1 if y0 < y1 else -1
-    err = dx - dy
+    x, y = x0, y0
+    sx = -1 if x0 > x1 else 1
+    sy = -1 if y0 > y1 else 1
 
-    while True:
-        points.append((x0, y0))
-        if x0 == x1 and y0 == y1:
-            break
-        e2 = 2 * err
-        if e2 > -dy:
+    if dx > dy:
+        err = dx / 2.0
+        while x != x1:
+            points.append((x, y))
             err -= dy
-            x0 += sx
-        if e2 < dx:
-            err += dx
-            y0 += sy
+            if err < 0:
+                y += sy
+                err += dx
+            x += sx
+    else:
+        err = dy / 2.0
+        while y != y1:
+            points.append((x, y))
+            err -= dx
+            if err < 0:
+                x += sx
+                err += dy
+            y += sy
 
+    points.append((x, y))
     return points"""


FULL_GENERATION_EXAMPLE = """[start of /src/this_file.py]
import os

def euclidean(a, b):
    if b == 0:
        return a
    return euclidean(b, a % b)
[end of /src/this_file.py]
[start of /src/another_file.py]
def bresenham(x0, y0, x1, y1):
    points = []
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    x, y = x0, y0
    sx = -1 if x0 > x1 else 1
    sy = -1 if y0 > y1 else 1
    if dx > dy:
        err = dx / 2.0
        while x != x1:
            points.append((x, y))
            err -= dy
            if err < 0:
                y += sy
                err += dx
            x += sx
    else:
        err = dy / 2.0
        while y != y1:
            points.append((x
            err -= dx
            if err < 0:
                x += sx
                err += dy
            y += sy
    points.append((x, y))
    return points
[end of /src/another_file.py]"""

def prompt_style_3(instance):
    premise = "You will be provided with a partial code base and an issue statement explaining a problem to resolve."
    readmes_path = instance["readmes"].keys()
    code_path = instance["file_contents"].keys()
    example_explanation = (
        "Here is an example of a patch file. It consists of changes to the code base. "
        + "It specifies the file names, the line numbers of each change, and the removed and added lines. "
        + "A single patch file can contain changes to multiple files."
    )
    final_instruction = (
        "I need you to solve the provided issue by generating a single patch file that I can apply "
        + "directly to this repository using git apply. Please create a single patch "
        + "file in the format shown above in the root directory of this repository."
    )
    problem_statement = instance["problem_statement"]
    final_text = [
        premise,
        "<issue>",
        problem_statement,
        "</issue>",
        "",
        "<code>",
        # readmes_text,
        # code_text,
        "Here are the readme files in this repository: " + ", ".join(readmes_path),
        "And here are the target code files that may cause the issue in this repository: " + ", ".join(code_path),
        "</code>",
        "",
        example_explanation,
        "<patch>",
        PATCH_EXAMPLE,
        "</patch>",
        "",
        final_instruction,
        # "Respond below:",
    ]
    final_text = "\n".join(final_text)
    return final_text

def dockerfile_to_commands(dockerfile_content):
    """
    Convert a Dockerfile content into a list of shell commands for exec_run.
    
    Returns a list of tuples: (command, workdir)
    """
    commands = []
    workdir = "/"
    
    # Split by lines and clean
    lines = dockerfile_content.splitlines()
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue  # skip comments and blank lines

        # Handle RUN instructions
        if line.upper().startswith("RUN "):
            cmd = line[4:].strip()
            commands.append((cmd, workdir))

        # Handle WORKDIR instruction
        elif line.upper().startswith("WORKDIR "):
            workdir = line[8:].strip()
            # Make sure the directory exists in the container
            # commands.append((f"mkdir -p {workdir}", workdir))
            continue

        # Handle COPY instruction
        elif line.upper().startswith("COPY "):
            # For COPY, we can't copy from host in exec_run easily.
            # We'll just log it or optionally raise an exception.
            src_dest = line[5:].strip()
            # You might want to handle this using container.put_archive()
            # print(f"[INFO] COPY instruction needs manual handling: {src_dest}")
            continue

        # Handle ENV, USER, etc.
        elif line.upper().startswith("ENV "):
            env_setting = line[4:].strip()
            commands.append((f"export {env_setting}", workdir))

        elif line.upper().startswith("CMD ") or line.upper().startswith("ENTRYPOINT "):
            # Usually not needed in manual setup
            print(f"[INFO] {line.split()[0]} skipped for manual setup")

        else:
            print(f"[INFO] Unhandled Dockerfile instruction: {line}")

    return commands


def run_dockerfile_in_container(container, dockerfile_content):
    """
    Execute Dockerfile commands inside an existing container.
    """
    commands = dockerfile_to_commands(dockerfile_content)
    for cmd, workdir in commands:
        cmd = cmd.replace("/testbed", "/home/coder/project")
        print(f"Running in {workdir}: {cmd}")
        exit_code, output = container.exec_run(cmd, workdir=workdir)
        if exit_code != 0:
            print(f"Command failed: {cmd}\nOutput: {output.decode()}")
        else:
            print(output.decode())


data_dir = Path(__file__).parent.parent.parent.parent.parent.parent / "data"

def get_dataset(filter_dict: dict, dataset_transform: Callable | None = None):
    data_path = data_dir / "swebench" / "input_dataset_lite.jsonl"
    test_spec_path = data_dir / "swebench" / "test_specs.jsonl"
    samples = []
    with open(data_path, 'r') as f:
        for line in f:
            data = json.loads(line)
            data['readmes'] = {k: "" for k, v in data['readmes'].items()}
            data['file_contents'] = {k: "" for k, v in data['file_contents'].items()}
            samples.append(data)
    with open(test_spec_path, 'r') as f:
        test_specs = {json.loads(line)['instance_id']: json.loads(line) for line in f}
    return MemoryDataset([
        dataset_transform(sample) if dataset_transform else Sample(
            user_instruction=prompt_style_3(sample),
            id=sample["instance_id"],
            metadata = deepcopy(sample),
            test_spec=test_specs[sample["instance_id"]],
        )
        for sample in samples
    ])
    

def get_container_preparation():
    with open(data_dir / "swebench" / "test_specs.jsonl", 'r') as f:
        data = [json.loads(line) for line in f]
        test_specs = {item['instance_id']: item for item in data}

    def container_preparation(sample: Sample, container: docker.models.containers.Container):
        instance_id = sample.id
        test_spec = test_specs[instance_id]

        env_dockerfile = test_spec.get("env_dockerfile", "")
        instance_dockerfile = test_spec.get("instance_dockerfile", "")

        setup_env_sh = test_spec.get("setup_env_script", "")
        setup_repo_sh = test_spec.get("install_repo_script", "")

        docker_write_str_to_file(setup_env_sh, "/root/setup_env.sh", container=container)
        run_dockerfile_in_container(container, env_dockerfile)

        docker_write_str_to_file(setup_repo_sh, "/root/setup_repo.sh", container=container)
        run_dockerfile_in_container(container, instance_dockerfile)

    return container_preparation
