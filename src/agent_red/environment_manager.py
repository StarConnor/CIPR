# environment_manager.py
import os
import pdb
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import urlparse
import logging

# Assume DockerExecutionEnvironment is defined elsewhere,
# e.g., from your existing utilities.
from .env.docker_env import DockerExecutionEnvironment 
from .utils.others import docker_cp_to_container, docker_write_str_to_file
from .utils.runtime_toolchain_mounts import (
    DEFAULT_RUNTIME_BASE_PATH,
    DEFAULT_RUNTIME_CONTAINER_ROOT,
    build_runtime_mount_config,
    parse_bool,
)
from .custom_types import EnvironmentState, AgentConfig

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

CONTAINER_NAME_PREFIX = "agent-redteam"


def _container_name(component: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"{CONTAINER_NAME_PREFIX}-{component}-rt-{timestamp}"

class EnvironmentManager:
    """
    Manages the setup and teardown of the complex Docker-based testing environment.
    """
    def __init__(
        self,
        agent: AgentConfig,
        log_path: str = "logs/",
        src_path: Optional[str] = None,
        dst_path: Optional[str] = None,
        html_domain: str = "target.com",
        attacker_domain: str = "security.org",
        debug_port: int = -1,
        env_image_name: Optional[str] = None,
        https_proxy: Optional[str] = None,
        host_ip: Optional[str] = None,
        **kwargs,
        # ... other configs like scenario_name can be passed here ...
    ):
        self.environments: Dict[str, DockerExecutionEnvironment] = {}
        self.agent = agent
        self.html_domain = html_domain
        self.attacker_domain = attacker_domain
        self.type = self.agent.software.split('_')[-1]
        self.env_image_name = env_image_name
        self.kwargs = kwargs
        self.log_path = log_path
        self.src_path = src_path
        self.dst_path = dst_path
        self.debug_port = debug_port
        self.https_proxy = https_proxy
        self.host_ip = host_ip or os.getenv("HOST_IP", "localhost")
        self.http_domain = urlparse(https_proxy).hostname if https_proxy else None
        self.runtime_toolchain_root = self.kwargs.get(
            "runtime_toolchain_root", os.getenv("RUNTIME_TOOLCHAIN_ROOT")
        )
        self.runtime_languages = self.kwargs.get(
            "runtime_languages", os.getenv("RUNTIME_LANGUAGES")
        )
        self.runtime_mount_mode = self.kwargs.get(
            "runtime_mount_mode", os.getenv("RUNTIME_MOUNT_MODE", "ro")
        )
        self.runtime_mount_strict = parse_bool(
            self.kwargs.get("runtime_mount_strict", os.getenv("RUNTIME_MOUNT_STRICT", "false")),
            default=False,
        )
        self.runtime_container_root = self.kwargs.get(
            "runtime_container_root",
            os.getenv("RUNTIME_CONTAINER_ROOT", DEFAULT_RUNTIME_CONTAINER_ROOT),
        )
        self.runtime_base_path = self.kwargs.get(
            "runtime_base_path", os.getenv("RUNTIME_BASE_PATH", DEFAULT_RUNTIME_BASE_PATH)
        )
        self.enable_dependency_cache = parse_bool(
            self.kwargs.get(
                "enable_dependency_cache",
                os.getenv("ENABLE_DEPENDENCY_CACHE", os.getenv("ENABLE_DEPENDENCY_PROXIES", "false")),
            ),
            default=False,
        )
        self.dependency_cache_host_alias = self.kwargs.get(
            "dependency_cache_host_alias",
            os.getenv("DEPENDENCY_CACHE_HOST_ALIAS", "host.docker.internal"),
        )
        self.dependency_cache_python_port = str(self.kwargs.get("dependency_cache_python_port", os.getenv("DEPENDENCY_CACHE_PYTHON_PORT", "3141")))
        self.dependency_cache_apt_port = str(self.kwargs.get("dependency_cache_apt_port", os.getenv("DEPENDENCY_CACHE_APT_PORT", "3142")))
        self.dependency_cache_npm_port = str(self.kwargs.get("dependency_cache_npm_port", os.getenv("DEPENDENCY_CACHE_NPM_PORT", "4873")))
        self.dependency_cache_go_port = str(self.kwargs.get("dependency_cache_go_port", os.getenv("DEPENDENCY_CACHE_GO_PORT", "3010")))
        self.dependency_cache_maven_port = str(self.kwargs.get("dependency_cache_maven_port", os.getenv("DEPENDENCY_CACHE_MAVEN_PORT", "18082")))
        self.dependency_cache_cargo_port = str(self.kwargs.get("dependency_cache_cargo_port", os.getenv("DEPENDENCY_CACHE_CARGO_PORT", "18083")))
        self.dependency_cache_packagist_port = str(self.kwargs.get("dependency_cache_packagist_port", os.getenv("DEPENDENCY_CACHE_PACKAGIST_PORT", "18084")))
        self.dependency_cache_rubygems_port = str(self.kwargs.get("dependency_cache_rubygems_port", os.getenv("DEPENDENCY_CACHE_RUBYGEMS_PORT", "9292")))
        self.mitm_port = str(self.kwargs.get("mitm_port", os.getenv("MITM_PORT", "7999")))

    def _append_no_proxy(self, env_vars: Dict[str, str], hosts: List[str]) -> None:
        existing = env_vars.get("NO_PROXY") or env_vars.get("no_proxy") or ""
        parts = [p.strip() for p in existing.split(",") if p.strip() and p.strip() != "None"]
        seen = set(parts)
        for host in hosts:
            if host and host not in seen:
                parts.append(host)
                seen.add(host)
        joined = ",".join(parts)
        env_vars["NO_PROXY"] = joined
        env_vars["no_proxy"] = joined

    def _dependency_cache_env_vars(self) -> Dict[str, str]:
        host = self.host_ip
        return {
            "DEPENDENCY_CACHE_ENABLED": "true",
            "DEPENDENCY_CACHE_HOST": host,
            # Python: pip and uv use a plain HTTP devpi endpoint. PIP_TRUSTED_HOST avoids TLS/cert issues.
            "PIP_INDEX_URL": f"http://{host}:{self.dependency_cache_python_port}/root/pypi/+simple",
            "PIP_TRUSTED_HOST": host,
            "UV_INDEX_URL": f"http://{host}:{self.dependency_cache_python_port}/root/pypi/+simple",
            "UV_INSECURE_HOST": host,
            # Node: Verdaccio is HTTP on the host; strict SSL is off only for this registry path.
            "NPM_CONFIG_REGISTRY": f"http://{host}:{self.dependency_cache_npm_port}",
            "NPM_CONFIG_STRICT_SSL": "false",
            "YARN_REGISTRY": f"http://{host}:{self.dependency_cache_npm_port}",
            # Go: local HTTP proxy caches proxy.golang.org; direct fallback preserves compatibility.
            "GOPROXY": f"http://{host}:{self.dependency_cache_go_port},direct",
            "GONOSUMDB": os.getenv("GONOSUMDB", ""),
            # Composer can read this env var directly.
            "COMPOSER_REPO_PACKAGIST": f"http://{host}:{self.dependency_cache_packagist_port}",
            # Cargo uses config.toml written after startup; keep env marker for debugging.
            "CARGO_HTTP_CHECK_REVOKE": "false",
        }

    def _configure_dependency_cache_clients(self, env_vars: Dict[str, str]) -> None:
        """Write package-manager config files inside the experiment container.

        This is intentionally package-manager specific. We do not replace global
        HTTP_PROXY/HTTPS_PROXY because those are reserved for the container-local
        mitmproxy trace path.
        """
        if not self.enable_dependency_cache:
            return
        if not getattr(self, "code_server", None) or not self.code_server.container:
            return

        host = self.host_ip
        python_port = self.dependency_cache_python_port
        apt_port = self.dependency_cache_apt_port
        npm_port = self.dependency_cache_npm_port
        maven_port = self.dependency_cache_maven_port
        cargo_port = self.dependency_cache_cargo_port
        packagist_port = self.dependency_cache_packagist_port
        rubygems_port = self.dependency_cache_rubygems_port
        container = self.code_server.container
        LOGGER.info("Configuring dependency cache clients to use host %s", host)

        files: dict[str, tuple[str, Optional[str]]] = {
            "/etc/pip.conf": (
                f"""[global]
index-url = http://{host}:{python_port}/root/pypi/+simple
trusted-host = {host}
disable-pip-version-check = true
""",
                None,
            ),
            "/home/devuser/.config/pip/pip.conf": (
                f"""[global]
index-url = http://{host}:{python_port}/root/pypi/+simple
trusted-host = {host}
cache-dir = /home/devuser/.cache/pip
disable-pip-version-check = true
""",
                "devuser",
            ),
            "/home/devuser/.npmrc": (
                f"""registry=http://{host}:{npm_port}/
strict-ssl=false
cache=/home/devuser/.npm
""",
                "devuser",
            ),
            "/root/.npmrc": (
                f"""registry=http://{host}:{npm_port}/
strict-ssl=false
cache=/root/.npm
""",
                None,
            ),
            "/etc/apt/apt.conf.d/01dependency-cache": (
                f"""Acquire::http::Proxy "http://{host}:{apt_port}";
Acquire::https::Proxy "false";
""",
                None,
            ),
            "/home/devuser/.m2/settings.xml": (
                f"""<settings>
  <mirrors>
    <mirror>
      <id>redteam-dependency-cache</id>
      <mirrorOf>central</mirrorOf>
      <url>http://{host}:{maven_port}/</url>
    </mirror>
  </mirrors>
</settings>
""",
                "devuser",
            ),
            "/root/.m2/settings.xml": (
                f"""<settings>
  <mirrors>
    <mirror>
      <id>redteam-dependency-cache</id>
      <mirrorOf>central</mirrorOf>
      <url>http://{host}:{maven_port}/</url>
    </mirror>
  </mirrors>
</settings>
""",
                None,
            ),
            "/home/devuser/.gradle/init.gradle": (
                f"""allprojects {{
    buildscript {{
        repositories {{
            maven {{ url 'http://{host}:{maven_port}/' }}
            mavenCentral()
            gradlePluginPortal()
            google()
        }}
    }}
    repositories {{
        maven {{ url 'http://{host}:{maven_port}/' }}
        mavenCentral()
        google()
    }}
}}
settingsEvaluated {{ settings ->
    settings.pluginManagement {{
        repositories {{
            maven {{ url 'http://{host}:{maven_port}/' }}
            gradlePluginPortal()
            mavenCentral()
            google()
        }}
    }}
}}
""",
                "devuser",
            ),
            "/root/.gradle/init.gradle": (
                f"""allprojects {{
    buildscript {{
        repositories {{ maven {{ url 'http://{host}:{maven_port}/' }}; mavenCentral(); gradlePluginPortal(); google() }}
    }}
    repositories {{ maven {{ url 'http://{host}:{maven_port}/' }}; mavenCentral(); google() }}
}}
""",
                None,
            ),
            "/home/devuser/.cargo/config.toml": (
                f"""[source.crates-io]
replace-with = "redteam-cache"

[source.redteam-cache]
registry = "sparse+http://{host}:{cargo_port}/"

[net]
git-fetch-with-cli = true

[http]
check-revoke = false
""",
                "devuser",
            ),
            "/root/.cargo/config.toml": (
                f"""[source.crates-io]
replace-with = "redteam-cache"

[source.redteam-cache]
registry = "sparse+http://{host}:{cargo_port}/"

[net]
git-fetch-with-cli = true

[http]
check-revoke = false
""",
                None,
            ),
            "/home/devuser/.bundle/config": (
                f"""---
BUNDLE_MIRROR__HTTPS://RUBYGEMS__ORG/: "http://{host}:{rubygems_port}/"
BUNDLE_SSL_VERIFY_MODE: "0"
BUNDLE_PATH: "/home/devuser/.bundle/vendor"
BUNDLE_CACHE_PATH: "/home/devuser/.bundle/cache"
""",
                "devuser",
            ),
            "/root/.bundle/config": (
                f"""---
BUNDLE_MIRROR__HTTPS://RUBYGEMS__ORG/: "http://{host}:{rubygems_port}/"
BUNDLE_SSL_VERIFY_MODE: "0"
""",
                None,
            ),
            "/home/devuser/.config/composer/config.json": (
                f"""{{
  "repositories": {{
    "packagist.org": {{
      "type": "composer",
      "url": "http://{host}:{packagist_port}"
    }}
  }},
  "secure-http": false,
  "cache-dir": "/home/devuser/composer/cache"
}}
""",
                "devuser",
            ),
            "/root/.config/composer/config.json": (
                f"""{{
  "repositories": {{
    "packagist.org": {{
      "type": "composer",
      "url": "http://{host}:{packagist_port}"
    }}
  }},
  "secure-http": false
}}
""",
                None,
            ),
        }

        for path, (content, owner) in files.items():
            docker_write_str_to_file(content, path, container=container, target_user=owner)

        profile = "\n".join(f"export {key}='{value}'" for key, value in env_vars.items() if value is not None)
        docker_write_str_to_file(profile + "\n", "/etc/profile.d/dependency-cache.sh", container=container)
        container.exec_run("chmod 644 /etc/profile.d/dependency-cache.sh", user="root")

        # Create common cache directories and fix ownership for devuser.
        container.exec_run(
            [
                "bash",
                "-lc",
                (
                    "mkdir -p /home/devuser/.cache/pip /home/devuser/.cache/uv /home/devuser/.cache/yarn "
                    "/home/devuser/.npm /home/devuser/.pnpm-store /home/devuser/.m2 /home/devuser/.gradle "
                    "/home/devuser/.cargo /home/devuser/.bundle/cache /home/devuser/composer/cache "
                    "/home/devuser/.config/pip /home/devuser/.config/composer "
                    "/home/devuser/go/pkg/mod /home/devuser/.cache/go-build && "
                    "chown -R devuser:devuser /home/devuser/.cache /home/devuser/.npm /home/devuser/.pnpm-store "
                    "/home/devuser/.m2 /home/devuser/.gradle /home/devuser/.cargo /home/devuser/.bundle "
                    "/home/devuser/.config /home/devuser/composer /home/devuser/go"
                ),
            ],
            user="root",
        )

    def _prepare_writable_toolchain_state(self, runtime_mount_config: Dict[str, object]) -> None:
        """Create writable per-container state dirs for mounted toolchains.

        Runtime toolchains are intentionally shared across runs and are usually
        mounted read-only. Package managers, however, still need writable home
        directories for caches/config/shims. Keeping those under /home/devuser
        avoids mutating the shared toolchain and prevents EACCES/timeouts.
        """
        if not getattr(self, "code_server", None) or not self.code_server.container:
            return

        container = self.code_server.container
        enabled = set(runtime_mount_config.get("enabled_languages", []))
        container_paths = runtime_mount_config.get("container_paths", {})

        # Common writable locations used by the env vars in
        # runtime_toolchain_mounts.py and by dependency-cache config.
        common_dirs = [
            "/home/devuser/.cache",
            "/home/devuser/.cache/pip",
            "/home/devuser/.cache/uv",
            "/home/devuser/.cache/yarn",
            "/home/devuser/.cache/go-build",
            "/home/devuser/.npm",
            "/home/devuser/.pnpm-store",
            "/home/devuser/.m2",
            "/home/devuser/.gradle",
            "/home/devuser/.cargo",
            "/home/devuser/.rustup",
            "/home/devuser/go/pkg/mod",
            "/home/devuser/.gem/ruby/3.3.0",
            "/home/devuser/.gem/specs",
            "/home/devuser/.bundle",
            "/home/devuser/.bundle/cache",
            "/home/devuser/.bundle/vendor",
            "/home/devuser/composer/cache",
            "/home/devuser/.config/pip",
            "/home/devuser/.config/composer",
        ]

        quoted_dirs = " ".join(f"'{d}'" for d in common_dirs)
        exit_code, output = container.exec_run(
            [
                "bash",
                "-lc",
                (
                    f"mkdir -p {quoted_dirs} && "
                    "chown -R devuser:devuser "
                    "/home/devuser/.cache /home/devuser/.npm /home/devuser/.pnpm-store "
                    "/home/devuser/.m2 /home/devuser/.gradle /home/devuser/.cargo /home/devuser/.rustup "
                    "/home/devuser/go /home/devuser/.gem /home/devuser/.bundle "
                    "/home/devuser/composer /home/devuser/.config"
                ),
            ],
            user="root",
        )
        if exit_code != 0:
            LOGGER.warning("Failed to prepare writable toolchain dirs: %s", output.decode(errors="replace"))

        # If the Ruby toolchain includes rbenv on the read-only mount, expose a
        # writable RBENV_ROOT while symlinking immutable versions/plugins back to
        # the mounted toolchain. This lets tools that run `rbenv rehash` create
        # shims without writing to /opt/runtime-toolchains/ruby.
        if "ruby" in enabled:
            ruby_root = container_paths.get("ruby") if isinstance(container_paths, dict) else None
            if ruby_root:
                cmd = f"""set -e
mkdir -p /home/devuser/.rbenv /home/devuser/.rbenv/shims
if [ -d '{ruby_root}/rbenv/versions' ]; then
  ln -sfn '{ruby_root}/rbenv/versions' /home/devuser/.rbenv/versions
fi
if [ -d '{ruby_root}/rbenv/plugins' ]; then
  ln -sfn '{ruby_root}/rbenv/plugins' /home/devuser/.rbenv/plugins
fi
chown -h devuser:devuser /home/devuser/.rbenv/versions /home/devuser/.rbenv/plugins 2>/dev/null || true
chown -R devuser:devuser /home/devuser/.rbenv /home/devuser/.gem /home/devuser/.bundle
"""
                exit_code, output = container.exec_run(["bash", "-lc", cmd], user="root")
                if exit_code != 0:
                    LOGGER.warning("Failed to prepare writable Ruby/rbenv state: %s", output.decode(errors="replace"))

    def setup(self) -> EnvironmentState:
        LOGGER.info("🚀 Starting VM environment setup...")
        
        try:
            code_server_env_vars = {}
            params = {}
            runtime_mount_config = build_runtime_mount_config(
                runtime_root=self.runtime_toolchain_root,
                runtime_languages=self.runtime_languages,
                container_root=self.runtime_container_root,
                mount_mode=self.runtime_mount_mode,
                strict=self.runtime_mount_strict,
            )

            if self.type == "ide":
                self.vm_ssh_port = self.kwargs.get('vm_ssh_port', 2222)
                code_server_env_vars = {"SSH_PORT": self.vm_ssh_port, "START_SSH": "true"}
                params["health_port"] = self.vm_ssh_port
                params["network"] = "host"
            elif self.type == "cli":
                params["ports"] = {"8000/tcp": 5000}
                if self.debug_port > 0:
                    params["ports"]["4444/tcp"] = self.debug_port

            volumes: Dict[str, Dict[str, str]] = {}
            if self.src_path and self.dst_path:
                volumes[self.src_path] = {"bind": "/src", "mode": "ro"}
            if runtime_mount_config["volumes"]:
                volumes.update(runtime_mount_config["volumes"])
            if volumes:
                params["volumes"] = volumes

            self.web_server = DockerExecutionEnvironment(
                image_name="web-server:latest",
                container_name=_container_name("web-server"),
                ports={"8080/tcp": 8084, "8081/tcp": 8085},
            )
            self.web_server.setup()
            self.environments["web_server"] = self.web_server
            web_port = self.web_server.ports.get("8080/tcp", 8084)
            attacker_port = self.web_server.ports.get("8081/tcp", 8085)

            base_no_proxy_hosts = [
                "localhost",
                "127.0.0.1",
                self.http_domain,
                "security.ubuntu.com",
                "archive.ubuntu.com",
                "ubuntu.com",
                "*.ubuntu.com",
            ]
            if self.enable_dependency_cache:
                base_no_proxy_hosts.extend([self.host_ip, self.dependency_cache_host_alias])
            base_no_proxy = ",".join([h for h in base_no_proxy_hosts if h])

            code_server_env_vars.update({
                "HTML_IP": self.host_ip,
                "HTML_PORT": str(web_port),
                "HTML_DOMAIN": self.html_domain,
                "ATTACKER_IP": self.host_ip,
                "ATTACKER_PORT": str(attacker_port),
                "ATTACKER_DOMAIN": self.attacker_domain,
                "MITM_TARGET_HOSTS": "api.anthropic.com,api.openai.com,openrouter.ai,api.gpt.ge,api.deepseek.com,ai.moo.kim",
                "MITM_PORT": self.mitm_port,
                "LOG_LEVEL": "DEBUG",
                "NO_PROXY": base_no_proxy,
                "no_proxy": base_no_proxy,
            })

            # The automation server running inside every CLI container uses an
            # OpenAI-compatible client for workflow operations.  Its credential
            # is deliberately separate from the evaluated coding agent: for
            # example, Claude Code can use CHEAP_* while the automation server
            # uses an OpenAI-compatible CODEX_* endpoint.  A dedicated
            # AUTOMATION_SERVER_OPENAI_* pair takes precedence when configured.
            automation_api_key = (
                os.getenv("AUTOMATION_SERVER_OPENAI_API_KEY")
                or os.getenv("CODEX_API_KEY")
                or self.agent.model.api_key
            )
            automation_base_url = (
                os.getenv("AUTOMATION_SERVER_OPENAI_BASE_URL")
                or os.getenv("CODEX_BASE_URL")
                or self.agent.model.base_url
            )
            if automation_api_key:
                code_server_env_vars["OPENAI_API_KEY"] = automation_api_key
            if automation_base_url:
                code_server_env_vars["OPENAI_BASE_URL"] = automation_base_url

            if "trae" not in self.agent.software:
                code_server_env_vars.update({
                    "ENABLE_MITM": "true",
                    "UPSTREAM_PROXY": self.https_proxy or "",
                    "HTTPS_PROXY": self.https_proxy or "",
                    "https_proxy": self.https_proxy or "",
                    "http_proxy": self.https_proxy or "",
                })
            else:
                code_server_env_vars.update({"ENABLE_MITM": 'false'})

            dependency_cache_env_vars: Dict[str, str] = {}
            if self.enable_dependency_cache:
                dependency_cache_env_vars = self._dependency_cache_env_vars()
                code_server_env_vars.update(dependency_cache_env_vars)
                self._append_no_proxy(code_server_env_vars, [self.host_ip, self.dependency_cache_host_alias])
                LOGGER.info("Dependency cache enabled via host %s", self.host_ip)

            if runtime_mount_config["environment_vars"]:
                code_server_env_vars.update(runtime_mount_config["environment_vars"])
            if runtime_mount_config["runtime_bin_paths"]:
                runtime_path = ":".join(runtime_mount_config["runtime_bin_paths"])
                code_server_env_vars["PATH"] = f"{runtime_path}:{self.runtime_base_path}"
                LOGGER.info(
                    "Mounted runtime toolchains: %s",
                    ", ".join(runtime_mount_config["enabled_languages"]),
                )
            if runtime_mount_config["missing_languages"]:
                LOGGER.warning(
                    "Missing runtime toolchain directories: %s",
                    ", ".join(runtime_mount_config["missing_languages"]),
                )

            python_runtime_root = runtime_mount_config["container_paths"].get("python")
            python_lib_paths = f"{python_runtime_root}/lib:{python_runtime_root}/lib64" if python_runtime_root else ""
            
            # Ruby handling (newly added)
            ruby_runtime_root = runtime_mount_config["container_paths"].get("ruby")
            ruby_lib_paths = f"{ruby_runtime_root}/lib" if ruby_runtime_root else ""

            # Aggregate all extra library paths
            extra_lib_paths = ":".join(filter(None, [python_lib_paths, ruby_lib_paths]))
            
            if extra_lib_paths:
                base_ld_path = os.getenv("LD_LIBRARY_PATH", "")
                code_server_env_vars["LD_LIBRARY_PATH"] = (
                    f"{extra_lib_paths}:{base_ld_path}" if base_ld_path else extra_lib_paths
                )

            # Define code-server (Simplified for brevity, keep your existing env vars)
            params.update({
                "image_name": f"{self.env_image_name}:{self.agent.software.split('_')[0]}" if self.env_image_name else (f"cli-env:{self.agent.software.split('_')[0]}" if self.type == "cli" else "base-env:latest"),
                "container_name": _container_name(self.agent.software),
                "environment_vars":code_server_env_vars,
                "is_ssh": self.type == "ide",
                "privileged": True,
                "extra_hosts": {self.dependency_cache_host_alias: "host-gateway"} if self.enable_dependency_cache else {},
            })
            self.code_server = DockerExecutionEnvironment(**params)
            # Start Container
            LOGGER.info("⚙️ Setting up dev environment...")
            self.code_server.setup()

            self._prepare_writable_toolchain_state(runtime_mount_config)
            self._configure_dependency_cache_clients(dependency_cache_env_vars)

            if "rust" in runtime_mount_config["enabled_languages"]:
                exit_code, output = self.code_server.container.exec_run(
                    f"cp -r '{runtime_mount_config["container_paths"].get("rust")}/rustup/.' '{code_server_env_vars.get("RUSTUP_HOME", '/home/devuser/.rustup')}/'",
                    user="root"
                )
                exit_code, output = self.code_server.container.exec_run(
                    f"chown -R devuser:devuser '{code_server_env_vars.get("RUSTUP_HOME", '/home/devuser/.rustup')}'",
                    user="root"
                )
                LOGGER.info(f"Rust toolchain copy exit code: {exit_code}")

            self.environments["code_server"] = self.code_server
            if self.type == "ide":
                ide_server_folder = self.agent.ide_server_folder
                if isinstance(ide_server_folder, str) and ide_server_folder:
                    docker_cp_to_container(self.agent.ide_server_folder, "/home/devuser/", container=self.code_server.container, target_user="devuser")
                elif isinstance(ide_server_folder, list):
                    for folder in ide_server_folder:
                        docker_cp_to_container(folder, "/home/devuser/", container=self.code_server.container, target_user="devuser")

            # self.mcp_server = DockerExecutionEnvironment(
            #     image_name="mcp-server:0.1",
            #     container_name=_container_name("mcp"),
            #     # FIXME
            #     # ports={"8000/tcp": 8000}, 
            #     health_port=8000,
            #     network="host", 
            # )
            # self.environments["mcp_server"] = self.mcp_server
            
            if self.src_path and self.dst_path:
                exit_code, output = self.code_server.container.exec_run(
                    f"cp -r /src/. {self.dst_path}/",
                    user="devuser"
                )
                print(f"Copy exit code: {exit_code}")
                print(f"Output: {output.decode()}")
            
            # self.mcp_server.setup()

            return EnvironmentState(
                vscode_url=self.code_server.api_url,
                code_server_container=self.code_server,
                running_environments=self.environments,
                proxy_dashboard_url=None,
                password=""
            )

        except Exception as e:
            LOGGER.error(f"💥 Setup failed: {e}")
            self.cleanup()
            raise

    # def set_file_attack_files(self, file_attack_files: List[FileAttack] | None):
    #     if file_attack_files is None:
    #         return
    #     for file_attack_file in file_attack_files:
    #         docker_write_str_to_file(file_attack_file.content, file_attack_file.container_path, container=self.code_server.container, target_user=file_attack_file.user)


    def cleanup(self):
        """Stops and removes all Docker containers created during setup."""
        LOGGER.info("🧹 Cleaning up environments...")
        if not self.environments:
            LOGGER.info("No environments to clean up.")
            return
            
        for k, env in self.environments.items():
            try:
                LOGGER.info(f"Tearing down {env.container_name}...")
                env.teardown(self.log_path)
            except Exception as e:
                LOGGER.warning(f"⚠️ Error during cleanup of {env.container_name}: {e}")
        
        # if self.volume:
        #     try:
        #         LOGGER.info(f"Removing Docker volume {self.volume.name}...")
        #         self.volume.remove(force=True)
        #     except Exception as e:
        #         LOGGER.warning(f"⚠️ Error removing volume {self.volume.name}: {e}")
