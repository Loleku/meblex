"""Generate PDF assembly instructions from assembly analysis data."""

from __future__ import annotations

import io
import base64
from typing import Any, Dict, List

from reportlab.lib.pagesizes import A4, inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image,
    PageBreak,
    Table,
    TableStyle,
)
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY


def _svg_to_image_bytes(svg_string: str, width: float = 4 * inch, height: float = 3 * inch) -> io.BytesIO:
    """
    Convert SVG string to image bytes for embedding in PDF.
    Falls back to simple placeholder if SVG conversion fails.
    """
    # For simplicity, we'll create a placeholder since SVG to image conversion
    # requires additional dependencies (cairosvg, etc.)
    # In production, you'd use cairosvg or similar
    placeholder = io.BytesIO()
    return placeholder


def generate_assembly_pdf(
    analysis_data: Dict[str, Any],
    filename: str = "assembly_instructions.pdf",
) -> bytes:
    """
    Generate a PDF document from assembly analysis data.
    
    Args:
        analysis_data: Result from process_step_to_assembly_analysis
        filename: Output filename
    
    Returns:
        PDF bytes
    """
    
    # Create PDF in memory
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=A4,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
    )
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=24,
        textColor=colors.HexColor("#1f5f4a"),
        spaceAfter=12,
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
    )
    
    heading_style = ParagraphStyle(
        "CustomHeading",
        parent=styles["Heading2"],
        fontSize=14,
        textColor=colors.HexColor("#1f5f4a"),
        spaceAfter=8,
        spaceBefore=8,
        fontName="Helvetica-Bold",
    )
    
    step_title_style = ParagraphStyle(
        "StepTitle",
        parent=styles["Heading3"],
        fontSize=12,
        textColor=colors.HexColor("#194d3c"),
        spaceAfter=6,
        spaceBefore=6,
        fontName="Helvetica-Bold",
    )
    
    body_style = ParagraphStyle(
        "CustomBody",
        parent=styles["BodyText"],
        fontSize=10,
        textColor=colors.HexColor("#1e2522"),
        spaceAfter=8,
        alignment=TA_JUSTIFY,
    )
    
    normal_style = styles["Normal"]
    
    # Story - container for all elements
    story = []
    
    # Title
    story.append(Paragraph("Assembly Instructions", title_style))
    story.append(Spacer(1, 0.3 * inch))
    
    # File information
    parts_2d = analysis_data.get("parts_2d", [])
    assembly_steps = analysis_data.get("assembly_steps", [])
    stats = analysis_data.get("stats", {})
    
    info_data = [
        ["Total Parts Groups:", str(stats.get("total_parts_groups", 0))],
        ["Total Individual Parts:", str(stats.get("total_individual_parts", 0))],
        ["Assembly Steps:", str(stats.get("assembly_steps_count", 0))],
        ["Mode:", stats.get("mode", "full_analysis").replace("_", " ").title()],
    ]
    
    info_table = Table(info_data, colWidths=[3 * inch, 2 * inch])
    info_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f6f9f7")),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1e2522")),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("GRID", (0, 0), (-1, -1), 1, colors.HexColor("#c9d2cd")),
        ])
    )
    story.append(info_table)
    story.append(Spacer(1, 0.3 * inch))
    
    # Parts summary
    story.append(Paragraph("Parts List", heading_style))
    
    parts_summary_data = [["Part Name", "Category", "Qty", "Dimensions"]]
    for part in parts_2d:
        dim_str = f"{part['dimensions'][0]:.1f}×{part['dimensions'][1]:.1f}×{part['dimensions'][2]:.1f}"
        parts_summary_data.append([
            part["name"],
            part["category"].capitalize(),
            part["quantity_label"],
            dim_str,
        ])
    
    parts_table = Table(parts_summary_data, colWidths=[2 * inch, 1.2 * inch, 0.8 * inch, 1.5 * inch])
    parts_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f5f4a")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#c9d2cd")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f9f7")]),
        ])
    )
    story.append(parts_table)
    story.append(Spacer(1, 0.4 * inch))
    
    # Assembly steps
    if assembly_steps:
        story.append(PageBreak())
        story.append(Paragraph("Assembly Steps", heading_style))
        story.append(Spacer(1, 0.2 * inch))
        
        for step_idx, step in enumerate(assembly_steps, 1):
            # Step header
            step_title = f"Step {step['stepNumber']}: {step['title']}"
            story.append(Paragraph(step_title, step_title_style))
            
            # Step description
            story.append(Paragraph(step["description"], body_style))
            
            # Parts in this step
            if step.get("partIndices"):
                parts_in_step = []
                for part_idx in step["partIndices"]:
                    if part_idx < len(parts_2d):
                        part = parts_2d[part_idx]
                        role = step.get("partRoles", {}).get(str(part_idx), "component")
                        parts_in_step.append(f"• {part['name']} ({role}) - {part['quantity_label']}")
                
                if parts_in_step:
                    story.append(Paragraph("<b>Parts:</b>", body_style))
                    for part_str in parts_in_step:
                        story.append(Paragraph(part_str, normal_style))
            
            # Context parts if any
            if step.get("contextPartIndices"):
                context_parts = []
                for part_idx in step["contextPartIndices"]:
                    if part_idx < len(parts_2d):
                        context_parts.append(parts_2d[part_idx]["name"])
                
                if context_parts:
                    story.append(Paragraph(
                        f"<i>Previously assembled: {', '.join(context_parts)}</i>",
                        normal_style
                    ))
            
            story.append(Spacer(1, 0.15 * inch))
            
            # Page break after every 3-4 steps (depending on space)
            if step_idx % 4 == 0 and step_idx < len(assembly_steps):
                story.append(PageBreak())
    
    # Build PDF
    doc.build(story)
    
    # Get bytes
    pdf_buffer.seek(0)
    return pdf_buffer.getvalue()


def export_assembly_to_pdf(
    assembly_data: Dict[str, Any],
) -> bytes:
    """
    Export assembly analysis to PDF format.
    
    Args:
        assembly_data: Complete assembly analysis result
    
    Returns:
        PDF bytes ready for download
    """
    
    if not assembly_data.get("parts_2d") or not assembly_data.get("assembly_steps"):
        raise RuntimeError("No assembly data to export")
    
    return generate_assembly_pdf(assembly_data)
