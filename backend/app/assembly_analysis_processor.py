"""Generate assembly instructions from STEP parts and metadata."""

from __future__ import annotations

import base64
import io
import json
import os
import tempfile
import logging
import math
from typing import Any, Dict, List, Optional, Tuple
from contextlib import contextmanager

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from app.parts_2d_processor import process_step_to_parts_2d

logger = logging.getLogger(__name__)

AssemblyAnalysisResult = Dict[str, Any]


@contextmanager
def temp_step_file(file_content: bytes):
    """Context manager for temporary STEP files - ensures cleanup."""
    tmp_file = None
    tmp_path = None
    try:
        tmp_file = tempfile.NamedTemporaryFile(suffix=".step", delete=False)
        tmp_file.write(file_content)
        tmp_file.flush()
        tmp_path = tmp_file.name
        tmp_file.close()
        yield tmp_path
    finally:
        if tmp_file:
            try:
                tmp_file.close()
            except Exception:
                pass
        
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError as e:
                logger.warning(f"Failed to delete temporary STEP file {tmp_path}: {e}")


def _get_openrouter_api_key() -> str:
    """Get OpenRouter API key from environment. Returns empty string if not set."""
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    return key


def _generate_model_screenshot_placeholder() -> str:
    """Generate a simple placeholder SVG for model visualization."""
    # This would be replaced with actual model screenshot in production
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300" fill="none">'
        '<rect width="400" height="300" fill="#f0f0f0"/>'
        '<text x="200" y="150" text-anchor="middle" font-size="16" fill="#666">'
        'Assembly Model (3D visualization placeholder)'
        '</text>'
        '</svg>'
    )
    return svg


def _create_exploded_view_svg(
    part_ids: List[int],
    total_parts: int,
    step_number: int,
) -> str:
    """Create an exploded view SVG for assembly step."""
    # Create a simple exploded view representation
    svg_parts = []
    svg_parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 500 400" fill="none">'
    )
    svg_parts.append(
        f'<rect width="500" height="400" fill="#fafafa"/>'
    )
    
    # Draw assembly step indicator
    svg_parts.append(
        f'<text x="250" y="30" text-anchor="middle" font-size="18" font-weight="bold" fill="#1f2421">'
        f'Assembly Step {step_number}'
        f'</text>'
    )
    
    # Draw parts being assembled
    part_positions = [
        (100, 150),
        (250, 150),
        (400, 150),
    ]
    
    for i, part_id in enumerate(part_ids[:3]):
        if i < len(part_positions):
            x, y = part_positions[i]
            svg_parts.append(
                f'<g>'
                f'<rect x="{x-40}" y="{y-40}" width="80" height="80" '
                f'fill="#e8f4f8" stroke="#4a90e2" stroke-width="2"/>'
                f'<text x="{x}" y="{y+5}" text-anchor="middle" font-size="14" fill="#1f2421">'
                f'Part {part_id}'
                f'</text>'
                f'</g>'
            )
    
    # Draw connection arrows
    if len(part_ids) > 1:
        svg_parts.append(
            f'<path d="M 140 150 L 210 150" stroke="#e74c3c" stroke-width="2" '
            f'marker-end="url(#arrowhead)"/>'
        )
        if len(part_ids) > 2:
            svg_parts.append(
                f'<path d="M 290 150 L 360 150" stroke="#e74c3c" stroke-width="2" '
                f'marker-end="url(#arrowhead)"/>'
            )
    
    # Add arrow marker
    svg_parts.append(
        '<defs>'
        '<marker id="arrowhead" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto">'
        '<polygon points="0 0, 10 3, 0 6" fill="#e74c3c"/>'
        '</marker>'
        '</defs>'
    )
    
    svg_parts.append('</svg>')
    
    return ''.join(svg_parts)


