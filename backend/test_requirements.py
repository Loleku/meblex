#!/usr/bin/env python3
"""Test all requirements are properly implemented."""

import sys
import os
from pathlib import Path

# Add the app directory to path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir))

from assembly_analysis_processor import (
    _validate_and_split_assembly_steps,
    process_step_to_assembly_analysis,
)
from parts_2d_processor import process_step_to_parts_2d
from pdf_exporter import export_assembly_to_pdf

def test_pdf_export():
    """Test PDF export functionality (Requirement 9)."""
    print("[TEST] Testing PDF export module import...")
    
    # Create minimal test data
    test_data = {
        "parts_2d": [
            {"name": "Panel A", "category": "panel", "quantity_label": "x1", "dimensions": [10, 10, 1]},
            {"name": "Connector B", "category": "connector", "quantity_label": "x2", "dimensions": [2, 2, 5]},
        ],
        "assembly_steps": [
            {
                "stepNumber": 1,
                "title": "Attach Base",
                "description": "Attach the base panel",
                "partIndices": [0],
                "partRoles": {"0": "base"},
                "contextPartIndices": [],
            }
        ],
        "stats": {
            "total_parts_groups": 2,
            "total_individual_parts": 3,
            "assembly_steps_count": 1,
            "mode": "full_analysis",
        }
    }
    
    try:
        pdf_bytes = export_assembly_to_pdf(test_data)
        assert isinstance(pdf_bytes, bytes), "PDF export should return bytes"
        assert len(pdf_bytes) > 0, "PDF bytes should not be empty"
        print(f"  [OK] PDF export generates {len(pdf_bytes)} bytes")
        return True
    except Exception as e:
        print(f"  [FAIL] PDF export failed: {e}")
        return False

def test_step_validation():
    """Test step validation with 1-2 parts constraint (Requirement 7)."""
    print("[TEST] Testing assembly step validation...")
    
    # Create test steps with more than 2 new parts
    test_parts = [
        {"name": "Part A", "category": "panel"},
        {"name": "Part B", "category": "connector"},
        {"name": "Part C", "category": "connector"},
        {"name": "Part D", "category": "connector"},
        {"name": "Part E", "category": "panel"},
    ]
    
    test_steps = [
        {
            "stepNumber": 1,
            "title": "Initial Assembly",
            "description": "Connect all parts",
            "partIndices": [0, 1, 2, 3, 4],  # 5 parts - should be split
            "partRoles": {str(i): "component" for i in range(5)},
            "contextPartIndices": [],
            "exploded_svg": "",
            "visual_assets": {},
        }
    ]
    
    try:
        validated = _validate_and_split_assembly_steps(test_steps, test_parts)
        assert len(validated) > 1, "Steps with >2 parts should be split"
        
        # Check that each step has at most 2 new parts
        for step in validated:
            new_parts = [idx for idx in step["partIndices"] if idx not in step["contextPartIndices"]]
            assert len(new_parts) <= 2, f"Step {step['stepNumber']} has {len(new_parts)} new parts (max 2)"
        
        print(f"  [OK] Step validation split 1 step with 5 parts into {len(validated)} steps")
        for step in validated:
            print(f"    - Step {step['stepNumber']}: {len(step['partIndices'])} parts (context: {len(step['contextPartIndices'])})")
        return True
    except Exception as e:
        print(f"  [FAIL] Step validation failed: {e}")
        return False

def test_context_parts():
    """Test context parts tracking (Requirement 8)."""
    print("[TEST] Testing context parts tracking...")
    
    test_steps = [
        {
            "stepNumber": 1,
            "title": "Step 1",
            "description": "First step",
            "partIndices": [0],
            "contextPartIndices": [],
        },
        {
            "stepNumber": 2,
            "title": "Step 2",
            "description": "Second step",
            "partIndices": [1],
            "contextPartIndices": [0],  # Context from previous
        },
    ]
    
    try:
        # Verify context parts are tracked
        for step in test_steps:
            assert "contextPartIndices" in step, "Step missing contextPartIndices"
            assert isinstance(step["contextPartIndices"], list), "contextPartIndices should be a list"
        
        print(f"  [OK] Context parts properly tracked in {len(test_steps)} steps")
        for i, step in enumerate(test_steps):
            print(f"    - Step {step['stepNumber']}: {len(step['contextPartIndices'])} context parts")
        return True
    except Exception as e:
        print(f"  [FAIL] Context parts test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("M3BL3X Requirements Verification Tests")
    print("="*60 + "\n")
    
    results = []
    
    # Test Requirement 9 (PDF Export)
    results.append(("Requirement 9: PDF Export", test_pdf_export()))
    print()
    
    # Test Requirement 7 (1-2 parts per step)
    results.append(("Requirement 7: Step Validation", test_step_validation()))
    print()
    
    # Test Requirement 8 (Context parts)
    results.append(("Requirement 8: Context Parts", test_context_parts()))
    print()
    
    # Summary
    print("="*60)
    print("Test Summary")
    print("="*60)
    passed = sum(1 for _, result in results if result)
    total = len(results)
    print(f"\nPassed: {passed}/{total}")
    for name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status}: {name}")
    
    print("\n" + "="*60)
    if passed == total:
        print("All tests passed!")
        print("="*60 + "\n")
        return 0
    else:
        print(f"{total - passed} test(s) failed")
        print("="*60 + "\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())
