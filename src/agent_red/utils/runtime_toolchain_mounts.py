import os
import pdb
from typing import Any, Dict, Iterable, List, Sequence


SUPPORTED_LANGUAGES: tuple[str, ...] = (
    "python",
    "javascript",
    "c",
    "cpp",
    "java",
    "typescript",
    "rust",
    "php",
    "go",
    "ruby",
)

LANGUAGE_ALIASES: dict[str, str] = {
    "py": "python",
    "js": "javascript",
    "node": "javascript",
    "ts": "typescript",
    "golang": "go",
    "c++": "cpp",
    "rb": "ruby",
}

DEFAULT_RUNTIME_CONTAINER_ROOT = "/opt/runtime-toolchains"
DEFAULT_RUNTIME_BASE_PATH = "/opt/mitmproxy-env/bin:/home/devuser/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

# Each inner list is an AND group; groups are OR-ed.
TOOLCHAIN_BINARY_GROUPS: dict[str, list[list[str]]] = {
    "python": [["bin/python3", "bin/uv"], ["bin/python", "bin/uv"]],
    "javascript": [["bin/node"]],
    "typescript": [["bin/tsc", "bin/node"]],
    "c": [["bin/gcc", "bin/cmake", "bin/make", "bin/ninja", "bin/pkg-config"], ["bin/clang", "bin/cmake", "bin/make", "bin/ninja", "bin/pkg-config"]],
    "cpp": [["bin/g++", "bin/cmake", "bin/make", "bin/ninja", "bin/pkg-config"], ["bin/clang++", "bin/cmake", "bin/make", "bin/ninja", "bin/pkg-config"]],
    "java": [["bin/java", "bin/javac", "bin/mvn", "bin/gradle"]],
    "rust": [["cargo/bin/rustc", "cargo/bin/cargo", "cargo/bin/rustfmt", "cargo/bin/clippy-driver"], ["bin/rustc", "bin/cargo", "bin/rustfmt", "bin/clippy-driver"]],
    "php": [["bin/composer"]],
    "go": [["bin/go", "bin/task"]],
    "ruby": [["bin/ruby"]],
}


def parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _iter_language_tokens(raw_languages: Any) -> Iterable[str]:
    if raw_languages is None:
        return

    if isinstance(raw_languages, str):
        for token in raw_languages.replace(";", ",").split(","):
            stripped = token.strip()
            if stripped:
                yield stripped
        return

    if isinstance(raw_languages, Sequence):
        for item in raw_languages:
            if isinstance(item, str):
                for token in item.replace(";", ",").split(","):
                    stripped = token.strip()
                    if stripped:
                        yield stripped


def normalize_runtime_languages(raw_languages: Any) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()

    for token in _iter_language_tokens(raw_languages):
        key = token.strip().lower()
        key = LANGUAGE_ALIASES.get(key, key)
        if key not in SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Unsupported runtime language '{token}'. Supported: {', '.join(SUPPORTED_LANGUAGES)}"
            )
        if key not in seen:
            seen.add(key)
            normalized.append(key)
    return normalized


def _is_toolchain_ready(host_path: str, language: str) -> bool:
    groups = TOOLCHAIN_BINARY_GROUPS.get(language)
    if not groups:
        return os.path.isdir(host_path)

    for group in groups:
        if all(os.path.isfile(os.path.join(host_path, rel_path)) for rel_path in group):
            return True
    return False


