"""
Module for processing STEP files and converting them to triangle meshes.
"""

from typing import Any, Dict, List
import os
import sys
import tempfile

import numpy as np


MeshResult = Dict[str, Any]


def _build_mesh_result(vertices: List[List[float]], triangles: List[List[int]]) -> MeshResult:
    if not vertices or not triangles:
        raise RuntimeError("Meshing succeeded but produced empty geometry.")

    vertices_array = np.array(vertices, dtype=np.float32)
    bounds = [
        float(vertices_array[:, 0].min()),
        float(vertices_array[:, 1].min()),
        float(vertices_array[:, 2].min()),
        float(vertices_array[:, 0].max()),
        float(vertices_array[:, 1].max()),
        float(vertices_array[:, 2].max()),
    ]

    return {
        "vertices": vertices,
        "triangles": triangles,
        "bounds": bounds,
        "vertex_count": len(vertices),
        "triangle_count": len(triangles),
    }


def _process_with_cadquery(file_content: bytes, tolerance: float) -> MeshResult:
    import cadquery as cq
    from OCP.BRep import BRep_Tool
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as tmp:
        tmp.write(file_content)
        tmp_path = tmp.name

    try:
        shape = cq.importers.importStep(tmp_path)
        ocp_shape = shape.val().wrapped

        mesh_algo = BRepMesh_IncrementalMesh(ocp_shape, tolerance, False, 0.5, False)
        mesh_algo.Perform()

        vertices: List[List[float]] = []
        triangles: List[List[int]] = []

        face_explorer = TopExp_Explorer(ocp_shape, TopAbs_FACE)
        from OCP.TopLoc import TopLoc_Location

        location = TopLoc_Location()

        while face_explorer.More():
            face = TopoDS.Face_s(face_explorer.Current())
            triangulation = BRep_Tool.Triangulation_s(face, location)

            if triangulation is not None:
                node_map: Dict[int, int] = {}

                for i in range(1, triangulation.NbNodes() + 1):
                    p = triangulation.Node(i)
                    p_world = p.Transformed(location.Transformation())
                    vertices.append([float(p_world.X()), float(p_world.Y()), float(p_world.Z())])
                    node_map[i] = len(vertices) - 1

                for i in range(1, triangulation.NbTriangles() + 1):
                    tri = triangulation.Triangle(i)
                    n1, n2, n3 = tri.Get()
                    triangles.append([node_map[n1], node_map[n2], node_map[n3]])

            face_explorer.Next()

        return _build_mesh_result(vertices, triangles)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _process_with_pyassimp(file_content: bytes) -> MeshResult:
    import pyassimp

    with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as tmp:
        tmp.write(file_content)
        tmp_path = tmp.name

    try:
        scene = pyassimp.load(tmp_path)

        vertices: List[List[float]] = []
        triangles: List[List[int]] = []
        vertex_offset = 0

        for mesh in scene.meshes:
            for vertex in mesh.vertices:
                vertices.append([float(vertex[0]), float(vertex[1]), float(vertex[2])])

            for face in mesh.faces:
                if len(face) >= 3:
                    triangles.append(
                        [
                            int(face[0]) + vertex_offset,
                            int(face[1]) + vertex_offset,
                            int(face[2]) + vertex_offset,
                        ]
                    )

            vertex_offset += len(mesh.vertices)

        return _build_mesh_result(vertices, triangles)
    finally:
        try:
            pyassimp.release(scene)
        except Exception:
            pass

        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def process_step_to_mesh(file_content: bytes, tolerance: float = 0.01) -> MeshResult:
    """
    Process a STEP file and convert it to a unified triangle mesh.

    Raises RuntimeError when no processor can successfully parse the file.
    """

    attempts: List[str] = []

    try:
        return _process_with_cadquery(file_content, tolerance)
    except Exception as exc:
        attempts.append(f"cadquery/OCP failed: {exc}")

    if sys.version_info < (3, 12):
        try:
            return _process_with_pyassimp(file_content)
        except Exception as exc:
            attempts.append(f"pyassimp failed: {exc}")
    else:
        attempts.append("pyassimp skipped on Python 3.12+ (distutils was removed)")

    details = " | ".join(attempts) if attempts else "No processors were attempted."
    raise RuntimeError(
        "STEP processing is unavailable or failed for this file. "
        "Install compatible CAD dependencies (recommended Python 3.11/3.12 with cadquery and cadquery-ocp). "
        f"Details: {details}"
    )
