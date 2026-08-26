# Codex CLI image

Set the codex env var before running the experiments of Codex:

```bash
export CODEX_API_KEY="your-api-key"
export CODEX_BASE_URL="https://your-compatible-endpoint/v1"
```

## Build the image
Enter `docker_prep/agents/codex`, then execute:

```bash
./docker_prep/agents/codex/build_image.sh
```

This will build the image `cli-env:codex`
