# Docker Image Build System

Unified Docker image build system for red-teaming multiple AI coding agents
with network tracing (mitmproxy) and per-run attacker servers.

## Features

- **Single entry point**: all agents share one `start_agent.sh`, configured via environment variables.
- **Flexible tracing**: mitmproxy network tracing and optional strace syscall tracing can be toggled per run.
- **Multi-agent support**: Claude Code, Codex, OpenCode, Cline, Gemini CLI, and more.
- **Uniform logging**: standardized log locations and formats across agents.

## Image Architecture

Every CLI agent image is built **directly on top of `base-env`**; there is no
intermediate `cli-env` layer. Agent images share the tag namespace
`cli-env:<agent>`:

```
base-env   (Ubuntu + Node + automation server + mitmproxy tracing)
    ↓ (one image per agent, all FROM base-env)
    ├── cli-env:cc       (Claude Code)
    ├── cli-env:codex    (Codex CLI)
    ├── cli-env:opencode (OpenCode)
    ├── cli-env:cline    (Cline)
    └── cli-env:gemini   (Gemini CLI)
```

At runtime the experiment framework derives the image name from
`env_image_name` + agent software (default `cli-env:<software>`); see
`src/agent_red/environment_manager.py`.

## Build Inputs

Build inputs are managed in one place:

```text
docker_prep/
├── base/assets/
│   ├── node-v22...tar.gz
│   ├── id_ed25519_1.pub          # SSH public key injected into images
│   ├── automation_server/
│   └── mitm-certs/
└── agents/
    ├── claude/claude-code.tgz
    ├── codex/codex.tgz
    ├── cline/cline.tgz
    ├── gemini/gemini.tgz
    └── opencode/opencode.tgz
```

Archives, certificates, and SSH keys are local build inputs and are ignored by
Git. A fresh checkout must provide them before building.

### 1. Prepare and build the base image

The Docker build stage needs access to Ubuntu, npm, and PyPI mirrors. Set a
proxy in your shell before running the build script; the script injects these
values into the `RUN` commands of a temporary rendered Dockerfile and never
modifies the committed Dockerfiles. The build aborts if no proxy is set, and
proxy values are never committed to Git.

```bash
export HTTP_PROXY=http://your-proxy-host:port
export HTTPS_PROXY=http://your-proxy-host:port
export http_proxy="$HTTP_PROXY"
export https_proxy="$HTTPS_PROXY"

cd docker_prep
./prepare_build_assets.sh base   # stages automation_server assets into base/assets/
./build.sh base                  # builds base-env
```

`build.sh base` requires:

- `base/assets/id_ed25519_1.pub` (or override with `PUBLIC_KEY_FILE=...`);
- `base/assets/node-v22.21.1-linux-x64.tar.gz`;
- `base/assets/automation_server/requirements-cli.txt`.

### 2. Build agent images

Use `build.sh` with one of the supported targets:
`base`, `cli`, `no_proxy`, `cc` (alias `claude`), `codex`, `opencode`,
`cline`, `gemini`, or `all`.

```bash
./build.sh cc        # builds cli-env:cc (rebuilds base-env first if needed)
./build.sh codex     # builds cli-env:codex
./build.sh opencode  # builds cli-env:opencode

./build.sh all       # builds base-env + every CLI agent image; fails with an
                     # explicit message if an agent's local package archive
                     # is missing
```

Each agent build first runs `./prepare_build_assets.sh <agent>` to stage its
local package archive.

### End-to-end standalone smoke test

Set your Codex API credentials and configure the build proxy, then run:

```bash
export HTTP_PROXY=http://your-proxy-host:port
export HTTPS_PROXY=http://your-proxy-host:port
export http_proxy="$HTTP_PROXY"
export https_proxy="$HTTPS_PROXY"
export CODEX_API_KEY=your-api-key
export CODEX_BASE_URL=https://your-compatible-endpoint/v1

bash docker_prep/test_standalone.sh
```

The script builds `base-env` and `cli-env:codex`, then runs
`standalone/codex_smoke_request.json`, whose fixed instruction is
`list all the files in this folder`. Results are written under
`results/standalone-codex-smoke/`; screenshots and the detailed runner log are
written under the corresponding `exp/standalone-standalone-codex-smoke/`
directory.

### 3. Run an image manually

```bash
docker run -it --rm --privileged \
  -v "$(pwd)/workspace:/home/devuser/project" \
  -p 8000:8000 \
  cli-env:cc
```

## Attacker Server

