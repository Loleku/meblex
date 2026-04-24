import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

# Add the app directory to path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir))

from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from app.mesh_processor import process_step_to_mesh
from app.parts_2d_processor import process_step_to_parts_2d

app = FastAPI(title="STEP to Mesh API")

jobs: dict[str, dict] = {}
parts_2d_jobs: dict[str, dict] = {}

# Enable CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "STEP to 3D Mesh API", "version": "1.0.0"}


async def process_step_job(job_id: str, filename: str, content: bytes, tolerance: float):
    started_at = datetime.now(timezone.utc).isoformat()
    jobs[job_id]["status"] = "processing"
    jobs[job_id]["progress"] = 10
    jobs[job_id]["started_at"] = started_at

    try:
        mesh_data = await asyncio.to_thread(process_step_to_mesh, content, tolerance)
        jobs[job_id]["progress"] = 90

        jobs[job_id]["result"] = build_mesh_api_response(
            mesh_data=mesh_data,
            filename=filename,
            file_size_bytes=len(content),
            tolerance=tolerance,
        )
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["progress"] = 100
    except Exception as exc:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["progress"] = 100
        jobs[job_id]["error"] = str(exc)
    finally:
        jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()


async def process_parts_2d_job(job_id: str, filename: str, content: bytes, tolerance: float):
    started_at = datetime.now(timezone.utc).isoformat()
    parts_2d_jobs[job_id]["status"] = "processing"
    parts_2d_jobs[job_id]["progress"] = 10
    parts_2d_jobs[job_id]["started_at"] = started_at

    try:
        parts_2d_data = await asyncio.to_thread(process_step_to_parts_2d, content, tolerance)
        parts_2d_jobs[job_id]["progress"] = 90

        parts_2d_jobs[job_id]["result"] = build_parts_2d_api_response(
            parts_2d_data=parts_2d_data,
            filename=filename,
            file_size_bytes=len(content),
            tolerance=tolerance,
        )
        parts_2d_jobs[job_id]["status"] = "completed"
        parts_2d_jobs[job_id]["progress"] = 100
    except Exception as exc:
        parts_2d_jobs[job_id]["status"] = "failed"
        parts_2d_jobs[job_id]["progress"] = 100
        parts_2d_jobs[job_id]["error"] = str(exc)
    finally:
        parts_2d_jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()


def build_job_status_payload(job: dict, include_result: bool = True) -> dict:
    response = {
        "success": job["status"] != "failed",
        "job_id": job["job_id"],
        "filename": job["filename"],
        "status": job["status"],
        "progress": job["progress"],
        "created_at": job["created_at"],
        "started_at": job["started_at"],
        "completed_at": job["completed_at"],
        "tolerance": job["tolerance"],
    }

    if job["status"] == "failed":
        response["error"] = job["error"]

    if include_result and job["status"] == "completed" and job["result"]:
        response["result"] = job["result"]

    return response


def build_mesh_api_response(mesh_data: dict, filename: str, file_size_bytes: int, tolerance: float) -> dict:
    return {
        "success": True,
        "geometry": {
            "vertices": mesh_data["geometry"]["vertices"],
            "normals": mesh_data["geometry"]["normals"],
            "indices": mesh_data["geometry"]["indices"],
        },
        "parts_metadata": mesh_data["parts_metadata"],
        "stats": {
            "filename": filename,
            "file_size_bytes": file_size_bytes,
            "vertex_count": mesh_data["vertex_count"],
            "triangle_count": mesh_data["triangle_count"],
            "tolerance": tolerance,
            "part_count": len(mesh_data["parts_metadata"]),
        },
    }


def build_parts_2d_api_response(parts_2d_data: dict, filename: str, file_size_bytes: int, tolerance: float) -> dict:
    stats = {
        "filename": filename,
        "file_size_bytes": file_size_bytes,
        "tolerance": tolerance,
        **parts_2d_data.get("stats", {}),
    }

    return {
        "success": True,
        "parts_2d": parts_2d_data.get("parts_2d", []),
        "solids": parts_2d_data.get("solids", []),
        "stats": stats,
    }