def _call_openrouter_api(
    prompt: str,
    model: str = "openrouter/auto",
    temperature: float = 0.7,
    max_tokens: int = 2000,
) -> str:
    """Call OpenRouter API with structured prompt and proper error handling."""
    import requests
    import logging
    
    logger = logging.getLogger(__name__)
    
    api_key = _get_openrouter_api_key()
    
    # Check if API key looks valid
    if not api_key or api_key.strip() == "":
        raise RuntimeError("OPENROUTER_API_KEY is not set in environment variables")
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://m3bl3x.local",
        "X-Title": "M3BL3X Assembly Analyzer",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
    }
    
    try:
        logger.info(f"Calling OpenRouter API with model: {model}")
        response = requests.post(url, json=payload, headers=headers, timeout=60)
        
        # Handle authentication errors
        if response.status_code == 401:
            logger.error(f"OpenRouter API authentication failed (401). API key may be invalid or expired.")
            raise RuntimeError(
                "OpenRouter API authentication failed (401 Unauthorized). "
                "Your API key may be invalid, expired, or the account lacks authorization."
            )
        
        # Handle rate limiting
        if response.status_code == 429:
            logger.warning(f"OpenRouter API rate limited (429). Retrying in a moment...")
            raise RuntimeError("OpenRouter API rate limited. Please try again in a moment.")
        
        # Handle other HTTP errors
        if response.status_code >= 400:
            try:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", str(response.status_code))
            except:
                error_msg = response.text[:200] if response.text else str(response.status_code)
            logger.error(f"OpenRouter API error ({response.status_code}): {error_msg}")
            raise RuntimeError(f"OpenRouter API error {response.status_code}: {error_msg}")
        
        response.raise_for_status()
        
    except requests.exceptions.Timeout:
        logger.error("OpenRouter API request timed out (60 seconds)")
        raise RuntimeError("OpenRouter API request timed out. The service may be overloaded.")
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Failed to connect to OpenRouter API: {str(e)}")
        raise RuntimeError("Failed to connect to OpenRouter API. Check your internet connection.")
    except requests.exceptions.RequestException as e:
        # Re-raise RuntimeError without wrapping
        if isinstance(e, RuntimeError):
            raise
        logger.error(f"OpenRouter API request failed: {str(e)}")
        raise RuntimeError(f"OpenRouter API request failed: {str(e)}")
    
    try:
        result = response.json()
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON response from OpenRouter: {str(e)}")
        raise RuntimeError(f"Invalid JSON response from OpenRouter: {str(e)}")
    
    if "choices" not in result or not result["choices"]:
        logger.error(f"Unexpected OpenRouter response structure: {result}")
        raise RuntimeError("Unexpected OpenRouter response structure: missing 'choices'")
    
    if not result["choices"][0].get("message", {}).get("content"):
        logger.error(f"Empty content in OpenRouter response: {result}")
        raise RuntimeError("Empty content in OpenRouter response")
    
    logger.info(f"Successfully got response from OpenRouter API")
    return result["choices"][0]["message"]["content"]


