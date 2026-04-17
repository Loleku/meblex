# Backend - STEP to Mesh API

FastAPI backend that accepts STEP files and returns triangulated mesh data for Three.js / React Three Fiber.

## Requirements

- Python 3.11 or 3.12 recommended
- Dependencies from `requirements.txt`

## Setup

```bash
cd backend
python -m pip install -r requirements.txt
```

## Run

```bash
python main.py
```

Server starts on `http://localhost:8002`.

Docs:
- Swagger UI: `http://localhost:8002/docs`
- ReDoc: `http://localhost:8002/redoc`

## API

### GET `/`

Health response:

```json
{
  "message": "STEP to 3D Mesh API",
  "version": "1.0.0"
}
```

### POST `/api/upload-step`

Uploads and triangulates a STEP file.

Form data:
- `file` (required): `.step` or `.stp`

Query params:
- `tolerance` (optional, float, default `0.01`, range `0.001..1.0`)
  - lower = denser mesh
  - higher = lighter mesh

Success response:

```json
{
  "success": true,
  "mesh": {
    "vertices": [[x, y, z], [x, y, z]],
    "triangles": [[i, j, k], [i, j, k]],
    "bounds": [min_x, min_y, min_z, max_x, max_y, max_z]
  },
  "stats": {
    "filename": "model.step",
    "file_size_bytes": 12345,
    "vertex_count": 1000,
    "triangle_count": 2000,
    "tolerance": 0.01
  }
}
```

On processing failure, API returns HTTP 500 with fail-fast error details.

## Smoke test script

You can test meshing directly:

```bash
python test_mesh.py C:/path/to/model.step --tolerance 0.02
```

## Notes about vertex count

Large `vertex_count` can be normal:
- triangulation duplicates points across face boundaries
- fine `tolerance` increases triangle density
