#!/usr/bin/env python3
"""Test assembly analysis processor."""

import argparse
import json
import sys
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Add app directory to path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir))

from assembly_analysis_processor import process_step_to_assembly_analysis


def main():
    parser = argparse.ArgumentParser(description="Test assembly analysis processor")
    parser.add_argument("step_file", help="Path to STEP file")
    parser.add_argument("--tolerance", type=float, default=0.02, help="Mesh tolerance")
    parser.add_argument("--preview-only", action="store_true", help="Only preview, no AI analysis")
    parser.add_argument("--model", default="openrouter/auto", help="OpenRouter model ID")
    parser.add_argument("--output", help="Save result to JSON file")
    
    args = parser.parse_args()
    
    step_path = Path(args.step_file)
    if not step_path.exists():
        print(f"Error: STEP file not found: {step_path}")
        sys.exit(1)
    
    print(f"Processing: {step_path}")
    print(f"Tolerance: {args.tolerance}")
    print(f"Preview only: {args.preview_only}")
    print(f"Model: {args.model}")
    print()
    
    try:
        with open(step_path, "rb") as f:
            content = f.read()
        
        print("Starting assembly analysis...")
        result = process_step_to_assembly_analysis(
            content,
            tolerance=args.tolerance,
            preview_only=args.preview_only,
            model=args.model,
        )
        
        print(f"Success! Generated {len(result.get('assembly_steps', []))} assembly steps")
        print(f"Total parts groups: {result['stats']['total_parts_groups']}")
        print(f"Total individual parts: {result['stats']['total_individual_parts']}")
        
        if result.get("assembly_steps"):
            print("\nAssembly steps:")
            for step in result["assembly_steps"]:
                print(f"  Step {step['stepNumber']}: {step['title']}")
                print(f"    Parts: {step['partIndices']}")
                print(f"    Description: {step['description']}")
        
        if args.output:
            output_path = Path(args.output)
            with open(output_path, "w") as f:
                json.dump(result, f, indent=2)
            print(f"\nResult saved to: {output_path}")
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
