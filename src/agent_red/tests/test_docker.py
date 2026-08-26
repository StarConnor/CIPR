import os
from datetime import datetime
from pathlib import Path

from src.env.docker_env import DockerExecutionEnvironment
from src.utils.others import docker_cp_to_container, docker_write_str_to_file

if __name__ == "__main__":
    try:
        code_server = DockerExecutionEnvironment(
            image_name="my-code-server:0.3",
            container_name=f"my-code-server-redteam-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            # mounts=mounts,
            ports={"8080/tcp": 8092},
        )
        code_server.setup()
        src_path = os.path.join(Path(__file__).parent.parent.parent, "logs", "files", "report.json")
        # print(f"Copying files from {src_path} to /home/coder in container...")

        # docker_cp_to_container(
        #     src_path=src_path,
        #     dst_path="/home/coder",
        #     container=code_server.container,
        # )

        print(f"Writing files to /home/coder/hello.txt in container...")

        docker_write_str_to_file(
            data="Hello World!",
            filename="/home/coder/hello.txt",
            container=code_server.container,
        )
        
        exit_code, output = code_server.container.exec_run(
            cmd="bash -c 'cat /home/coder/hello.txt'",
            user="coder",
        )
        print(output.decode())
    finally:
        code_server.teardown()