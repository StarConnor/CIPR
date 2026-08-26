# Claude Code CLI Image

## Local Configuration Files

Claude Code requires login when no local configuration is available. Before building
the image, copy your own Claude Code configuration files into this directory:

```text
docker_prep/agents/claude/.claude.json
docker_prep/agents/claude/.claude.json.backup
```

These files may contain login state, account information, or other sensitive data.
Do not commit or share them. The repository only documents the required filenames;
a fresh clone will not contain these files.

The build script checks that both files exist before starting the Docker build and
prints instructions if either file is missing.

## Example

If Claude Code uses its default configuration directory on your system, run:

```bash
cp ~/.claude.json docker_prep/agents/claude/.claude.json
cp ~/.claude.json.backup docker_prep/agents/claude/.claude.json.backup
```

Make sure these are your own files and adjust the source paths if necessary. Do not
paste their contents into the README, issues, or logs.

## Build

Enter `docker_prep/agents/claude/`, then execute:
```bash
./build_image.sh
```
