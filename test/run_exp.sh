#!/usr/bin/env bash

# Run one fixed sample from data/cipr_no_skills by default. Resolve paths from
# this script so both `./run_exp.sh` (inside test/) and `./test/run_exp.sh`
# (from the repository root) work.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="${SCRIPT_DIR}/exp-dataset.yaml"
AGENT="cc_cli"
MODEL="deepseek-v4-flash"
DATASET="cipr_no_skills"
concurrency=1
server="http://127.0.0.1:8083"
fetch_completed_args=()

# Simple argument parsing
while [[ $# -gt 0 ]]; do
    case $1 in
        --config) CONFIG="$2"; shift 2 ;;
        --agent) AGENT="$2"; shift 2 ;;
        --model) MODEL="$2"; shift 2 ;;
        --dataset) DATASET="$2"; shift 2 ;;
        --concurrency) concurrency="$2"; shift 2 ;;
        --server) server="$2"; shift 2 ;;
        --fetch-completed-results) fetch_completed_args+=("--fetch-completed-results"); shift ;;
        --fetch-completed-results-full) fetch_completed_args+=("--fetch-completed-results-full"); shift ;;
        *) echo "Unknown argument: $1"; exit 1 ;;
    esac
done

# Check required arguments
if [ -z "$CONFIG" ] || [ -z "$AGENT" ]; then
    echo "Usage: $0 --config <config_file> --agent <agent_name> [--model <model>] [--dataset <dataset>]"
    exit 1
fi

while true; do
    echo "[$(date)] Starting experiment request client..."
    
    python "${SCRIPT_DIR}/run_exp.py" --config "$CONFIG" --agent "$AGENT" --model "$MODEL" --dataset "$DATASET" --concurrency "$concurrency" --server "$server" "${fetch_completed_args[@]}"
    
    EXIT_CODE=$?
    
    if [ $EXIT_CODE -eq 0 ]; then
        echo "[$(date)] All experiments completed successfully! Exiting loop."
        break
    else
        echo "[$(date)] Client connection failed or terminated abnormally (status code: $EXIT_CODE)."
        echo "The server may be restarting; waiting 15 seconds before re-sending the request to trigger Resume..."
        sleep 15
    fi
done