@app.post("/api/step/upload")
async def upload_step_file_async(
    file: UploadFile = File(...),
    tolerance: float = Query(0.01, ge=0.001, le=1.0),
):
    if not file.filename or (
        not file.filename.lower().endswith(".step") and not file.filename.lower().endswith(".stp")
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Only .step and .stp files are supported.",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="File is empty")

    job_id = str(uuid4())
    jobs[job_id] = {
        "job_id": job_id,
        "filename": file.filename,
        "status": "queued",
        "progress": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "started_at": None,
        "completed_at": None,
        "error": None,
        "result": None,
        "tolerance": tolerance,
    }

    asyncio.create_task(process_step_job(job_id, file.filename, content, tolerance))

    return JSONResponse(
        content={
            "success": True,
            "job_id": job_id,
            "status": "queued",
            "status_url": f"/api/step/upload/{job_id}",
            "events_url": f"/api/step/upload/{job_id}/events",
        },
        status_code=202,
    )


@app.get("/api/step/upload/{job_id}")
async def get_upload_job_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JSONResponse(content=build_job_status_payload(job))


@app.get("/api/step/upload/{job_id}/events")
async def stream_upload_job_events(job_id: str, request: Request):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        last_status = None
        last_progress = None

        while True:
            current_job = jobs.get(job_id)
            if not current_job:
                payload = {"success": False, "job_id": job_id, "status": "not_found"}
                yield f"event: failed\ndata: {json.dumps(payload)}\n\n"
                break

            status = current_job["status"]
            progress = current_job["progress"]

            if status != last_status or progress != last_progress:
                payload = build_job_status_payload(current_job)
                if status == "completed":
                    event_name = "completed"
                elif status == "failed":
                    event_name = "failed"
                elif status == "processing":
                    event_name = "progress"
                else:
                    event_name = "queued"

                yield f"event: {event_name}\ndata: {json.dumps(payload)}\n\n"
                last_status = status
                last_progress = progress

            if status in {"completed", "failed"}:
                break

            if await request.is_disconnected():
                break

            await asyncio.sleep(0.25)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/step/parts-2d")
async def upload_step_file_parts_2d(
    file: UploadFile = File(...),
    tolerance: float = Query(0.01, ge=0.001, le=1.0),
):
    if not file.filename or (
        not file.filename.lower().endswith(".step") and not file.filename.lower().endswith(".stp")
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Only .step and .stp files are supported.",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="File is empty")

    job_id = str(uuid4())
    parts_2d_jobs[job_id] = {
        "job_id": job_id,
        "filename": file.filename,
        "status": "queued",
        "progress": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "started_at": None,
        "completed_at": None,
        "error": None,
        "result": None,
        "tolerance": tolerance,
    }

    asyncio.create_task(process_parts_2d_job(job_id, file.filename, content, tolerance))

    return JSONResponse(
        content={
            "success": True,
            "job_id": job_id,
            "status": "queued",
            "status_url": f"/api/step/parts-2d/{job_id}",
            "events_url": f"/api/step/parts-2d/{job_id}/events",
        },
        status_code=202,
    )


@app.get("/api/step/parts-2d/{job_id}")
async def get_parts_2d_job_status(job_id: str):
    job = parts_2d_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JSONResponse(content=build_job_status_payload(job))


@app.get("/api/step/parts-2d/{job_id}/events")
async def stream_parts_2d_job_events(job_id: str, request: Request):
    job = parts_2d_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        last_status = None
        last_progress = None

        while True:
            current_job = parts_2d_jobs.get(job_id)
            if not current_job:
                payload = {"success": False, "job_id": job_id, "status": "not_found"}
                yield f"event: failed\ndata: {json.dumps(payload)}\n\n"
                break

            status = current_job["status"]
            progress = current_job["progress"]

            if status != last_status or progress != last_progress:
                payload = build_job_status_payload(current_job)
                if status == "completed":
                    event_name = "completed"
                elif status == "failed":
                    event_name = "failed"
                elif status == "processing":
                    event_name = "progress"
                else:
                    event_name = "queued"

                yield f"event: {event_name}\ndata: {json.dumps(payload)}\n\n"
                last_status = status
                last_progress = progress

            if status in {"completed", "failed"}:
                break

            if await request.is_disconnected():
                break

            await asyncio.sleep(0.25)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/upload-step")
async def upload_step_file(
    file: UploadFile = File(...),
    tolerance: float = Query(0.01, ge=0.001, le=1.0),
):
    """
    Upload and process a STEP file.
    
    Receives a STEP file, converts it to a triangle mesh,
    and returns the mesh data in JSON format for Three.js visualization.
    
    Returns:
        JSON object containing:
        - vertices: Array of [x, y, z] coordinates
        - triangles: Array of [i, j, k] vertex indices
        - bounds: Bounding box [min_x, min_y, min_z, max_x, max_y, max_z]
        - stats: File and mesh statistics
    """
    try:
        # Validate file extension
        if not file.filename.lower().endswith('.step') and not file.filename.lower().endswith('.stp'):
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Only .step and .stp files are supported."
            )
        
        # Read file content
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="File is empty")
        
        # Process the STEP file
        mesh_data = process_step_to_mesh(content, tolerance=tolerance)
        
        # Prepare response
        response = build_mesh_api_response(
            mesh_data=mesh_data,
            filename=file.filename,
            file_size_bytes=len(content),
            tolerance=tolerance,
        )
        
        return JSONResponse(content=response)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing file: {str(e)}"
        )
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)
