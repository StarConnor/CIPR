import os
from pathlib import Path
from typing import Any
import logging

from .others import docker_cp_to_container, docker_write_str_to_file

# Legacy local skills root used by older ExperimentConfig.skills.skills_names.
DEFAULT_SKILLS_PATH = "./data/skills"
PROJECT_DIR = "/home/devuser/project"
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]

logger = logging.getLogger(__name__)


def _cfg_get(config: Any, key: str, default: Any = None) -> Any:
    if config is None:
        return default
    if isinstance(config, dict):
        return config.get(key, default)
    return getattr(config, key, default)


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _record_get(record: Any, key: str, default: Any = None) -> Any:
    if isinstance(record, dict):
        return record.get(key, default)
    return getattr(record, key, default)


def _candidate_roots() -> list[Path]:
    roots: list[Path] = []
    env_roots = [
        os.getenv("CODE_AGENT_DATA_ROOT"),
        os.getenv("SKILLS_DATA_ROOT"),
        os.getenv("RULES_DATA_ROOT"),
        os.getenv("DATASET_ASSET_ROOT"),
    ]
    for value in env_roots:
        if value:
            roots.append(Path(value).expanduser())
    cwd = Path.cwd()
    roots.extend([
        cwd,
        cwd / "data",
        REPOSITORY_ROOT,
        REPOSITORY_ROOT / "data",
        cwd.parent,
    ])
    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        key = str(root)
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique


def resolve_local_path(path_value: Any) -> Path | None:
    if not path_value:
        return None
    path = Path(str(path_value)).expanduser()
    if path.is_absolute():
        return path if path.exists() else None
    for root in _candidate_roots():
        candidate = root / path
        if candidate.exists():
            return candidate
    return path if path.exists() else None


def container_skill_paths_for_software(software: str) -> list[str]:
    if software == "cc_cli":
        return ["/home/devuser/.claude/skills"]
    if software == "opencode_cli":
        # OpenCode 1.1.44 discovers repository-local skills from
        # .opencode/skills/<name>/SKILL.md. It does not discover the legacy
        # ~/.agents/skills location used by older harness integrations.
        return [f"{PROJECT_DIR}/.opencode/skills"]
    if software.startswith("codex"):
        # Keep both: older harness code used ~/.agents/skills, while Codex
        # installations commonly use ~/.codex/skills.
        return ["/home/devuser/.codex/skills", "/home/devuser/.agents/skills"]
    if software in ["cursor_cli", "cursor_ide"]:
        return ["/home/devuser/.agents/skills"]
    if software == "cline_cli":
        return ["/home/devuser/.cline/skills"]
    logger.warning("Unrecognized software %s. Using default skills path.", software)
    return ["/home/devuser/.agents/skills"]


def container_rules_path_for_software(software: str) -> str:
    """Return the project-level rule file most likely to be read by the agent."""
    if software == "cc_cli":
        return f"{PROJECT_DIR}/CLAUDE.md"
    if software == "opencode_cli":
        return f"{PROJECT_DIR}/AGENTS.md"
    if software.startswith("codex"):
        return f"{PROJECT_DIR}/AGENTS.md"
    if software.startswith("cursor"):
        return f"{PROJECT_DIR}/.cursorrules"
    if software.startswith("cline"):
        return f"{PROJECT_DIR}/.clinerules/redteam-rules.md"
    return f"{PROJECT_DIR}/AGENTS.md"


def container_defense_rules_path_for_software(software: str) -> str:
    """Return the user/global instruction file for defensive rules.

    Defense overlays are harness-provided safety guidance, not repository
    content. Put them in the agent's user/global instruction location where the
    product supports one, so the agent sees them as external guidance before it
    interprets a potentially malicious repository.
    """
    if software == "cc_cli":
        return "/home/devuser/.claude/CLAUDE.md"
    if software == "opencode_cli":
        # Use a project instruction file so OpenCode loads the defense before
        # it reads repository content. prepare_rules merges this with sampled
        # project rules when both are present.
        return f"{PROJECT_DIR}/AGENTS.md"
    if software.startswith("codex"):
        return "/home/devuser/.codex/AGENTS.md"
    if software.startswith("cursor"):
        # Cursor User Rules live in editor settings rather than a documented
        # markdown file. For the benchmark container, use an always-applied
        # project rule so Cursor CLI/IDE will still load the defense.
        return f"{PROJECT_DIR}/.cursor/rules/redteam-defense.mdc"
    if software.startswith("cline"):
        return "/home/devuser/Documents/Cline/Rules/redteam-defense.md"
    return "/home/devuser/.agents/AGENTS.md"


