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
  "geometry": {
    "vertices": [x1, y1, z1, x2, y2, z2],
    "normals": [nx1, ny1, nz1, nx2, ny2, nz2],
    "indices": [i0, i1, i2, i3, i4, i5]
  },
  "parts_metadata": [
    {
      "part_id": "part_0",
      "name": "root",
      "bounds": [min_x, min_y, min_z, max_x, max_y, max_z],
      "vertex_count": 1000,
      "triangle_count": 2000,
      "index_start": 0,
      "index_count": 6000
    }
  ],
  "stats": {
    "filename": "model.step",
    "file_size_bytes": 12345,
    "vertex_count": 1000,
    "triangle_count": 2000,
    "tolerance": 0.01,
    "part_count": 1
  },
}
```

On processing failure, API returns HTTP 500 with fail-fast error details.

### POST `/api/step/upload` (Stage 1 async flow)

Starts background processing and returns a `job_id`.

Response (`202 Accepted`):

```json
{
  "success": true,
  "job_id": "uuid",
  "status": "queued",
  "status_url": "/api/step/upload/{job_id}",
  "events_url": "/api/step/upload/{job_id}/events"
}
```

### GET `/api/step/upload/{job_id}`

Returns job status (`queued`, `processing`, `completed`, `failed`) and progress.
When completed, response includes final triangulated payload in `result`.

### GET `/api/step/upload/{job_id}/events`

Server-Sent Events (SSE) stream for real-time progress updates.

Events:
- `queued`
- `progress`
- `completed` (includes final `result`)
- `failed` (includes `error`)

Example frontend usage:

```ts
const source = new EventSource(`${API_URL}/api/step/upload/${jobId}/events`);

source.addEventListener("progress", (event) => {
  const payload = JSON.parse((event as MessageEvent).data);
  console.log(payload.progress);
});

source.addEventListener("completed", (event) => {
  const payload = JSON.parse((event as MessageEvent).data);
  console.log(payload.result.geometry);
  source.close();
});

source.addEventListener("failed", (event) => {
  const payload = JSON.parse((event as MessageEvent).data);
  console.error(payload.error);
  source.close();
});
```

### POST `/api/step/parts-2d` (async parts extraction + SVG)

Starts background processing for STEP solids extraction, part classification,
and 2D isometric SVG generation.

Form data:
- `file` (required): `.step` or `.stp`

Query params:
- `tolerance` (optional, float, default `0.01`, range `0.001..1.0`)

Response (`202 Accepted`):

```json
{
  "success": true,
  "job_id": "uuid",
  "status": "queued",
  "status_url": "/api/step/parts-2d/{job_id}",
  "events_url": "/api/step/parts-2d/{job_id}/events"
}
```

### GET `/api/step/parts-2d/{job_id}`

Returns parts-2d job status (`queued`, `processing`, `completed`, `failed`) and progress.
When completed, `result` includes:
- extracted solids metadata
- category classification (`panel`, `connector`, `other`)
- grouped 2D part drawings (`parts_2d`) with one SVG per group and `quantity`
- grouping by dimensions + volume with relative tolerance `15%`

### GET `/api/step/parts-2d/{job_id}/events`

SSE stream for parts-2d processing with events:
- `queued`
- `progress`
- `completed`
- `failed`

### POST `/api/step/assembly-analysis` (async assembly instructions generation)

Starts background processing for assembly instruction generation from STEP file.
Extracts parts, classifies them, and generates step-by-step assembly sequence.
Uses AI (OpenRouter) to analyze geometry and generate instructions, or fallback
to heuristic-based sequence if AI is unavailable.

Form data:
- `file` (required): `.step` or `.stp`

Query params:
- `tolerance` (optional, float, default `0.01`, range `0.001..1.0`)
- `preview_only` (optional, bool, default `false`)
  - `true`: quick preview SVG without AI analysis
  - `false`: full assembly step generation with AI
- `model` (optional, string, default `"openrouter/auto"`)
  - OpenRouter model ID for AI analysis (requires OPENROUTER_API_KEY in .env)

Response (`202 Accepted`):

```json
{
  "success": true,
  "job_id": "uuid",
  "status": "queued",
  "status_url": "/api/step/assembly-analysis/{job_id}",
  "events_url": "/api/step/assembly-analysis/{job_id}/events"
}
```

### GET `/api/step/assembly-analysis/{job_id}`

Returns assembly analysis job status and progress.
When completed, `result` includes:
- `mode`: `"preview_only"` or `"full_analysis"`
- `parts_2d`: extracted and grouped parts with 2D SVGs
- `assembly_steps`: array of assembly instructions
- `model_preview_svg`: quick preview of assembled model
- `stats`: analysis statistics

Assembly step structure:

```json
{
  "stepNumber": 1,
  "title": "Mount side panel",
  "description": "Connect left side panel (A) to frame using connectors",
  "partIndices": [0, 5],
  "partRoles": {"0": "side panel", "5": "connector"},
  "contextPartIndices": [],
  "exploded_svg": "<svg>...</svg>",
  "visual_assets": {
    "exploded_view": true,
    "context_parts_visible": false
  }
}
```

### GET `/api/step/assembly-analysis/{job_id}/events`

SSE stream for assembly analysis with events:
- `queued`
- `progress`
- `completed`
- `failed`


## Smoke test script

You can test meshing directly:

```bash
python test_mesh.py C:/path/to/model.step --tolerance 0.02
```

Parts 2D smoke test:

```bash
python test_parts_2d.py C:/path/to/model.step --tolerance 0.02
```

Assembly analysis smoke test:

```bash
python test_assembly_analysis.py C:/path/to/model.step --tolerance 0.02
```

With AI analysis (requires OPENROUTER_API_KEY in .env):

```bash
python test_assembly_analysis.py C:/path/to/model.step --tolerance 0.02 --model "openrouter/auto"
```

Preview mode only:

```bash
python test_assembly_analysis.py C:/path/to/model.step --tolerance 0.02 --preview-only
```

## Notes about vertex count

Large `vertex_count` can be normal:
- triangulation duplicates points across face boundaries
- fine `tolerance` increases triangle density
