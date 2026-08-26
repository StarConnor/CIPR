#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash docker_prep/languages/download_toolchains.sh <runtime_root> [languages]

Examples:
  bash docker_prep/languages/download_toolchains.sh /mnt/toolchains
  bash docker_prep/languages/download_toolchains.sh /mnt/toolchains python,javascript,go,rust

Notes:
  1) This script uses docker images as source and exports runtimes to host folders.
  2) Output layout matches runtime mount checker: <runtime_root>/<language>/bin/*
EOF
}

normalize_language() {
  local raw
  raw="$(echo "$1" | tr '[:upper:]' '[:lower:]' | xargs)"
  case "$raw" in
    py) echo "python" ;;
    js|node) echo "javascript" ;;
    ts) echo "typescript" ;;
    golang) echo "go" ;;
    c++) echo "cpp" ;;
    rb) echo "ruby" ;;
    python|javascript|c|cpp|java|typescript|rust|php|go|ruby) echo "$raw" ;;
    *) echo "" ;;
  esac
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -lt 1 ]]; then
  usage
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker command not found" >&2
  exit 1
fi

runtime_root="$1"
languages_csv="${2:-python,javascript,c,cpp,java,typescript,rust,php,go,ruby}"
languages_csv="${languages_csv//;/,}"
task_version="${TASK_VERSION:-v3.45.4}"

mkdir -p "$runtime_root"

IFS=',' read -r -a requested <<< "$languages_csv"
languages=()

contains_lang() {
  local value="$1"
  for item in "${languages[@]:-}"; do
    if [[ "$item" == "$value" ]]; then
      return 0
    fi
  done
  return 1
}

for lang in "${requested[@]}"; do
  normalized="$(normalize_language "$lang")"
  if [[ -z "$normalized" ]]; then
    echo "Unsupported language: $lang" >&2
    exit 1
  fi
  if ! contains_lang "$normalized"; then
    languages+=("$normalized")
  fi
done

extract_from_image() {
  local image="$1"
  local out_dir="$2"
  local shell_cmd="$3"
  local clear_out="${4:-true}"
  local host_uid host_gid
  local cleanup_cmd
  local -a docker_env_args

  mkdir -p "$out_dir"
  if [[ "$clear_out" == "true" ]]; then
    cleanup_cmd="rm -rf /out/*"
  else
    cleanup_cmd="mkdir -p /out"
  fi

  host_uid="$(id -u)"
  host_gid="$(id -g)"

  docker_env_args=(
    -e HOST_UID="$host_uid"
    -e HOST_GID="$host_gid"
  )

  for proxy_var in \
    http_proxy https_proxy no_proxy \
    HTTP_PROXY HTTPS_PROXY NO_PROXY \
    GOPROXY GOSUMDB GOPRIVATE GONOSUMDB GOPROXY_FALLBACK; do
    if [[ -n "${!proxy_var:-}" ]]; then
      docker_env_args+=( -e "$proxy_var=${!proxy_var}" )
    fi
  done

  docker run --rm \
    "${docker_env_args[@]}" \
    -v "$out_dir:/out" \
    "$image" \
    sh -lc "set -e
$cleanup_cmd
$shell_cmd
chown -R \"\$HOST_UID:\$HOST_GID\" /out"
}

install_python() {
  local out_dir="$runtime_root/python"
  extract_from_image "python:3.12-bookworm" "$out_dir" '
    mkdir -p /out/bin /out/lib /out/include
    python -m pip install --no-cache-dir uv >/dev/null 2>&1 || true
    cp -a /usr/local/bin/python* /out/bin/
    cp -a /usr/local/bin/uv /out/bin/ || true
    cp -a /usr/local/lib/python* /out/lib/
    cp -a /usr/local/lib/libpython*.so* /out/lib/ || true
    cp -a /usr/local/include/python* /out/include/ || true

  # Make pip entrypoints relocatable; copied scripts often hardcode /usr/local/bin/pythonX.Y
    cat >/out/bin/pip <<"EOF"
#!/usr/bin/env sh
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
export LD_LIBRARY_PATH="$SCRIPT_DIR/../lib:$SCRIPT_DIR/../lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$SCRIPT_DIR/python3" -m pip "$@"
EOF
    cat >/out/bin/pip3 <<"EOF"
#!/usr/bin/env sh
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
export LD_LIBRARY_PATH="$SCRIPT_DIR/../lib:$SCRIPT_DIR/../lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$SCRIPT_DIR/python3" -m pip "$@"
EOF
  cat >/out/bin/pip3.12 <<"EOF"
#!/usr/bin/env sh
SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
export LD_LIBRARY_PATH="$SCRIPT_DIR/../lib:$SCRIPT_DIR/../lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
exec "$SCRIPT_DIR/python3" -m pip "$@"
EOF
  chmod +x /out/bin/pip /out/bin/pip3 /out/bin/pip3.12
  '
}

install_javascript() {
  local out_dir="$runtime_root/javascript"
  extract_from_image "node:22-bookworm" "$out_dir" '
    # Install package managers
    npm install -g yarn@latest pnpm@latest --force >/dev/null 2>&1
    # Download the fnm static binary
    https_proxy=http://10.214.99.83:7897 curl -fsSL https://fnm.vercel.app/install | bash -s -- --install-dir /tmp/fnm-bin --skip-shell 2>/dev/null || true
    if [ -f /tmp/fnm-bin/fnm ]; then
      mkdir -p /out/bin
      cp -a /tmp/fnm-bin/fnm /out/bin/fnm
    fi
    
    # Install dev tools
    npm install -g tsx@latest nodemon@latest --force >/dev/null 2>&1
    
    mkdir -p /out/bin /out/lib
    
    # Copy binaries
    for bin in node npm npx yarn yarnpkg pnpm corepack tsx nodemon; do
      if [ -f "/usr/local/bin/$bin" ]; then
        cp -a "/usr/local/bin/$bin" /out/bin/
      fi
    done
    
    cp -a /usr/local/lib/node_modules /out/lib/
  '
}

install_typescript() {
  local out_dir="$runtime_root/typescript"
  extract_from_image "node:22-bookworm" "$out_dir" '
    npm install -g typescript@latest yarn@latest pnpm@latest tsx@latest --force >/dev/null 2>&1
    # Download the fnm static binary
    https_proxy=http://10.214.99.83:7897 curl -fsSL https://fnm.vercel.app/install | bash -s -- --install-dir /tmp/fnm-bin --skip-shell 2>/dev/null || true
    if [ -f /tmp/fnm-bin/fnm ]; then
      mkdir -p /out/bin
      cp -a /tmp/fnm-bin/fnm /out/bin/fnm
    fi
    
    mkdir -p /out/bin /out/lib
    cp -a /usr/local/bin/node /out/bin/
    
    # Copy all package managers
    for bin in npm npx yarn yarnpkg pnpm corepack tsx; do
      [ -f "/usr/local/bin/$bin" ] && cp -a "/usr/local/bin/$bin" /out/bin/
    done
    
    cp -a /usr/local/lib/node_modules /out/lib/
    
    # Create TypeScript symlinks
    ln -sf ../lib/node_modules/typescript/bin/tsc /out/bin/tsc
    ln -sf ../lib/node_modules/typescript/bin/tsserver /out/bin/tsserver
  '
}

install_java() {
  local out_dir="$runtime_root/java"

  extract_from_image "eclipse-temurin:21-jdk" "$out_dir" '
    mkdir -p /out
    cp -a /opt/java/openjdk/* /out/
  '

  extract_from_image "maven:3.9-eclipse-temurin-21" "$out_dir" '
    mvn_bin="$(command -v mvn || true)"
    if [ -z "$mvn_bin" ]; then
      echo "mvn not found in maven image" >&2
      exit 1
    fi

    mvn_real="$(readlink -f "$mvn_bin")"
    maven_home="$(dirname "$(dirname "$mvn_real")")"

    mkdir -p /out/tools /out/bin
    cp -a "$maven_home" /out/tools/maven
    ln -sfn ../tools/maven/bin/mvn /out/bin/mvn
  ' "false"

  extract_from_image "gradle:jdk21" "$out_dir" '
    gradle_bin="$(command -v gradle || true)"
    if [ -z "$gradle_bin" ]; then
      echo "gradle not found in gradle image" >&2
      exit 1
    fi

    gradle_real="$(readlink -f "$gradle_bin")"
    gradle_home="$(dirname "$(dirname "$gradle_real")")"

    mkdir -p /out/tools/gradle /out/bin
    cp -a "$gradle_home" /out/tools/gradle/
    ln -sfn ../tools/gradle/"$(basename "$gradle_home")"/bin/gradle /out/bin/gradle
  ' "false"
}

install_rust() {
  local out_dir="$runtime_root/rust"
  extract_from_image "rust:1.95-bookworm" "$out_dir" '
    mkdir -p /out
    
    # Install components
    rustup component add rustfmt clippy 2>/dev/null || true
    
    # Copy directories (copied as-is to keep the existing correct settings.toml)
    cp -a /usr/local/cargo /out/
    cp -a /usr/local/rustup /out/
    
    # Create symlinks
    mkdir -p /out/bin
    ln -sf ../cargo/bin/cargo /out/bin/cargo
    ln -sf ../cargo/bin/rustc /out/bin/rustc
    for tool in rustfmt clippy-driver cargo-clippy; do
      tool_path="/usr/local/cargo/bin/$tool"
      if [ -e "$tool_path" ]; then
        cp -L "$tool_path" "/out/bin/$tool" 2>/dev/null || true
      fi
    done
  '
}

install_php() {
  local out_dir="$runtime_root/php"

  extract_from_image "composer:2" "$out_dir" '
    mkdir -p /out/bin
    cp -a /usr/bin/composer /out/bin/composer
  ' "false"
}

install_go() {
  local out_dir="$runtime_root/go"
  extract_from_image "golang:1.22-bookworm" "$out_dir" '
    export PATH="/usr/local/go/bin:$PATH"
    export GOBIN="/tmp/go-bin"
    mkdir -p "$GOBIN"

    if [ -n "${GOPROXY_FALLBACK:-}" ] && [ -z "${GOPROXY:-}" ]; then
      export GOPROXY="$GOPROXY_FALLBACK"
    fi

    task_archive_url="https://github.com/go-task/task/releases/download/'"$task_version"'/task_linux_amd64.tar.gz"

    if command -v curl >/dev/null 2>&1; then
      curl -fsSL "$task_archive_url" -o /tmp/task.tgz
    else
      apt-get update >/dev/null 2>&1
      DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends curl ca-certificates >/dev/null 2>&1
      rm -rf /var/lib/apt/lists/*
      curl -fsSL "$task_archive_url" -o /tmp/task.tgz
    fi

    tar -xzf /tmp/task.tgz -C "$GOBIN" task
    chmod +x "$GOBIN/task"

    if [ ! -x "$GOBIN/task" ]; then
      echo "task binary not found after download" >&2
      exit 1
    fi

    mkdir -p /out
    cp -a /usr/local/go/* /out/
    mkdir -p /out/bin
    cp -L "$GOBIN/task" /out/bin/task
  '
}

install_g_golang() {
  local out_dir="$runtime_root/go"
  extract_from_image "golang:1.22-bookworm" "$out_dir" '
    https_proxy=http://10.214.99.83:7897 curl -fsSL https://raw.githubusercontent.com/stefanmaric/g/refs/heads/next/bin/g -o /tmp/g
    chmod +x /tmp/g
    mkdir -p /out/bin
    cp /tmp/g /out/bin/g
  ' "false"
}

install_ruby() {
  local out_dir="$runtime_root/ruby"
  
  # We may need git to fetch rbenv, so install git inside the docker container first
  extract_from_image "ruby:3.3-bookworm" "$out_dir" '
    # Install base dependencies to download rbenv
    apt-get update -qq && apt-get install -y git curl >/dev/null 2>&1 || true

    # 1. Copy the native Ruby directories
    for dir in bin lib include share; do
      if [ -d "/usr/local/$dir" ]; then
        mkdir -p "/out/$(dirname $dir)"
        cp -a "/usr/local/$dir" "/out/"
      fi
    done
    
    # Fix the shebang lines of the bundled tools
    for bin in ruby gem bundle bundler irb rake erb rdoc; do
      if [ -f "/usr/local/bin/$bin" ]; then
        if [ "$bin" != "ruby" ]; then
          sed -i "s|^#!/usr/local/bin/ruby|#!/usr/bin/env ruby|g" "/out/bin/$bin"
        fi
      fi
    done
    
    if [ -f /out/lib/libruby.so.3.3 ]; then
      ln -sf libruby.so.3.3 /out/lib/libruby.so 2>/dev/null || true
    fi

    # ========================================================
    # 2. Install and integrate the environment management tool rbenv
    # ========================================================
    mkdir -p /out/rbenv
    
    # Clone rbenv and its build plugin ruby-build
    https_proxy=http://10.214.99.83:7897 git clone https://github.com/rbenv/rbenv.git /out/rbenv
    https_proxy=http://10.214.99.83:7897 git clone https://github.com/rbenv/ruby-build.git /out/rbenv/plugins/ruby-build
    
    # Remove .git directories to reduce size
    rm -rf /out/rbenv/.git /out/rbenv/plugins/ruby-build/.git
    
    # Expose the rbenv command in the global bin directory
    ln -sf ../rbenv/bin/rbenv /out/bin/rbenv

    # ========================================================
    # 3. [Trick] Disguise the extracted 3.3.0 as an rbenv-installed version
    # ========================================================
    mkdir -p /out/rbenv/versions
    
    # Use a relative path for the symlink: point rbenv/versions/3.3.0 at the /out root.
    # No matter where this bundle is mounted inside a container later, the relative link will never break!
    ln -sf ../.. /out/rbenv/versions/3.3.0
  '
}

install_c_cpp_bundle() {
  local out_dir="$1"
  extract_from_image "gcc:11-bullseye" "$out_dir" '
    apt-get update >/dev/null 2>&1
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends cmake make ninja-build pkg-config >/dev/null 2>&1
    rm -rf /var/lib/apt/lists/*
    mkdir -p /out/bin
    gcc_bin="$(command -v gcc || true)"
    gpp_bin="$(command -v g++ || true)"

    if [ -z "$gcc_bin" ] || [ -z "$gpp_bin" ]; then
      echo "gcc or g++ not found in image" >&2
      exit 1
    fi

    cp -L "$gcc_bin" /out/bin/gcc
    cp -L "$gpp_bin" /out/bin/g++
    ln -sf gcc /out/bin/cc
    ln -sf g++ /out/bin/c++

    for tool in cmake make ninja pkg-config; do
      tool_path="$(command -v "$tool" || true)"
      if [ -n "$tool_path" ]; then
        cp -L "$tool_path" "/out/bin/$tool"
      fi
    done
  '
}

need_c=false
need_cpp=false
for language in "${languages[@]}"; do
  case "$language" in
    c) need_c=true ;;
    cpp) need_cpp=true ;;
  esac
done

for language in "${languages[@]}"; do
  case "$language" in
    python)
      echo "[download] preparing python..."
      install_python
      ;;
    javascript)
      echo "[download] preparing javascript..."
      install_javascript
      ;;
    typescript)
      echo "[download] preparing typescript..."
      install_typescript
      ;;
    java)
      echo "[download] preparing java..."
      install_java
      ;;
    rust)
      echo "[download] preparing rust..."
      install_rust
      ;;
    php)
      echo "[download] preparing php..."
      install_php
      ;;
    go)
      echo "[download] preparing go..."
      install_go
      install_g_golang
      ;;
    ruby)
      echo "[download] preparing ruby..."
      install_ruby
      ;;
    c|cpp)
      # handled in a shared bundle step below
      ;;
  esac
done

if [[ "$need_c" == true ]]; then
  echo "[download] preparing c..."
  install_c_cpp_bundle "$runtime_root/c"
fi

if [[ "$need_cpp" == true ]]; then
  if [[ "$need_c" == true ]]; then
    rm -rf "$runtime_root/cpp"
    ln -sfn "$runtime_root/c" "$runtime_root/cpp"
  else
    echo "[download] preparing cpp..."
    install_c_cpp_bundle "$runtime_root/cpp"
  fi
fi

echo "[download] done. generated root: $runtime_root"