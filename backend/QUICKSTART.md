## Quick Start - Backend

### 1) Install dependencies

```bash
cd backend
python -m pip install -r requirements.txt
```

### 2) Start API

```bash
python main.py
```

Expected:

```
Uvicorn running on http://0.0.0.0:8002
```

### 3) Try upload from Swagger

Open:

```
http://localhost:8002/docs
```

Use `POST /api/upload-step`:
- choose `.step`/`.stp` file
- optionally set `tolerance` query param

### 4) cURL example

```bash
curl -X POST "http://localhost:8002/api/upload-step?tolerance=0.02" \
  -F "file=@your_model.step"
```

### 4b) Stage 1 async endpoint

Start job:

```bash
curl -X POST "http://localhost:8002/api/step/upload?tolerance=0.02" \
  -F "file=@your_model.step"
```

Check status:

```bash
curl "http://localhost:8002/api/step/upload/<job_id>"
```

SSE progress stream:

```bash
curl -N "http://localhost:8002/api/step/upload/<job_id>/events"
```

### 4c) Parts 2D async endpoint

Start parts job:

```bash
curl -X POST "http://localhost:8002/api/step/parts-2d?tolerance=0.02" \
  -F "file=@your_model.step"
```

Check parts status:

```bash
curl "http://localhost:8002/api/step/parts-2d/<job_id>"
```

Parts SSE stream:

```bash
curl -N "http://localhost:8002/api/step/parts-2d/<job_id>/events"
```

### 5) Optional smoke test

```bash
python test_mesh.py C:/path/to/your_model.step --tolerance 0.02
```

```bash
python test_parts_2d.py C:/path/to/your_model.step --tolerance 0.02
```

## Tolerance tips

- `0.001 - 0.01`: very detailed, heavy meshes
- `0.02 - 0.05`: good default for interactive preview
- `0.1+`: coarse preview, fewer triangles
