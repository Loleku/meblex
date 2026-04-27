"""Extract STEP solids, classify parts, and generate 2D isometric SVGs."""

from __future__ import annotations

import math
import os
import tempfile
from typing import Any, Dict, List, Tuple


Parts2DResult = Dict[str, Any]

EPSILON = 1e-6
ISO_COS_30 = math.sqrt(3.0) / 2.0
GROUP_TOLERANCE = 0.15


def _median(values: List[float]) -> float:
    if not values:
        return 0.0

    ordered = sorted(values)
    size = len(ordered)
    midpoint = size // 2

    if size % 2 == 1:
        return float(ordered[midpoint])

    return float((ordered[midpoint - 1] + ordered[midpoint]) / 2.0)


def _read_step_root_shape(step_path: str):
    import cadquery as cq

    step_shape = cq.importers.importStep(step_path)
    try:
        return step_shape.val().wrapped
    except Exception:
        objects = getattr(step_shape, "objects", None)
        if not objects:
            raise

        if len(objects) == 1:
            return objects[0].wrapped

        from OCP.BRep import BRep_Builder
        from OCP.TopoDS import TopoDS_Compound

        builder = BRep_Builder()
        compound = TopoDS_Compound()
        builder.MakeCompound(compound)

        added_count = 0
        for obj in objects:
            wrapped = getattr(obj, "wrapped", None)
            if wrapped is None:
                continue
            builder.Add(compound, wrapped)
            added_count += 1

        if added_count == 0:
            raise RuntimeError("STEP import did not expose any CAD shapes.")

        return compound


def _extract_solids(root_shape) -> List[Any]:
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    solids: List[Any] = []
    explorer = TopExp_Explorer(root_shape, TopAbs_SOLID)

    while explorer.More():
        solids.append(TopoDS.Solid_s(explorer.Current()))
        explorer.Next()

    if not solids:
        return [root_shape]

    return solids


def _compute_bbox(shape) -> List[float]:
    from OCP.Bnd import Bnd_Box
    from OCP.BRepBndLib import BRepBndLib

    box = Bnd_Box()
    box.SetGap(0.0)

    add_fn = getattr(BRepBndLib, "AddOptimal_s", None)
    if add_fn is None:
        add_fn = getattr(BRepBndLib, "Add_s", None)
    if add_fn is None:
        add_fn = getattr(BRepBndLib, "AddOptimal", None)
    if add_fn is None:
        add_fn = getattr(BRepBndLib, "Add", None)
    if add_fn is None:
        raise RuntimeError("Unable to compute STEP part bounding box.")

    try:
        add_fn(shape, box)
    except TypeError:
        try:
            add_fn(shape, box, False)
        except TypeError:
            add_fn(shape, box, False, True)

    xmin, ymin, zmin, xmax, ymax, zmax = box.Get()
    return [float(xmin), float(ymin), float(zmin), float(xmax), float(ymax), float(zmax)]


def _compute_volume(shape) -> float:
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps

    props = GProp_GProps()

    volume_fn = getattr(BRepGProp, "VolumeProperties_s", None)
    if volume_fn is None:
        volume_fn = getattr(BRepGProp, "VolumeProperties", None)
    if volume_fn is None:
        return 0.0

    try:
        volume_fn(shape, props)
    except TypeError:
        volume_fn(shape, props, True, False, False)

    return float(abs(props.Mass()))


def _compute_surface_ratios(shape) -> Tuple[int, float, float]:
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    face_count = 0
    plane_count = 0
    cylinder_count = 0

    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        face = TopoDS.Face_s(explorer.Current())
        face_count += 1

        try:
            surface = BRepAdaptor_Surface(face, True)
        except TypeError:
            surface = BRepAdaptor_Surface(face)

        surface_type = surface.GetType()
        if surface_type == GeomAbs_Plane:
            plane_count += 1
        elif surface_type == GeomAbs_Cylinder:
            cylinder_count += 1

        explorer.Next()

    if face_count == 0:
        return 0, 0.0, 0.0

    return face_count, plane_count / face_count, cylinder_count / face_count