`attacker_server/` builds a separate image that hosts two Flask services:

- port `8080`: serves the IPI dataset HTML test pages (`data/ipi_web_dataset/html_pages`);
- port `8081`: simulates the attacker/C&C endpoint and records incoming exfiltration requests.

```bash
bash docker_prep/attacker_server/build_docker.sh
```

Requires `git submodule update --init --recursive` so that the dataset HTML
pages are present.

## Runtime Language Toolchain Mounts (avoid image bloat)

`EnvironmentManager` supports mounting host-side language toolchains into
experiment containers at startup instead of baking them into the image.

1) Prepare host directories, one folder per language:

```text
/mnt/toolchains/
    python/
    javascript/
    c/
    cpp/
    java/
    typescript/
    rust/
    php/
    go/
    ruby/
```

If you do not have toolchains yet, download them first:

```bash
bash docker_prep/languages/download_toolchains.sh /mnt/toolchains python,javascript,c,cpp,java,typescript,rust,php,go,ruby
```

2) Generate and export the environment variables:

```bash
eval "$(bash docker_prep/languages/runtime_toolchains_env.sh /mnt/toolchains python,javascript,go,rust)"
```

Note: `runtime_toolchains_env.sh` validates key executables (e.g. `bin/python3`,
`bin/node`, `bin/go`), so empty directories are not mistakenly treated as enabled.

3) Start your experiment service; `EnvironmentManager` reads:

```text
RUNTIME_TOOLCHAIN_ROOT
RUNTIME_LANGUAGES
RUNTIME_MOUNT_STRICT
```

Optional variables:

```text
RUNTIME_MOUNT_MODE=ro|rw
RUNTIME_CONTAINER_ROOT=/opt/runtime-toolchains
RUNTIME_BASE_PATH=/opt/mitmproxy-env/bin:/home/devuser/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENT_TYPE` | `generic` | Agent identifier |
| `ENABLE_MITM` | `true` | Enable network tracing |
| `ENABLE_STRACE` | `false` | Enable syscall tracing |
| `MITM_PORT` | `8080` | mitmproxy port |
| `LOG_LEVEL` | `INFO` | Log level |

## Adding a New Agent

Create `agents/your_agent/Dockerfile.your_agent`:

```dockerfile
FROM cli-env

# Install the agent
USER root
RUN install-your-agent

# Configuration
USER devuser
COPY --chown=devuser:devuser .config /home/devuser/.config
WORKDIR /home/devuser/project

# Environment variables
ENV AGENT_TYPE=your-agent
ENV ENABLE_MITM=true
ENV ENABLE_STRACE=false

CMD ["/app/start_agent.sh"]
```

Then register the target in `build.sh`.

## Dependency Cache for Repeated prepare_env Runs

This repo includes an optional all-in-one dependency cache container under
`docker_prep/dependency_cache`. It is separate from the in-container
mitmproxy used to trace coding-agent API traffic.

Start it before the queue server/client:

```bash
bash docker_prep/dependency_cache/start_cache.sh
export ENABLE_DEPENDENCY_CACHE=true
export DEPENDENCY_CACHE_HOST=192.168.244.1
# optional, defaults to 7999 and keeps IDE http.proxy consistent
export MITM_PORT=7999
```

Then start your queue server/client normally. `EnvironmentManager` will
configure experiment containers with package-manager specific settings:

- Python/uv/pip -> devpi on `:3141`
- apt -> apt-cacher-ng on `:3142`
- npm/yarn/pnpm -> Verdaccio on `:4873`
- Go -> `GOPROXY=http://<host>:3010,direct`
- Maven/Gradle -> Maven Central cache on `:18082`
- Rust/Cargo -> crates.io sparse cache on `:18083`
- PHP/Composer -> Packagist metadata cache on `:18084`
- Ruby/Bundler -> RubyGems cache on `:9292`

The cache avoids port `8083` because that is the queue server default port,
and also avoids `8084/8085` because experiments use them as preferred host
ports for the HTML/attacker web server. You can override cache host ports with
`DEPENDENCY_CACHE_*_PORT` variables; keep the same variables exported when
starting experiments.

Do not point global `HTTP_PROXY`/`HTTPS_PROXY` at these cache endpoints. Those
variables remain reserved for the coding-agent API trace chain:

```text
agent -> container mitmproxy -> upstream internet proxy -> LLM API
```

The cache host is automatically added to `NO_PROXY` so package-manager calls
to the cache bypass mitmproxy and avoid SSL interception/certificate problems.