def _generate_fallback_assembly_steps(parts_2d: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Generate a simple assembly sequence based on part categories."""
    
    if not parts_2d:
        return []
    
    steps: List[Dict[str, Any]] = []
    step_number = 1
    
    # Group parts with their indices
    panels = [(i, p) for i, p in enumerate(parts_2d) if p["category"] == "panel"]
    connectors = [(i, p) for i, p in enumerate(parts_2d) if p["category"] == "connector"]
    others = [(i, p) for i, p in enumerate(parts_2d) if p["category"] == "other"]
    
    # Simple heuristic assembly sequence
    
    # Step 1: Start with largest panel (base/bottom)
    if panels:
        idx, panel = panels[0]
        step = {
            "stepNumber": step_number,
            "title": "Place base panel",
            "description": f"Position the base panel ({panel['name']}) as the foundation.",
            "partIndices": [idx],
            "partRoles": {str(idx): "base panel"},
            "contextPartIndices": [],
        }
        steps.append(step)
        step_number += 1
    
    # Step 2: Add side panels
    for panel_idx, (idx, panel) in enumerate(panels[1:2]):  # Add one more panel
        if idx != (panels[0][0] if panels else -1):
            step = {
                "stepNumber": step_number,
                "title": f"Attach side panel",
                "description": f"Connect side panel ({panel['name']}) using connectors.",
                "partIndices": [idx] + ([c[0] for c in connectors[:2]] if connectors else []),
                "partRoles": {
                    str(idx): "side panel",
                    **{str(c[0]): "connector" for c in connectors[:2]}
                },
                "contextPartIndices": [panels[0][0]] if panels else [],
            }
            steps.append(step)
            step_number += 1
            break
    
    # Step 3: Add remaining parts
    already_added = set(i for step in steps for i in step["partIndices"])
    remaining = [(i, p) for i, p in enumerate(parts_2d) if i not in already_added]
    
    if remaining:
        for i, (part_idx, part) in enumerate(remaining[:4]):
            step = {
                "stepNumber": step_number,
                "title": f"Add component {step_number - 1}",
                "description": f"Attach {part['category']} part ({part['name']}) to the assembly.",
                "partIndices": [part_idx],
                "partRoles": {str(part_idx): part["category"]},
                "contextPartIndices": list(already_added),
            }
            steps.append(step)
            already_added.add(part_idx)
            step_number += 1
    
    return steps


def _validate_assembly_steps(steps: Any, parts_count: int) -> List[Dict[str, Any]]:
    """
    Validate assembly steps have correct structure and part indices are within bounds.
    
    Args:
        steps: Data to validate (should be list of dicts)
        parts_count: Total number of parts available
    
    Returns:
        Validated steps list
    
    Raises:
        RuntimeError: If validation fails
    """
    if not isinstance(steps, list):
        raise RuntimeError(f"Assembly steps must be a list, got {type(steps).__name__}")
    
    if not steps:
        return []
    
    validated = []
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            raise RuntimeError(f"Step {i} is not a dictionary: {type(step).__name__}")
        
        # Validate required fields
        if "title" not in step or not isinstance(step.get("title"), str):
            raise RuntimeError(f"Step {i} missing or invalid title")
        if "description" not in step or not isinstance(step.get("description"), str):
            raise RuntimeError(f"Step {i} missing or invalid description")
        
        part_indices = step.get("partIndices", [])
        if not isinstance(part_indices, list):
            raise RuntimeError(f"Step {i} partIndices must be a list")
        
        # Validate part indices are integers within bounds
        for idx in part_indices:
            if not isinstance(idx, int):
                raise RuntimeError(f"Step {i} part index {idx} is not an integer")
            if idx < 0 or idx >= parts_count:
                raise RuntimeError(
                    f"Step {i} references invalid part index {idx}. "
                    f"Only {parts_count} parts available (0-{parts_count-1})"
                )
        
        context_indices = step.get("contextPartIndices", [])
        if isinstance(context_indices, list):
            for idx in context_indices:
                if isinstance(idx, int) and (idx < 0 or idx >= parts_count):
                    raise RuntimeError(
                        f"Step {i} context index {idx} out of bounds"
                    )
        
        validated.append(step)
    
    return validated


def _analyze_assembly_with_ai(
    parts_2d_data: Dict[str, Any],
    model: str = "openrouter/auto",
) -> List[Dict[str, Any]]:
    """Generate assembly steps using AI analysis."""
    
    parts_2d = parts_2d_data.get("parts_2d", [])
    solids = parts_2d_data.get("solids", [])
    
    if not parts_2d or not solids:
        return []
    
    # Build detailed prompt for AI
    parts_info = []
    for i, part in enumerate(parts_2d):
        parts_info.append(
            f"Group {i} ({part['name']}): "
            f"Category={part['category']}, "
            f"Quantity={part['quantity']}, "
            f"Dimensions={part['dimensions']}, "
            f"Volume~={round(sum(d for d in part['dimensions'])**0.33, 2)}"
        )
    
    prompt = f"""You are an expert furniture assembly instruction designer. 
    
Analyze the following furniture parts and generate a step-by-step assembly sequence:

PARTS:
{chr(10).join(parts_info)}

REQUIREMENTS:
1. Generate a logical assembly sequence (typically: build frame → attach panels → add connectors)
2. Each step connects 1-2 new parts to previously assembled components
3. Output MUST be valid JSON array
4. Each step must have: stepNumber, title, description, partIndices (group indices), partRoles

OUTPUT MUST be valid JSON:
[
  {{
    "stepNumber": 1,
    "title": "Assembly title",
    "description": "Step description",
    "partIndices": [0, 5],
    "partRoles": {{"0": "role1", "5": "role2"}},
    "contextPartIndices": []
  }}
]

Generate {min(len(parts_2d), 8)} assembly steps. Return ONLY the JSON array, no other text."""

    import logging
    logger = logging.getLogger(__name__)
    
    try:
        response_text = _call_openrouter_api(prompt, model=model, max_tokens=3000)
        
        # Try to extract JSON from response
        response_text = response_text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        steps = json.loads(response_text)
        
        # Validate structure with bounds checking
        steps = _validate_assembly_steps(steps, len(parts_2d))
        
        logger.info(f"Successfully generated {len(steps)} assembly steps using AI")
        return steps
    
    except json.JSONDecodeError as exc:
        logger.warning(f"AI response was not valid JSON: {exc}. Using fallback sequence.")
        return _generate_fallback_assembly_steps(parts_2d)
    except RuntimeError as exc:
        # Catch all API/validation errors and fall back gracefully
        logger.warning(f"AI analysis failed: {exc}. Using fallback sequence.")
        return _generate_fallback_assembly_steps(parts_2d)
    except Exception as exc:
        # Catch any other unexpected errors
        logger.warning(f"Unexpected error during AI analysis: {exc}. Using fallback sequence.")
        return _generate_fallback_assembly_steps(parts_2d)


def _create_assembly_step_with_visuals(
    step: Dict[str, Any],
    parts_2d_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Enhance assembly step with visual elements."""
    
    step_number = step.get("stepNumber", 1)
    part_indices = step.get("partIndices", [])
    
    # Create exploded view SVG
    exploded_svg = _create_exploded_view_svg(
        part_indices,
        len(parts_2d_data.get("parts_2d", [])),
        step_number,
    )
    
    return {
        **step,
        "exploded_svg": exploded_svg,
        "visual_assets": {
            "exploded_view": True,
            "context_parts_visible": len(step.get("contextPartIndices", [])) > 0,
        },
    }


def _validate_and_split_assembly_steps(
    steps: List[Dict[str, Any]],
    parts_2d: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Validate assembly steps and enforce 1-2 new parts per step constraint.
    If a step has more than 2 new parts, split it into multiple steps.
    
    Args:
        steps: Original assembly steps from AI or fallback
        parts_2d: All extracted parts
    
    Returns:
        Validated steps with 1-2 new parts per step
    """
    if not steps:
        return steps
    
    validated_steps = []
    step_number = 1
    
    for original_step in steps:
        part_indices = original_step.get("partIndices", [])
        context_indices = original_step.get("contextPartIndices", [])
        
        # Calculate new parts (parts not in context)
        new_part_indices = [idx for idx in part_indices if idx not in context_indices]
        
        # If step has more than 2 new parts, split it
        if len(new_part_indices) > 2:
            # Split into multiple steps
            batches = []
            for i in range(0, len(new_part_indices), 2):
                batch = new_part_indices[i:i+2]
                batches.append(batch)
            
            # Create sub-steps
            cumulative_context = context_indices.copy()
            for batch_idx, batch in enumerate(batches):
                is_last_batch = (batch_idx == len(batches) - 1)
                
                # Create new step title
                base_title = original_step.get("title", "Assembly").split(" -")[0]
                sub_title = f"{base_title} - Part {batch_idx + 1}/{len(batches)}"
                
                # Build description mentioning which parts
                part_names = [parts_2d[idx]["name"] for idx in batch if idx < len(parts_2d)]
                sub_desc = f"{original_step.get('description', 'Connect parts.')} [Parts: {', '.join(part_names)}]"
                
                new_step = {
                    "stepNumber": step_number,
                    "title": sub_title,
                    "description": sub_desc,
                    "partIndices": list(batch),
                    "partRoles": {str(idx): original_step.get("partRoles", {}).get(str(idx), "component") 
                                  for idx in batch},
                    "contextPartIndices": cumulative_context.copy(),
                    "exploded_svg": original_step.get("exploded_svg", ""),
                    "visual_assets": original_step.get("visual_assets", {
                        "exploded_view": "",
                        "context_parts_visible": True,
                    }),
                }
                
                validated_steps.append(new_step)
                cumulative_context.extend(batch)
                step_number += 1
        else:
            # Step is valid (1-2 new parts)
            validated_step = original_step.copy()
            validated_step["stepNumber"] = step_number
            validated_steps.append(validated_step)
            step_number += 1
    
    return validated_steps


def process_step_to_assembly_analysis(
    file_content: bytes,
    tolerance: float = 0.01,
    preview_only: bool = False,
    model: str = "openrouter/auto",
) -> AssemblyAnalysisResult:
    """
    Process STEP file and generate assembly instructions.
    
    Args:
        file_content: Raw STEP file bytes
        tolerance: Mesh tolerance for parts extraction
        preview_only: If True, only generate quick preview SVG without AI analysis
        model: OpenRouter model to use for AI analysis
    
    Returns:
        Assembly analysis result with steps and visualizations
    """
    
    if not file_content:
        raise RuntimeError("STEP file is empty.")
    
    if tolerance <= 0:
        raise RuntimeError("Tolerance must be greater than zero.")
    
    with temp_step_file(file_content) as temp_path:
        # Step 1: Extract and classify parts
        parts_2d_data = process_step_to_parts_2d(file_content, tolerance)
        
        # Step 2: Generate assembly steps
        if preview_only:
            # Quick preview: just show the assembled model
            assembly_steps = []
        else:
            # Full analysis: use AI to generate assembly sequence
            assembly_steps = _analyze_assembly_with_ai(
                parts_2d_data,
                model=model,
            )
            
            # Enhance steps with visuals
            enhanced_steps = []
            for step in assembly_steps:
                enhanced_step = _create_assembly_step_with_visuals(
                    step,
                    parts_2d_data,
                )
                enhanced_steps.append(enhanced_step)
            assembly_steps = enhanced_steps
            
            # Validate and enforce 1-2 new parts per step constraint
            parts_list = parts_2d_data.get("parts_2d", [])
            assembly_steps = _validate_and_split_assembly_steps(assembly_steps, parts_list)
        
        # Prepare response
        return {
            "success": True,
            "mode": "preview_only" if preview_only else "full_analysis",
            "parts_2d": parts_2d_data.get("parts_2d", []),
            "solids": parts_2d_data.get("solids", []),
            "assembly_steps": assembly_steps,
            "model_preview_svg": _generate_model_screenshot_placeholder(),
            "stats": {
                **parts_2d_data.get("stats", {}),
                "assembly_steps_count": len(assembly_steps),
                "total_parts_groups": len(parts_2d_data.get("parts_2d", [])),
                "total_individual_parts": sum(
                    p.get("quantity", 1) for p in parts_2d_data.get("parts_2d", [])
                ),
            },
        }