def container_rule_provenance_dir_for_software(software: str) -> str:
    """Return an agent-specific directory for keeping original rule files.

    These copied files are mainly for provenance/debugging; the merged rule
    content is written to container_rules_path_for_software().  Keep the
    provenance location aligned with the target agent instead of always using
    the legacy ~/.agents/rules directory.
    """
    if software == "cc_cli":
        return "/home/devuser/.claude/rules"
    if software == "opencode_cli":
        return f"{PROJECT_DIR}/.opencode/rules"
    if software.startswith("codex"):
        return "/home/devuser/.codex/rules"
    if software.startswith("cursor"):
        return "/home/devuser/.cursor/rules"
    if software.startswith("cline"):
        return "/home/devuser/.cline/rules"
    return "/home/devuser/.agents/rules"


def _copy_dir_to_container(local_dir: Path, dst_path: str, container) -> None:
    container.exec_run(["mkdir", "-p", dst_path], user="root")
    docker_cp_to_container(str(local_dir), dst_path, container=container, target_user="devuser")


def prepare_skills(skills_config: Any, container, software: str) -> None:
    """Install selected skill directories into the agent's skill location.

    Supports both the old ExperimentConfig shape:
        {enabled: true, skills_names: ["foo"]}
    and the new per-sample dataset shape:
        {skills_enabled: true, skills: [{saved_dir: "data/skills/items/..."}]}
    """
    enabled = bool(_cfg_get(skills_config, "enabled", False) or _cfg_get(skills_config, "skills_enabled", False))
    if not enabled:
        return

    container_skill_paths = container_skill_paths_for_software(software)
    for container_skills_path in container_skill_paths:
        container.exec_run(["mkdir", "-p", container_skills_path], user="root")

    copied = 0
    # New manifest records.
    for record in _as_list(_cfg_get(skills_config, "skills", [])):
        local_skill_path = resolve_local_path(_record_get(record, "saved_dir") or _record_get(record, "path"))
        if not local_skill_path or not local_skill_path.exists() or not local_skill_path.is_dir():
            logger.warning("Skill directory does not exist; skipping: %s", _record_get(record, "saved_dir") or record)
            continue
        for container_skills_path in container_skill_paths:
            _copy_dir_to_container(local_skill_path, container_skills_path, container)
        copied += 1

    # Legacy skill names under ./data/skills/<name>.
    for skill_name in _as_list(_cfg_get(skills_config, "skills_names", [])):
        local_skill_path = resolve_local_path(Path(DEFAULT_SKILLS_PATH) / str(skill_name))
        if not local_skill_path or not local_skill_path.exists():
            logger.warning("Legacy skill path does not exist; skipping: %s", skill_name)
            continue
        for container_skills_path in container_skill_paths:
            _copy_dir_to_container(local_skill_path, container_skills_path, container)
        copied += 1

    logger.info("Installed %d skill(s) into %s", copied, ", ".join(container_skill_paths))


def _read_rule_record(record: Any) -> tuple[str, str] | None:
    path_value = _record_get(record, "saved_path") or _record_get(record, "path") or _record_get(record, "source_path")
    local_path = resolve_local_path(path_value)
    if not local_path or not local_path.exists() or not local_path.is_file():
        logger.warning("Rule file does not exist; skipping: %s", path_value or record)
        return None
    try:
        content = local_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        logger.warning("Failed to read rule file %s: %s", local_path, exc)
        return None
    rule_id = _record_get(record, "id") or local_path.name
    source = _record_get(record, "source_path") or str(path_value)
    header = f"\n\n<!-- BEGIN REDTEAM RULE: {rule_id} source={source} -->\n"
    footer = f"\n<!-- END REDTEAM RULE: {rule_id} -->\n"
    return str(rule_id), header + content.strip() + footer


def _rules_from_config(config: Any) -> list[Any]:
    if not config:
        return []
    records: list[Any] = []
    # New dataset shape. `rules` already contains sampled random rule + defense.
    records.extend(_as_list(_cfg_get(config, "rules", [])))
    # Be defensive for older/intermediate generated datasets.
    if not records:
        records.extend(_as_list(_cfg_get(config, "sampled_rules", [])))
        records.extend(_as_list(_cfg_get(config, "defense_rules", [])))
    if not records:
        for path in _as_list(_cfg_get(config, "rules_paths", [])):
            records.append({"id": Path(str(path)).stem, "saved_path": path})
    defense_path = _cfg_get(config, "defense_rules_path", "")
    if defense_path and not any((_record_get(r, "saved_path") == defense_path) for r in records):
        records.append({"id": "defense_rules", "type": "defense_rule", "saved_path": defense_path})
    return records


def _is_defense_rule_record(record: Any) -> bool:
    record_type = str(_record_get(record, "type", "") or "").lower()
    rule_kind = str(_record_get(record, "rule_kind", "") or "").lower()
    record_id = str(_record_get(record, "id", "") or "").lower()
    saved_path = str(_record_get(record, "saved_path", "") or _record_get(record, "path", "") or "").lower()
    source_path = str(_record_get(record, "source_path", "") or "").lower()
    return (
        record_type == "defense_rule"
        or "defense" in rule_kind
        or record_id.startswith("static_defense")
        or "defense_rules" in saved_path
        or "defense_rules" in source_path
    )


