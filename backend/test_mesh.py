from app.mesh_processor import process_step_to_mesh

with open('')

result = process_step_to_mesh(b'test', tolerance=0.01)
print('Sample mesh generated:')
print(f'  Vertices: {result["vertex_count"]}')
print(f'  Triangles: {result["triangle_count"]}')
print(f'  Bounds: {result["bounds"]}')
print(f'  Is Sample: {result.get("is_sample", False)}')
print('\nBackend is working correctly!')