def _extract_triangles(shape, tolerance: float) -> List[Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]]:
    from OCP.BRep import BRep_Tool
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    from OCP.TopLoc import TopLoc_Location

    mesh_algo = BRepMesh_IncrementalMesh(shape, tolerance, False, 0.5, False)
    mesh_algo.Perform()

    triangles: List[Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]] = []
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    location = TopLoc_Location()

    triangulation_fn = getattr(BRep_Tool, "Triangulation_s", None)
    if triangulation_fn is None:
        triangulation_fn = getattr(BRep_Tool, "Triangulation", None)
    if triangulation_fn is None:
        raise RuntimeError("Unable to read triangulation from STEP faces.")

    while explorer.More():
        face = TopoDS.Face_s(explorer.Current())
        triangulation = triangulation_fn(face, location)

        if triangulation is not None:
            node_map: Dict[int, Tuple[float, float, float]] = {}

            for index in range(1, triangulation.NbNodes() + 1):
                point = triangulation.Node(index)
                world_point = point.Transformed(location.Transformation())
                node_map[index] = (
                    float(world_point.X()),
                    float(world_point.Y()),
                    float(world_point.Z()),
                )

            for index in range(1, triangulation.NbTriangles() + 1):
                triangle = triangulation.Triangle(index)
                node1, node2, node3 = triangle.Get()
                if node1 in node_map and node2 in node_map and node3 in node_map:
                    triangles.append((node_map[node1], node_map[node2], node_map[node3]))

        explorer.Next()

    return triangles


def _project_isometric(point: Tuple[float, float, float]) -> Tuple[float, float]:
    x_coord, y_coord, z_coord = point
    iso_x = (x_coord - y_coord) * ISO_COS_30
    iso_y = z_coord + ((x_coord + y_coord) * 0.5)
    return iso_x, iso_y


def _edge_key(first: Tuple[float, float], second: Tuple[float, float]) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    first_q = (round(first[0], 3), round(first[1], 3))
    second_q = (round(second[0], 3), round(second[1], 3))
    if first_q <= second_q:
        return first_q, second_q
    return second_q, first_q


def _empty_svg() -> Tuple[str, List[float]]:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1" fill="none"></svg>',
        [0.0, 0.0, 1.0, 1.0],
    )


def _build_isometric_svg(triangles: List[Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]]) -> Tuple[str, List[float]]:
    if not triangles:
        return _empty_svg()

    edge_counts: Dict[Tuple[Tuple[float, float], Tuple[float, float]], int] = {}
    edge_points: Dict[Tuple[Tuple[float, float], Tuple[float, float]], Tuple[Tuple[float, float], Tuple[float, float]]] = {}

    for triangle in triangles:
        projected = [_project_isometric(vertex) for vertex in triangle]

        for first_index, second_index in ((0, 1), (1, 2), (2, 0)):
            first = projected[first_index]
            second = projected[second_index]

            if abs(first[0] - second[0]) < EPSILON and abs(first[1] - second[1]) < EPSILON:
                continue

            key = _edge_key(first, second)
            edge_counts[key] = edge_counts.get(key, 0) + 1
            if key not in edge_points:
                edge_points[key] = (first, second)

    if not edge_points:
        return _empty_svg()

    boundary_keys = [key for key, count in edge_counts.items() if count == 1]
    selected_keys = boundary_keys if len(boundary_keys) >= 6 else list(edge_points.keys())
    selected_keys = sorted(selected_keys)

    max_edges = 1100
    if len(selected_keys) > max_edges:
        step = max(1, len(selected_keys) // max_edges)
        selected_keys = selected_keys[::step]

    all_points = [point for key in selected_keys for point in edge_points[key]]
    min_x = min(point[0] for point in all_points)
    max_x = max(point[0] for point in all_points)
    min_y = min(point[1] for point in all_points)
    max_y = max(point[1] for point in all_points)

    span_x = max_x - min_x
    span_y = max_y - min_y
    span = max(span_x, span_y, 1.0)
    padding = span * 0.09

    width = span_x + (padding * 2.0)
    height = span_y + (padding * 2.0)
    stroke_width = max(1.0, span * 0.0045)

    lines: List[str] = []
    for key in selected_keys:
        first, second = edge_points[key]
        x1 = (first[0] - min_x) + padding
        y1 = (max_y - first[1]) + padding
        x2 = (second[0] - min_x) + padding
        y2 = (max_y - second[1]) + padding
        lines.append(
            f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" />'
        )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.2f} {height:.2f}" fill="none">'
        f'<g stroke="#1f2421" stroke-width="{stroke_width:.2f}" stroke-linecap="round" stroke-linejoin="round">'
        f"{''.join(lines)}"
        "</g>"
        "</svg>"
    )

    return svg, [0.0, 0.0, round(width, 2), round(height, 2)]


