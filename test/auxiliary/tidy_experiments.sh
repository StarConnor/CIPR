#!/bin/bash
# Script name: tidy_experiments.sh
# Purpose: 1. Align the directory structure under exp/dataset and exp/single_sample
#          2. Remove model directories that contain no .json files
#          3. Renumber the remaining model directories sequentially

set -e  # Exit immediately on error

# Root directories to process
ROOTS=("exp/dataset" "exp/single_sample")

# Process each root directory
for ROOT in "${ROOTS[@]}"; do
    # Check whether the root directory exists
    [[ -d "$ROOT" ]] || { echo "Warning: $ROOT does not exist, skipping"; continue; }

    echo "Processing: $ROOT"
    
    # Step 1: Align structure, moving contents out of redundant directories
    # Pattern: agent_name/dataset_name/model_name-n/redundant_name/
    find "$ROOT" -mindepth 4 -maxdepth 4 -type d | while read -r redundant_dir; do
        parent_dir=$(dirname "$redundant_dir")  # model_name-n directory
        # Move everything (including hidden files) from the redundant directory to its parent
        if [[ -n "$(ls -A "$redundant_dir")" ]]; then
            mv "$redundant_dir"/* "$redundant_dir"/.[!.]* "$parent_dir" 2>/dev/null || true
        fi
        # Remove the now-empty redundant directory
        rmdir "$redundant_dir" 2>/dev/null && echo "  Cleaned up redundant directory: $redundant_dir"
    done

    # Step 2: Remove model directories (model_name-n) that contain no .json files
    # Iterate over all dataset_name directories
    find "$ROOT" -mindepth 2 -maxdepth 2 -type d | while read -r dataset_dir; do
        # Iterate over each model_name-n directory under the dataset
        find "$dataset_dir" -mindepth 1 -maxdepth 1 -type d | while read -r model_dir; do
            # Check whether any .json file exists (recursively) in this directory
            if [[ -z "$(find "$model_dir" -name "*.json" -type f -print -quit)" ]]; then
                echo "  Deleting directory without JSON files: $model_dir"
                rm -rf "$model_dir"
            fi
        done
    done

    # Step 3: Under each dataset_name, renumber the model_name-* directories
    find "$ROOT" -mindepth 2 -maxdepth 2 -type d | while read -r dataset_dir; do
        # Use an associative array to group by original model_name
        declare -A groups
        # Collect all existing model_name-n directories
        # Fix: place the stderr redirection outside the loop
        for dir in "$dataset_dir"/* "$dataset_dir"/.[!.]*; do
            [[ -d "$dir" ]] || continue
            base=$(basename "$dir")
            # Extract model_name and number, e.g.: resnet50-1
            if [[ "$base" =~ ^(.+)-([0-9]+)$ ]]; then
                model_name="${BASH_REMATCH[1]}"
                num="${BASH_REMATCH[2]}"
                groups["$model_name"]+="$num:$dir "  # Store number and path
            fi
        done 2>/dev/null  # Redirect error output here

        # Reorder directories within each model_name group
        for model_name in "${!groups[@]}"; do
            # Parse all number/path pairs, sorted by number
            items=()
            for item in ${groups[$model_name]}; do
                num="${item%:*}"
                path="${item#*:}"
                items+=("$num:$path")
            done
            # Sort numerically by number
            IFS=$'\n' sorted=($(sort -n <<<"${items[*]}"))
            unset IFS

            new_index=1
            for item in "${sorted[@]}"; do
                old_path="${item#*:}"
                new_name="${model_name}-${new_index}"
                new_path="$(dirname "$old_path")/$new_name"
                if [[ "$old_path" != "$new_path" ]]; then
                    echo "  Renaming: $old_path -> $new_path"
                    mv "$old_path" "$new_path"
                fi
                ((new_index++))
            done
        done
        unset groups  # Clear the associative array to avoid leftovers in the next loop iteration
    done
done

echo "All processing complete!"