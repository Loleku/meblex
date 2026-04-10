```
# Backend - STEP to Mesh API

FastAPI backend for processing STEP files and converting them to 3D triangle meshes for visualization with Three.js.

## Project Structure

```
backend/
├── main.py              # FastAPI application entry point
├── app/
│   ├── __init__.py      # Package marker
│   └── mesh_processor.py  # Core STEP processing module
├── requirements.txt     # Python dependencies
└── test_mesh.py         # Test script for mesh processing
```

## Setup

### 1. Install Dependencies

```bash
cd backend
python -m pip install -r requirements.txt
```

### 2. Enable Real STEP Processing (Optional)

The backend currently uses a sample mesh fallback. To enable real STEP file processing, install one of:

#### Option A: CadQuery with OpenCASCADE (Recommended)

```bash
# This requires pre-built wheels - not available for Python 3.14 yet
# Consider using Python 3.11 or earlier for full support
pip install cadquery pythonocc-core
```

#### Option B: AssImp

```bash
# For AssImp support
pip install pyassimp
# You'll also need Assimp library installed on your system
```

## Running the Server

```bash
# Development mode with auto-reload
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Production mode
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

The API will be available at: `http://localhost:8000`

### API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API Endpoints

### GET `/`

Health check endpoint.

**Response:**
```json
{
  "message": "STEP to 3D Mesh API",
  "version": "1.0.0"
}
```

### POST `/api/upload-step`

Upload and process a STEP file.

**Parameters:**
- `file` (FormData, required): STEP file (.step or .stp)

**Response:**
```json
{
  "success": true,
  "mesh": {
    "vertices": [[x1, y1, z1], [x2, y2, z2], ...],
    "triangles": [[i1, j1, k1], [i2, j2, k2], ...],
    "bounds": [min_x, min_y, min_z, max_x, max_y, max_z]
  },
  "stats": {
    "filename": "model.step",
    "file_size_bytes": 12345,
    "vertex_count": 1000,
    "triangle_count": 500
  }
}
```

**Example with curl:**
```bash
curl -X POST "http://localhost:8000/api/upload-step" \
  -F "file=@model.step"
```

## Features

- **STEP File Support**: Reads `.step` and `.stp` files
- **Triangle Mesh Conversion**: Automatically triangulates 3D geometry
- **JSON Output**: Returns mesh data in JSON format suitable for Three.js
- **Bounding Box Calculation**: Includes geometry bounds for visualization
- **CORS Enabled**: Ready for browser-based frontends
- **Error Handling**: Comprehensive error messages for debugging

## Testing

Run the test script to verify the backend is working:

```bash
python test_mesh.py
```

Expected output:
```
Sample mesh generated:
  Vertices: 8
  Triangles: 12
  Bounds: [0.0, 0.0, 0.0, 1.0, 1.0, 1.0]
  Is Sample: True

Backend is working correctly!
```

## Current Limitations

Due to Python 3.14 package availability limitations:

1. **Real STEP Processing Not Available**: The current setup uses a sample cube mesh as fallback
2. **OCP Bindings**: OpenCASCADE Python bindings not available for Python 3.14
3. **AssImp**: Python bindings not available for Python 3.14

### Workaround

Use Python 3.11 or earlier to enable full STEP processing with CadQuery and OpenCASCADE.

## Mesh Processor Module

### Function: `process_step_to_mesh(file_content, tolerance=0.01)`

Converts STEP file bytes to a triangle mesh.

**Parameters:**
- `file_content` (bytes): Raw STEP file content
- `tolerance` (float): Mesh refinement tolerance (lower = finer mesh)

**Returns:**
```python
{
    "vertices": [[x, y, z], ...],     # List of vertex coordinates
    "triangles": [[i, j, k], ...],    # List of triangle indices
    "bounds": [x_min, y_min, z_min, x_max, y_max, z_max],  # Bounding box
    "vertex_count": int,              # Number of vertices
    "triangle_count": int,            # Number of triangles
    "is_sample": bool,                # Whether sample mesh was generated
    "warning": str                    # Optional warning message
}
```

## Technology Stack

- **FastAPI**: Modern Python web framework
- **Uvicorn**: ASGI server
- **NumPy**: Numerical computations
- **CadQuery**: CAD file processing (optional)
- **OpenCASCADE**: 3D geometry kernel (optional)
- **AssImp**: Model import library (optional)

## Next Steps

1. **Setup Frontend**: Create Three.js visualization component
2. **Real STEP Processing**: Install Python 3.11 and required dependencies for full support
3. **Performance Optimization**: Implement mesh decimation for large models
4. **File Caching**: Add temporary file storage for batch processing
5. **WebSocket Support**: Add real-time processing updates
```
