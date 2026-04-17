import argparse
import sys
from pathlib import Path

from app.mesh_processor import process_step_to_mesh


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Smoke test for STEP-to-mesh processing."
    )
    parser.add_argument("step_file", help="Path to .step or .stp file")
    parser.add_argument(
        "--tolerance",
        type=float,
        default=0.01,
        help="Meshing tolerance (lower value = denser mesh)",
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
        result = process_step_to_mesh(content, tolerance=args.tolerance)
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1

    print("STEP mesh processing OK")
    print(f"  file: {step_path.name}")
    print(f"  tolerance: {args.tolerance}")
    print(f"  vertices: {result['vertex_count']}")
    print(f"  triangles: {result['triangle_count']}")
    print(f"  bounds: {result['bounds']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
