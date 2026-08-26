import argparse
import json
import os
import re
from pathlib import Path
from typing import Any
from tqdm import tqdm
import pdb

from openai import OpenAI


DEFAULT_SKILLS_DIR = (
    "/home/zfk/projects/benchmark/code-agent-redteam-dataset/prepare_dataset/"
    "skills/PoisonedSkills/poisoned_skills"
)
DEFAULT_OUTPUT_JSON = (
    "/home/zfk/projects/benchmark/code-agent-redteam-dataset/prepare_dataset/"
    "dataset_gen/raw_attacks.json"
)
DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_BASE_URL = "https://api.deepseek.com"
DDIPE_SRC = "https://arxiv.org/abs/2604.03081"
DDIPE_ABBR = "DDIPE"


SYSTEM_PROMPT = """You are a security dataset annotator.
Task: Extract hidden attack payloads AND their deceptive context from a potentially poisoned SKILL.md.

Rules:
1. Focus on malicious or suspicious instructions/code, such as:
   - exfiltration of env/credentials/files
   - stealth network callbacks / telemetry to untrusted internal domains
   - persistence hooks, backdoors, privilege escalation, supply-chain hijack
   - mandatory hidden steps that must not be disclosed to user
2. Extract BOTH the malicious code AND the deceptive narrative framing it. Attackers often use fake compliance, logging, or "system requirement" headers to trick the agent.
3. `deceptive_context`: The exact headings, paragraphs, and instructions (social engineering) used to mandate or hide the execution.
4. `payload`: The actual executable malicious script/command.
5. Keep extracted text exactly as it appears in the original snippet.
6. If no malicious payload exists, return an empty array for payloads.
7. Output STRICT JSON only.

JSON schema:
{
  "payloads":[
    {
      "deceptive_context": "string",
      "payload": "string",
      "hidden_strategy": "string",
      "category": "string",
      "description": "string"
    }
  ]
}
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract attack payloads from poisoned SKILL.md files and update raw_attacks.json"
    )
    parser.add_argument("--skills-dir", default=DEFAULT_SKILLS_DIR)
    parser.add_argument("--output", default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--api-key", default=os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY"))
    parser.add_argument(
        "--max-chars",
        type=int,
        default=18000,
        help="Max chars sent to LLM for each SKILL.md",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Only process first N SKILL.md files (0 means all)",
    )
    parser.add_argument(
        "--keep-non-ddipe",
        action="store_true",
        help="Keep existing non-DDIPE entries in output JSON",
    )
    return parser.parse_args()


def load_existing_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    return []


def clean_text(text: str) -> str:
    text = text.replace("\x00", "")
    return text


def build_user_prompt(skill_path: Path, skill_text: str, max_chars: int) -> str:
    snippet = clean_text(skill_text)
    if len(snippet) > max_chars:
        head = snippet[: max_chars // 2]
        tail = snippet[-(max_chars // 2) :]
        snippet = head + "\n\n...[TRUNCATED]...\n\n" + tail

    return (
        f"File: {skill_path}\n"
        "Extract all attack payloads from this SKILL.md.\n"
        "Return strict JSON following the given schema.\n\n"
        f"SKILL_CONTENT_BEGIN\n{snippet}\nSKILL_CONTENT_END"
    )


def _extract_json_blob(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("No JSON object found in model output")
    return text[start : end + 1]


def call_llm_extract(
    client: OpenAI,
    model: str,
    skill_path: Path,
    skill_text: str,
    max_chars: int,
) -> list[dict[str, str]]:
    prompt = build_user_prompt(skill_path, skill_text, max_chars=max_chars)
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        # 开启 JSON Mode
        response_format={"type": "json_object"}, 
        extra_body={"thinking": {"type": "disabled"}},
        temperature=0,
        max_tokens=4000, # ⚠️ 重要：将 max_tokens 调大，1400 对包含大量代码的输出可能不够
    )

    # 检查是否因为达到 token 上限而被截断
    if resp.choices[0].finish_reason == "length":
        print("警告：输出被截断，请继续增大 max_tokens")

    raw = resp.choices[0].message.content or ""

    # 使用 JSON Mode 后，返回的必定是一个 JSON 字符串，可以直接解析
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"解析失败: {e}")
        print(f"原始输出: {raw}")
        raise

    payloads = data.get("payloads", [])
    if not isinstance(payloads, list):
        return []

    out: list[dict[str, str]] = []
    for item in payloads:
        if not isinstance(item, dict):
            continue
        payload = str(item.get("payload", "")).strip()
        if not payload:
            continue
        out.append(
            {
                "payload": payload,
                "deceptive_context": str(item.get("deceptive_context", "")).strip(),
                "hidden_strategy": str(item.get("hidden_strategy", "")).strip(),
                "category": str(item.get("category", "")).strip(),
                "description": str(item.get("description", "")).strip(),
            }
        )
    return out


def convert_to_rows(payloads: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for p in payloads:
        rows.append(
            {
                "src": DDIPE_SRC,
                "abbr": DDIPE_ABBR,
                "payload": p["payload"],
                "deceptive_context": p.get("deceptive_context", ""),
                "hidden_strategy": p.get("hidden_strategy", ""),
                "category": p.get("category", ""),
                "description": p.get("description", ""),
            }
        )
    return rows


def dedup_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, str]] = []
    for r in rows:
        key = (r.get("abbr", ""), r.get("payload", "").strip())
        if not key[1] or key in seen:
            continue
        seen.add(key)
        deduped.append(r)
    return deduped


def extract_ddipe() -> None:
    args = parse_args()

    if not args.api_key:
        raise SystemExit("Missing API key. Set OPENAI_API_KEY or DEEPSEEK_API_KEY, or use --api-key.")

    skills_dir = Path(args.skills_dir)
    if not skills_dir.exists():
        raise SystemExit(f"Skills directory not found: {skills_dir}")

    skill_files = sorted(skills_dir.glob("V*/SKILL.md"))
    if args.limit and args.limit > 0:
        skill_files = skill_files[: args.limit]

    print(f"Found {len(skill_files)} SKILL.md files in {skills_dir}")

    client = OpenAI(api_key=args.api_key, base_url=args.base_url)

    extracted_rows: list[dict[str, str]] = []
    failed_files: list[str] = []

    pbar = tqdm(skill_files, desc="Processing SKILL.md files", unit="file")
    with open("backup.jsonl", 'w') as f:
        for idx, skill_file in enumerate(skill_files, start=1):
            try:
                text = skill_file.read_text(encoding="utf-8", errors="ignore")
                payloads = call_llm_extract(
                    client=client,
                    model=args.model,
                    skill_path=skill_file,
                    skill_text=text,
                    max_chars=args.max_chars,
                )
                rows = convert_to_rows(payloads)
                extracted_rows.extend(rows)
                for row in rows:
                    f.write(json.dumps(row) + "\n")
                print(f"[{idx}/{len(skill_files)}] {skill_file.name}: extracted {len(rows)} payload(s)")
            except Exception as exc:
                failed_files.append(str(skill_file))
                print(f"[{idx}/{len(skill_files)}] {skill_file.name}: FAILED ({exc})")
            pbar.update(1)

    extracted_rows = dedup_rows(extracted_rows)

    output_path = Path(args.output)
    existing = load_existing_rows(output_path)
    base_rows: list[dict[str, Any]] = []
    if args.keep_non_ddipe:
        base_rows = [r for r in existing if isinstance(r, dict) and r.get("abbr") != DDIPE_ABBR]

    final_rows = dedup_rows(base_rows + extracted_rows)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(final_rows, f, ensure_ascii=False, indent=4)

    print("Done")
    print(f"- Extracted DDIPE rows: {len(extracted_rows)}")
    print(f"- Final rows written: {len(final_rows)}")
    print(f"- Output: {output_path}")
    if failed_files:
        print(f"- Failed files: {len(failed_files)}")
        for ff in failed_files[:20]:
            print(f"  * {ff}")


if __name__ == "__main__":
    extract_ddipe()