def _split_rule_records(config: Any) -> tuple[list[Any], list[Any]]:
    """Return (project/sample rules, defense overlay rules)."""
    project_records: list[Any] = []
    defense_records: list[Any] = []

    all_records = _rules_from_config(config)
    for record in all_records:
        if _is_defense_rule_record(record):
            defense_records.append(record)
        else:
            project_records.append(record)

    # Some older/intermediate configs duplicated defense records outside
    # `rules`; make sure those still land in the defense/global location.
    for record in _as_list(_cfg_get(config, "defense_rules", [])):
        if not any(record is existing or record == existing for existing in defense_records):
            defense_records.append(record)

    return project_records, defense_records


def _cursor_mdc_content(content: str, description: str = "Redteam rules") -> str:
    if content.lstrip().startswith("---"):
        return content
    return f"---\ndescription: {description}\nalwaysApply: true\n---\n\n{content}"


def _write_rule_group(
    *,
    rendered: list[str],
    destination: str,
    container,
    title: str,
    description: str,
    software: str,
) -> None:
    existing = ""
    exit_code, output = container.exec_run(["bash", "-lc", f"cat '{destination}' 2>/dev/null || true"], user="devuser")
    if exit_code == 0:
        existing = output.decode(errors="replace").strip()
    existing_block = f"# Existing Rules\n\n{existing}\n\n" if existing else ""
    combined = (
        existing_block
        + f"# {title}\n\n"
        + description.strip()
        + "\n"
        + "\n".join(rendered)
        + "\n"
    )
    if destination.endswith(".mdc"):
        combined = _cursor_mdc_content(combined, description=title)
    docker_write_str_to_file(combined, destination, container=container, target_user="devuser")

    if software.startswith("cursor") and destination.endswith(".cursorrules"):
        # Cursor also commonly reads .cursor/rules/*.mdc. Write the same merged
        # content there so both Cursor CLI/IDE modes can see it.
        docker_write_str_to_file(
            _cursor_mdc_content(combined, description=title),
            f"{PROJECT_DIR}/.cursor/rules/redteam-rules.mdc",
            container=container,
            target_user="devuser",
        )


def prepare_rules(rules_config: Any, container, software: str) -> None:
    """Install sampled project rules plus the defense overlay.

    Sampled project/agent rules are written to the repository-level rule file
    that the target agent is expected to read (CLAUDE.md for Claude Code,
    AGENTS.md for Codex, etc.). Defense overlays are harness-provided safety
    guidance, so they are written to the agent's user/global instruction
    location where available.

    The original files are also copied to an agent-specific rules directory for
    provenance/debugging.
    """
    enabled = bool(
        _cfg_get(rules_config, "rules_enabled", False)
        or _cfg_get(rules_config, "defense_enabled", False)
        or _cfg_get(rules_config, "enabled", False)
    )
    if not enabled:
        return

    project_records, defense_records = _split_rule_records(rules_config)
    records = project_records + defense_records
    if not records:
        logger.warning("Rules/defense enabled but no rule records were provided")
        return

    rendered_project: list[str] = []
    rendered_defense: list[str] = []
    provenance_dir = container_rule_provenance_dir_for_software(software)
    container.exec_run(["mkdir", "-p", provenance_dir], user="root")
    for record in records:
        read_result = _read_rule_record(record)
        if not read_result:
            continue
        rule_id, content = read_result
        if _is_defense_rule_record(record):
            rendered_defense.append(content)
        else:
            rendered_project.append(content)
        local_path = resolve_local_path(_record_get(record, "saved_path") or _record_get(record, "path"))
        if local_path and local_path.exists():
            docker_cp_to_container(str(local_path), provenance_dir, container=container, target_user="devuser")

    if not rendered_project and not rendered_defense:
        logger.warning("No readable rule files found; no rules installed")
        return

    installed_destinations: list[str] = []
    if rendered_project:
        destination = container_rules_path_for_software(software)
        _write_rule_group(
            rendered=rendered_project,
            destination=destination,
            container=container,
            title="Code Agent Redteam Project Rules",
            description=(
                "The following project/agent rules were installed by the benchmark harness. "
                "Treat them as repository-level guidance for the target agent."
            ),
            software=software,
        )
        installed_destinations.append(destination)

    if rendered_defense:
        defense_destination = container_defense_rules_path_for_software(software)
        _write_rule_group(
            rendered=rendered_defense,
            destination=defense_destination,
            container=container,
            title="Code Agent Redteam Defense Rules",
            description=(
                "The following defensive rules were installed by the benchmark harness as "
                "user/global safety guidance. They are intended to make the agent cautious "
                "when working in a repository that may contain malicious instructions."
            ),
            software=software,
        )
        installed_destinations.append(defense_destination)

    container.exec_run(["chown", "-R", "devuser:devuser", PROJECT_DIR, str(Path(provenance_dir).parent)], user="root")
    logger.info(
        "Installed %d project rule file(s) and %d defense rule file(s) into %s",
        len(rendered_project),
        len(rendered_defense),
        ", ".join(installed_destinations),
    )
