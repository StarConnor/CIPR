# Example standalone runs on the three shipped CIPR datasets.
# Adjust agent/model/run-name as needed.

uv run python standalone/run_local_exp.py \
  --dataset cipr_no_skills \
  --agent codex_cli \
  --model gpt-5.4 \
  --concurrency 3 \
  --run-name cipr-no-skills-codex \
  --skip-completed \
  --no-stream-logs

uv run python standalone/run_local_exp.py \
  --dataset cipr_normal_skills \
  --agent codex_cli \
  --model gpt-5.4 \
  --concurrency 3 \
  --run-name cipr-normal-skills-codex \
  --skip-completed \
  --no-stream-logs

uv run python standalone/run_local_exp.py \
  --dataset cipr_defense_skills \
  --agent opencode_cli \
  --model deepseek-v4-pro \
  --concurrency 3 \
  --run-name cipr-defense-skills-opencode-ds-pro \
  --skip-completed \
  --no-stream-logs