def _classify_parts(parts: List[Dict[str, Any]]) -> None:
    if not parts:
        return

    max_dims = [part["max_dim"] for part in parts]
    volumes = [part["volume"] for part in parts]
    largest_dim = max(max_dims) if max_dims else 1.0
    largest_volume = max(volumes) if volumes else 1.0
    median_dim = _median(max_dims)
    median_volume = _median([volume for volume in volumes if volume > 0]) or 1.0

    small_dim_threshold = max(largest_dim * 0.08, median_dim * 0.45)
    small_volume_threshold = max(largest_volume * 0.01, median_volume * 0.2)
    panel_dim_threshold = max(largest_dim * 0.35, median_dim * 1.2)

    for part in parts:
        thickness, width, length = sorted(part["dimensions"])

        thin_ratio = thickness / max(width, EPSILON)
        slender_ratio = length / max(thickness, EPSILON)
        is_large = length >= panel_dim_threshold
        is_small = part["max_dim"] <= small_dim_threshold and part["volume"] <= small_volume_threshold

        planar_ratio = part["planar_ratio"]
        cylindrical_ratio = part["cylindrical_ratio"]

        if is_large and thin_ratio <= 0.18 and planar_ratio >= 0.55:
            category = "panel"
        elif is_small and (cylindrical_ratio >= 0.2 or slender_ratio >= 2.6):
            category = "connector"
        else:
            category = "other"

        part["is_small"] = bool(is_small)
        part["category"] = category


def _build_signature(part: Dict[str, Any]) -> str:
    dim_small, dim_mid, dim_large = sorted(part["dimensions"])
    return (
        f"{part['category']}"
        f"|d{dim_small:.1f}-{dim_mid:.1f}-{dim_large:.1f}"
        f"|v{part['volume']:.1f}"
        f"|p{part['planar_ratio']:.2f}"
        f"|c{part['cylindrical_ratio']:.2f}"
        f"|f{part['face_count']}"
    )


def _is_within_relative_tolerance(reference: float, candidate: float, tolerance: float) -> bool:
    reference_abs = abs(reference)
    candidate_abs = abs(candidate)
    scale = max(reference_abs, candidate_abs, EPSILON)
    return abs(reference_abs - candidate_abs) <= scale * tolerance


def _parts_match_with_tolerance(reference: Dict[str, Any], candidate: Dict[str, Any], tolerance: float) -> bool:
    if reference["category"] != candidate["category"]:
        return False

    reference_dims = sorted(reference["dimensions"])
    candidate_dims = sorted(candidate["dimensions"])

    for reference_dim, candidate_dim in zip(reference_dims, candidate_dims):
        if not _is_within_relative_tolerance(reference_dim, candidate_dim, tolerance):
            return False

    return _is_within_relative_tolerance(reference["volume"], candidate["volume"], tolerance)