def _build_language_env_vars(language: str, container_path: str) -> Dict[str, str]:
    language_key = language.upper()
    env_vars: Dict[str, str] = {
        f"RUNTIME_{language_key}_ROOT": container_path,
    }

    if language == "java":
        env_vars["JAVA_HOME"] = container_path
        env_vars["MAVEN_HOME"] = f"{container_path}/tools/maven"
        env_vars["GRADLE_HOME"] = f"{container_path}/tools/gradle"
        env_vars["MAVEN_USER_HOME"] = "/home/devuser/.m2"
        env_vars["GRADLE_USER_HOME"] = "/home/devuser/.gradle"
    elif language == "go":
        env_vars["GOROOT"] = container_path
        env_vars["GOPATH"] = "/home/devuser/go"
        env_vars["GOMODCACHE"] = "/home/devuser/go/pkg/mod"
        env_vars["GOCACHE"] = "/home/devuser/.cache/go-build"
    elif language == "rust":
        env_vars["RUSTUP_HOME"] = "/home/devuser/.rustup"
        env_vars["CARGO_HOME"] = "/home/devuser/.cargo"
    elif language == "php":
        env_vars["COMPOSER_HOME"] = "/home/devuser/composer"
    elif language == "ruby":
        # The runtime toolchain is usually bind-mounted read-only and may be
        # root-owned.  Keep Ruby itself on the mounted path, but direct all
        # mutable RubyGems/Bundler/rbenv state to /home/devuser.  Otherwise
        # commands such as `gem install`, `bundle install`, or rbenv shim
        # generation can fail with EACCES under ~/.bundle or the mounted
        # toolchain tree.
        user_gem_home = "/home/devuser/.gem/ruby/3.3.0"
        readonly_gem_home = f"{container_path}/lib/ruby/gems/3.3.0"
        env_vars["GEM_HOME"] = user_gem_home
        env_vars["GEM_PATH"] = f"{user_gem_home}:{readonly_gem_home}"
        env_vars["GEM_SPEC_CACHE"] = "/home/devuser/.gem/specs"
        env_vars["BUNDLE_PATH"] = "/home/devuser/.bundle/vendor"
        env_vars["BUNDLE_CACHE_PATH"] = "/home/devuser/.bundle/cache"
        env_vars["BUNDLE_APP_CONFIG"] = "/home/devuser/.bundle"
        env_vars["BUNDLE_USER_HOME"] = "/home/devuser/.bundle"
        env_vars["RBENV_ROOT"] = "/home/devuser/.rbenv"

        # Additionally set the RUBYLIB environment variable so Ruby can find the standard library
        # and C extension libraries in dynamically mounted paths.
        # Include both x86_64 and aarch64 for cross-platform compatibility.
        ruby_lib_paths =[
            f"{container_path}/lib/ruby/site_ruby/3.3.0",
            f"{container_path}/lib/ruby/site_ruby/3.3.0/x86_64-linux",
            f"{container_path}/lib/ruby/site_ruby/3.3.0/aarch64-linux",
            f"{container_path}/lib/ruby/vendor_ruby/3.3.0",
            f"{container_path}/lib/ruby/vendor_ruby/3.3.0/x86_64-linux",
            f"{container_path}/lib/ruby/vendor_ruby/3.3.0/aarch64-linux",
            f"{container_path}/lib/ruby/3.3.0",
            f"{container_path}/lib/ruby/3.3.0/x86_64-linux",
            f"{container_path}/lib/ruby/3.3.0/aarch64-linux",
        ]
        env_vars["RUBYLIB"] = ":".join(ruby_lib_paths)

    return env_vars


def _build_runtime_bin_paths(container_paths: Dict[str, str]) -> list[str]:
    runtime_bin_paths: list[str] = []
    for language, container_path in container_paths.items():
        runtime_bin_paths.append(f"{container_path}/bin")
        if language == "rust":
            runtime_bin_paths.append(f"{container_path}/cargo/bin")
    return runtime_bin_paths


def build_runtime_mount_config(
    runtime_root: str | None,
    runtime_languages: Any,
    container_root: str = DEFAULT_RUNTIME_CONTAINER_ROOT,
    mount_mode: str = "ro",
    strict: bool = False,
) -> Dict[str, Any]:
    normalized_languages = normalize_runtime_languages(runtime_languages)
    if not runtime_root or not normalized_languages:
        return {
            "volumes": {},
            "environment_vars": {},
            "enabled_languages": [],
            "missing_languages": normalized_languages,
            "runtime_bin_paths": [],
            "container_paths": {},
        }

    normalized_mode = (mount_mode or "ro").strip().lower()
    if normalized_mode not in {"ro", "rw"}:
        raise ValueError("runtime mount_mode must be either 'ro' or 'rw'")

    resolved_runtime_root = os.path.abspath(runtime_root)
    volumes: Dict[str, Dict[str, str]] = {}
    container_paths: Dict[str, str] = {}
    enabled_languages: list[str] = []
    missing_languages: list[str] = []

    for language in normalized_languages:
        host_path = os.path.join(resolved_runtime_root, language)
        if os.path.isdir(host_path) and _is_toolchain_ready(host_path, language):
            container_path = f"{container_root}/{language}"
            volumes[host_path] = {"bind": container_path, "mode": normalized_mode}
            container_paths[language] = container_path
            enabled_languages.append(language)
        else:
            missing_languages.append(language)

    if strict and missing_languages:
        missing = ", ".join(missing_languages)
        raise FileNotFoundError(
            f"Missing runtime toolchains under {resolved_runtime_root}: {missing}"
        )

    env_vars: Dict[str, str] = {
        "RUNTIME_TOOLCHAIN_ROOT": container_root,
        "RUNTIME_LANGUAGES": ",".join(normalized_languages),
        "RUNTIME_ENABLED_LANGUAGES": ",".join(enabled_languages),
        "RUNTIME_MISSING_LANGUAGES": ",".join(missing_languages),
    }

    for language, container_path in container_paths.items():
        env_vars.update(_build_language_env_vars(language, container_path))

    runtime_bin_paths = _build_runtime_bin_paths(container_paths)
    if runtime_bin_paths:
        env_vars["RUNTIME_BIN_PATHS"] = ":".join(runtime_bin_paths)

    return {
        "volumes": volumes,
        "environment_vars": env_vars,
        "enabled_languages": enabled_languages,
        "missing_languages": missing_languages,
        "runtime_bin_paths": runtime_bin_paths,
        "container_paths": container_paths,
    }