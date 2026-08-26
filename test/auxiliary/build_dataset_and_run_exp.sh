#!/usr/bin/env bash
set -Eeuo pipefail

# Build the CIIP dataset, install it into code-agent-redteam, then run experiments.
#
# Default behavior: detach into the background so you do not need to wait.
# Logs are written to: /home/zfk/projects/demo/code-agent-redteam/test/logs/build_dataset_and_run_exp_<timestamp>.log
#
# Usage:
#   ./build_dataset_and_run_exp.sh              # start in background and return immediately
#   ./build_dataset_and_run_exp.sh --foreground # run in current terminal
#
# Optional environment overrides:
#   SAMPLE_N_REPOS=10 SAMPLE_N_PAYLOADS=1 CONCURRENCY=3 MODEL=deepseek-v4-pro ./build_dataset_and_run_exp.sh

TEST_DIR="/home/zfk/projects/demo/code-agent-redteam/test"
DATASET_BUILD_DIR="/home/zfk/projects/benchmark/code-agent-redteam-dataset/prepare_dataset"
RESUME_DATASET="${DATASET_BUILD_DIR}/dataset_exfiltration_destruction_persistence_direct_llm_1_python_js_c.json"
REPOS_DATASET="data/repos-dataset.json"
OUTPUT_DATASET_NAME="dataset_exfiltration_destruction_persistence_direct_llm_10.json"
OUTPUT_DATASET="${DATASET_BUILD_DIR}/${OUTPUT_DATASET_NAME}"
DEST_DATASET_DIR="/home/zfk/projects/demo/code-agent-redteam/data/ciip"
DEST_DATASET="${DEST_DATASET_DIR}/dataset.json"

SAMPLE_N_REPOS="${SAMPLE_N_REPOS:-10}"
SAMPLE_N_PAYLOADS="${SAMPLE_N_PAYLOADS:-1}"
AGENT="${AGENT:-cc_cli}"
MODEL="${MODEL:-deepseek-v4-pro}"
CONCURRENCY="${CONCURRENCY:-3}"

LOG_DIR="${TEST_DIR}/logs"
mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_FILE:-${LOG_DIR}/build_dataset_and_run_exp_$(date +%Y%m%d_%H%M%S).log}"
LOCK_FILE="/tmp/build_dataset_and_run_exp.lock"

if [[ "${1:-}" != "--foreground" && -z "${RUN_DATASET_EXP_IN_BACKGROUND:-}" ]]; then
  echo "Starting dataset build + experiment in background..."
  echo "Log: ${LOG_FILE}"
  RUN_DATASET_EXP_IN_BACKGROUND=1 nohup "$0" --foreground >"${LOG_FILE}" 2>&1 &
  pid=$!
  echo "PID: ${pid}"
  echo "Monitor with: tail -f ${LOG_FILE}"
  exit 0
fi

exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  echo "[$(date '+%F %T')] Another build_dataset_and_run_exp.sh is already running; lock=${LOCK_FILE}" >&2
  exit 1
fi

cd "${DATASET_BUILD_DIR}"

if [[ ! -f "${RESUME_DATASET}" ]]; then
  echo "[$(date '+%F %T')] Resume dataset not found: ${RESUME_DATASET}" >&2
  exit 1
fi
if [[ ! -f "${REPOS_DATASET}" ]]; then
  echo "[$(date '+%F %T')] Repos dataset not found under ${DATASET_BUILD_DIR}: ${REPOS_DATASET}" >&2
  exit 1
fi

echo "[$(date '+%F %T')] Step 1/3: building dataset in ${DATASET_BUILD_DIR}"
echo "[$(date '+%F %T')] Output: ${OUTPUT_DATASET}"
python -m dataset_gen.main \
  --sample-n-repos "${SAMPLE_N_REPOS}" \
  --sample-n-payloads "${SAMPLE_N_PAYLOADS}" \
  --repos-dataset "${REPOS_DATASET}" \
  --resume-from-existing-dataset "${RESUME_DATASET}" \
  --output_name "${OUTPUT_DATASET_NAME}"

echo "[$(date '+%F %T')] Step 2/3: copying dataset to ${DEST_DATASET}"
mkdir -p "${DEST_DATASET_DIR}"
cp -f "${OUTPUT_DATASET}" "${DEST_DATASET}"
ls -lh "${DEST_DATASET}"

echo "[$(date '+%F %T')] Step 3/3: starting experiment"
cd "${TEST_DIR}"
echo "[$(date '+%F %T')] Command: bash run_exp.sh --agent ${AGENT} --model ${MODEL} --concurrency ${CONCURRENCY}"
bash run_exp.sh --agent "${AGENT}" --model "${MODEL}" --concurrency "${CONCURRENCY}"

echo "[$(date '+%F %T')] Done."