def _group_parts(parts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: List[Dict[str, Any]] = []

    for part in parts:
        should_group = part["is_small"] or part["category"] == "connector"

        if not should_group:
            grouped.append(
                {
                    "representative": part,
                    "items": [part],
                    "should_group": False,
                }
            )
            continue

        matched_group = None
        for group in grouped:
            if not group["should_group"]:
                continue

            representative = group["representative"]
            if _parts_match_with_tolerance(representative, part, GROUP_TOLERANCE):
                matched_group = group
                break

        if matched_group is None:
            grouped.append(
                {
                    "representative": part,
                    "items": [part],
                    "should_group": True,
                }
            )
        else:
            matched_group["items"].append(part)

    grouped_parts: List[Dict[str, Any]] = []
    category_counters = {"panel": 0, "connector": 0, "other": 0}

    for group_index, group in enumerate(grouped, start=1):
        group_items = group["items"]
        representative = group["representative"]

        category = representative["category"]
        category_counters[category] += 1

        grouped_parts.append(
            {
                "group_id": f"group_{group_index}",
                "name": f"{category}_{category_counters[category]:02d}",
                "category": category,
                "quantity": len(group_items),
                "quantity_label": f"x{len(group_items)}",
                "part_ids": [part["part_id"] for part in group_items],
                "signature": representative["signature"],
                "dimensions": representative["dimensions"],
                "bbox_3d": representative["bbox_3d"],
                "svg": representative["svg"],
                "view_box": representative["view_box"],
                "group_tolerance": GROUP_TOLERANCE,
            }
        )

    return grouped_parts


def process_step_to_parts_2d(file_content: bytes, tolerance: float = 0.01) -> Parts2DResult:
    if not file_content:
        raise RuntimeError("STEP file is empty.")

    if tolerance <= 0:
        raise RuntimeError("Tolerance must be greater than zero.")

    with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as temporary_file:
        temporary_file.write(file_content)
        temporary_path = temporary_file.name

    try:
        try:
            root_shape = _read_step_root_shape(temporary_path)
        except Exception as exc:
            raise RuntimeError(
                "STEP parts processing requires cadquery + cadquery-ocp. "
                f"Import/read failed: {exc}"
            ) from exc

        solids = _extract_solids(root_shape)

        raw_parts: List[Dict[str, Any]] = []
        for index, solid in enumerate(solids):
            try:
                bbox = _compute_bbox(solid)
                dimensions = [
                    max(0.0, bbox[3] - bbox[0]),
                    max(0.0, bbox[4] - bbox[1]),
                    max(0.0, bbox[5] - bbox[2]),
                ]

                # Validate bounding box
                if not all(math.isfinite(d) for d in dimensions):
                    print(f"Warning: Solid {index} has invalid dimensions: {dimensions}")
                    continue

                max_dim = max(dimensions) if dimensions else 0.0
                if max_dim <= EPSILON:
                    continue

                volume = _compute_volume(solid)
                face_count, planar_ratio, cylindrical_ratio = _compute_surface_ratios(solid)
                triangles = _extract_triangles(solid, tolerance)
                svg, view_box = _build_isometric_svg(triangles)

                raw_parts.append(
                    {
                        "part_id": f"part_{index}",
                        "bbox_3d": bbox,
                        "dimensions": [round(value, 4) for value in dimensions],
                        "max_dim": float(max_dim),
                        "volume": float(round(volume, 4)),
                        "face_count": int(face_count),
                        "planar_ratio": float(round(planar_ratio, 4)),
                        "cylindrical_ratio": float(round(cylindrical_ratio, 4)),
                        "svg": svg,
                        "view_box": view_box,
                    }
                )
            except Exception as e:
                print(f"Warning: Failed to process solid {index}: {e}")
                continue

        if not raw_parts:
            raise RuntimeError(
                "No solids were extracted from the STEP file. "
                "The file may be empty or contain only non-solid geometry. "
                "Please verify the file format and contents."
            )

        _classify_parts(raw_parts)
        for part in raw_parts:
            part["signature"] = _build_signature(part)

        grouped_parts = _group_parts(raw_parts)

        category_counts = {"panel": 0, "connector": 0, "other": 0}
        for part in raw_parts:
            category_counts[part["category"]] += 1

        solids_output = [
            {
                "part_id": part["part_id"],
                "category": part["category"],
                "is_small": part["is_small"],
                "dimensions": part["dimensions"],
                "bbox_3d": part["bbox_3d"],
                "volume": part["volume"],
            }
            for part in raw_parts
        ]

        return {
            "parts_2d": grouped_parts,
            "solids": solids_output,
            "stats": {
                "solids_count": len(raw_parts),
                "groups_count": len(grouped_parts),
                "category_counts": category_counts,
                "projection": "isometric",
                "group_tolerance": GROUP_TOLERANCE,
            },
        }
    finally:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)
