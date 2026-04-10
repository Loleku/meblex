"""
Module for processing 3D models (STEP files) and converting them to triangle meshes.
Uses direct OpenCASCADE calls via ctypes or a fallback method.
"""

import numpy as np
from typing import Dict, List, Tuple, Any
import io
import tempfile
import os


def generate_sample_mesh() -> Dict[str, Any]:
    """
    Generate a sample cube mesh for testing purposes.
    This is a fallback when STEP processing is unavailable.
    
    Returns:
        Dictionary with mesh data containing vertices, triangles, and bounds
    """
    # Create a simple cube mesh
    vertices = [
        # Bottom face (z=0)
        [0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
        # Top face (z=1)
        [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1],
    ]
    
    triangles = [
        # Bottom face
        [0, 1, 2], [0, 2, 3],
        # Top face
        [4, 6, 5], [4, 7, 6],
        # Front face
        [0, 5, 1], [0, 4, 5],
        # Back face
        [2, 7, 3], [2, 6, 7],
        # Left face
        [0, 3, 7], [0, 7, 4],
        # Right face
        [1, 5, 6], [1, 6, 2],
    ]
    
    vertices_array = np.array(vertices, dtype=np.float32)
    bounds = [0.0, 0.0, 0.0, 1.0, 1.0, 1.0]
    
    return {
        "vertices": vertices,
        "triangles": triangles,
        "bounds": bounds,
        "vertex_count": len(vertices),
        "triangle_count": len(triangles),
        "is_sample": True
    }


def process_step_to_mesh(file_content: bytes, tolerance: float = 0.01) -> Dict[str, Any]:
    """
    Process a STEP file and convert it to a unified triangle mesh.
    
    Args:
        file_content: Raw STEP file content as bytes
        tolerance: Mesh refinement tolerance
        
    Returns:
        Dictionary with mesh data containing:
        - vertices: List of [x, y, z] coordinates
        - triangles: List of [i, j, k] vertex indices
        - bounds: Bounding box [min_x, min_y, min_z, max_x, max_y, max_z]
    """
    
    # Try to use CadQuery if available
    try:
        import cadquery as cq
        from OCP.BRepMesh import BRepMesh_IncrementalMesh
        from OCP.Standard import Standard_True
        from OCP.TopExp import TopExp
        from OCP.TopAbs import TopAbs_FACE
        
        # Write to temporary file
        with tempfile.NamedTemporaryFile(suffix='.step', delete=False) as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name
        
        try:
            # Load using CadQuery
            shape = cq.importers.importStep(tmp_path)
            
            # Mesh the shape
            mesh_algo = BRepMesh_IncrementalMesh(shape.val(), tolerance, Standard_True)
            mesh_algo.Perform()
            
            all_vertices = []
            all_triangles = []
            
            # Extract triangles from each face
            exp = TopExp()
            for face in exp.MapShapesAndAncestors(shape.val(), TopAbs_FACE, TopAbs_FACE):
                from OCP.Poly import Poly_Triangulation
                
                triangulation = Poly_Triangulation(face, False)
                if triangulation is None:
                    continue
                    
                # Extract vertices
                nodes = triangulation.Nodes()
                face_vertices = {}
                for i in range(1, nodes.Length() + 1):
                    node = nodes.Value(i)
                    all_vertices.append([node.X(), node.Y(), node.Z()])
                    face_vertices[i] = len(all_vertices) - 1
                
                # Extract triangles
                triangles = triangulation.Triangles()
                for i in range(1, triangles.Length() + 1):
                    tri = triangles.Value(i)
                    n1, n2, n3 = tri.Get()
                    all_triangles.append([face_vertices[n1], face_vertices[n2], face_vertices[n3]])
            
            if all_vertices:
                vertices_array = np.array(all_vertices, dtype=np.float32)
                bounds = [
                    float(vertices_array[:, 0].min()),
                    float(vertices_array[:, 1].min()),
                    float(vertices_array[:, 2].min()),
                    float(vertices_array[:, 0].max()),
                    float(vertices_array[:, 1].max()),
                    float(vertices_array[:, 2].max()),
                ]
                
                return {
                    "vertices": all_vertices,
                    "triangles": all_triangles,
                    "bounds": bounds,
                    "vertex_count": len(all_vertices),
                    "triangle_count": len(all_triangles)
                }
                
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
    except Exception as e:
        print(f"CadQuery processing failed: {e}")
    
    # Fallback: Try using AssImp if available
    try:
        import assimp
        
        # Write to temporary file
        with tempfile.NamedTemporaryFile(suffix='.step', delete=False) as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name
        
        try:
            scene = assimp.load(tmp_path)
            
            all_vertices = []
            all_triangles = []
            vertex_offset = 0
            
            for mesh in scene.meshes:
                # Add vertices
                for vertex in mesh.vertices:
                    all_vertices.append(vertex.tolist())
                
                # Add triangles
                for face in mesh.faces:
                    if len(face) >= 3:
                        all_triangles.append([
                            face[0] + vertex_offset,
                            face[1] + vertex_offset,
                            face[2] + vertex_offset
                        ])
                
                vertex_offset += len(mesh.vertices)
            
            if all_vertices:
                vertices_array = np.array(all_vertices, dtype=np.float32)
                bounds = [
                    float(vertices_array[:, 0].min()),
                    float(vertices_array[:, 1].min()),
                    float(vertices_array[:, 2].min()),
                    float(vertices_array[:, 0].max()),
                    float(vertices_array[:, 1].max()),
                    float(vertices_array[:, 2].max()),
                ]
                
                return {
                    "vertices": all_vertices,
                    "triangles": all_triangles,
                    "bounds": bounds,
                    "vertex_count": len(all_vertices),
                    "triangle_count": len(all_triangles)
                }
                
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
                
    except Exception as e:
        print(f"AssImp processing failed: {e}")
    
    # Fallback: Return a sample mesh and note that STEP processing is unavailable
    result = generate_sample_mesh()
    result["warning"] = "Could not process STEP file. Returning sample cube mesh. Install CadQuery with OCP support."
    return result
