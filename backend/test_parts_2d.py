import argparse
import sys
from pathlib import Path

from app.parts_2d_processor import process_step_to_parts_2d


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Smoke test for STEP parts extraction and 2D SVG generation."
    )
    parser.add_argument("step_file", help="Path to .step or .stp file")
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.01,
        help="Meshing tolerance for 2D outlines",
    )
    args = parser.parse_args()

    step_path = Path(args.step_file)
    if not step_path.exists() or not step_path.is_file():
        print(f"ERROR: File not found: {step_path}")
        return 1

    if step_path.suffix.lower() not in {".step", ".stp"}:
        print("ERROR: File must have .step or .stp extension")
        return 1

    if args.tolerance <= 0:
        print("ERROR: --tolerance must be greater than 0")
        return 1

    try:
        content = step_path.read_bytes()
        result = process_step_to_parts_2d(content, tolerance=args.tolerance)
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1

    stats = result["stats"]
    print("STEP parts-2d processing OK")
    print(f"  file: {step_path.name}")
    print(f"  tolerance: {args.tolerance}")
    print(f"  solids: {stats['solids_count']}")
    print(f"  groups: {stats['groups_count']}")
    print(f"  category_counts: {stats['category_counts']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
