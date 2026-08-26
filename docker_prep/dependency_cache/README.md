# Dependency cache container

All-in-one cache/proxy container for repeated `prepare_env` runs. It is intentionally separate from the in-container mitmproxy used for coding-agent API tracing.

Build and start:

```bash
bash docker_prep/dependency_cache/start_cache.sh
```

Then enable client-side configuration before starting queue_server/client:

```bash
export ENABLE_DEPENDENCY_CACHE=true
export DEPENDENCY_CACHE_HOST=192.168.244.1
```

Smoke test the cache endpoints:

```bash
bash docker_prep/dependency_cache/test_cache.sh --host 192.168.244.1
```

To verify the endpoints are reachable from a Docker container, use:

```bash
bash docker_prep/dependency_cache/test_cache.sh --docker --host 192.168.244.1
```

Ports:

- `3141`: devpi, Python simple index: `http://<host>:3141/root/pypi/+simple`
- `3142`: apt-cacher-ng
- `4873`: Verdaccio npm registry
- `3010`: nginx cache for `goproxy.cn`
- `18082`: nginx cache for Maven Central
- `18083`: nginx cache for crates.io sparse index
- `18084`: nginx cache for Packagist metadata
- `9292`: nginx cache for RubyGems

Notes:

- Do not set global `HTTP_PROXY`/`HTTPS_PROXY` to these endpoints. Those variables are reserved for the container-local mitmproxy trace chain.
- The experiment container configuration writes package-manager specific settings and adds `DEPENDENCY_CACHE_HOST` to `NO_PROXY`, so calls to cache services bypass mitmproxy and avoid TLS interception/certificate issues.
- Some package ecosystems still download source archives from GitHub or other hosts; those downloads may not be fully cached by this lightweight container.
- The cache intentionally avoids host ports `8083`, `8084`, and `8085`, which are used by the queue server and experiment web/attacker servers in this project.
- Host ports can be overridden with `DEPENDENCY_CACHE_*_PORT`, for example `DEPENDENCY_CACHE_CARGO_PORT=28083`. Use the same env var when starting experiments so `EnvironmentManager` injects matching client URLs.
