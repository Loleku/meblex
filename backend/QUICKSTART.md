## Quick Start - Backend

### 1. Start the API Server

From the `backend` directory:

```bash
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

You should see:
```
Uvicorn running on http://0.0.0.0:8000
```

### 2. Test the API

**Option A: Using Swagger UI (Browser)**
```
http://localhost:8000/docs
```

Click "Try it out" on the `/api/upload-step` endpoint to upload a STEP file.

**Option B: Using curl**
```bash
curl -X POST "http://localhost:8000/api/upload-step" \
  -F "file=@your_model.step"
```

**Option C: Using Python**
```python
import requests

with open('model.step', 'rb') as f:
    files = {'file': f}
    response = requests.post('http://localhost:8000/api/upload-step', files=files)
    mesh_data = response.json()
    
print(f"Vertices: {mesh_data['stats']['vertex_count']}")
print(f"Triangles: {mesh_data['stats']['triangle_count']}")
```

### 3. API Response Format

```json
{
  "success": true,
  "mesh": {
    "vertices": [[0, 0, 0], [1, 0, 0], [1, 1, 0], ...],
    "triangles": [[0, 1, 2], [0, 2, 3], ...],
    "bounds": [0, 0, 0, 1, 1, 1]
  },
  "stats": {
    "filename": "model.step",
    "file_size_bytes": 12345,
    "vertex_count": 100,
    "triangle_count": 50
  }
}
```

### Current Status

✅ **API is working**
✅ **Mesh data format is ready for Three.js**
⚠️ **Currently returning sample cube** (real STEP processing requires Python 3.11 or earlier)

### To Use Real STEP Files

1. Switch to Python 3.11 or earlier
2. Reinstall dependencies:
   ```bash
   pip install -r requirements.txt
   ```

This will install CadQuery with OpenCASCADE support for real STEP file processing.
