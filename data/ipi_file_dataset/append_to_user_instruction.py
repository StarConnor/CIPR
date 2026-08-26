#!/usr/bin/env python3
"""
Script to add a string to the end of the user_instruction field in dataset.json
"""

import json
import argparse
from pathlib import Path


def append_to_user_instruction(input_file, output_file, append_text, target_field: str = "user_instruction"):
    """
    Append text to the end of user_instruction field in all samples.
    
    Args:
        input_file: Path to the input JSON file
        output_file: Path to the output JSON file
        append_text: Text to append to each user_instruction field
    """
    # Read the JSON file
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Count modified samples
    modified_count = 0
    
    # Iterate through samples and append text
    if 'samples' in data:
        for sample in data['samples']:
            if "user_instruction" in sample:
                if "configuration" in sample['user_instruction']:
                    os.rena
    
    # Write the modified data to output file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"Modified {modified_count} samples")
    print(f"Output written to: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Add a string to the end of user_instruction field in dataset.json'
    )
    parser.add_argument(
        '--input_file',
        type=str,
        default="./data/ipi_web_dataset/dataset.json",
        help='Path to the input JSON file'
    )
    parser.add_argument(
        '--append_text',
        type=str,
        default=" You can read the website in http://172.16.171.1:8080/test.",
        help='text to append to user_instruction field'
    )
    parser.add_argument(
        '--target_field',
        type=str,
        default="user_instruction",
        help='target_field to be appended'
    )
    parser.add_argument(
        '-o', '--output',
        type=str,
        default=None,
        help='Path to the output JSON file (default: overwrites input file)'
    )
    
    args = parser.parse_args()
    
    # Use input file as output if not specified
    output_file = args.output if args.output else args.input_file
    
    append_to_user_instruction(args.input_file, output_file, args.append_text, args.target_field)


if __name__ == '__main__':
    main()
