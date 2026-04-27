import asyncio
import json
import sys
import os
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from uuid import uuid4

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Add the app directory to path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir))

from fastapi import FastAPI, UploadFile, File, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from app.mesh_processor import process_step_to_mesh
from app.parts_2d_processor import process_step_to_parts_2d
from app.assembly_analysis_processor import process_step_to_assembly_analysis
from app.pdf_exporter import export_assembly_to_pdf

app = FastAPI(title="STEP to Mesh API")

jobs: dict[str, dict] = {}
parts_2d_jobs: dict[str, dict] = {}
assembly_analysis_jobs: dict[str, dict] = {}

# Configuration constants
MAX_FILE_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB
MAX_JOB_AGE_MINUTES = 60
MAX_CONCURRENT_JOBS = 5
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8002",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:8002",
]
if os.getenv("ENVIRONMENT") == "production":
    ALLOWED_ORIGINS = [
        os.getenv("FRONTEND_URL", "https://example.com"),
    ]

# Job processing semaphore
job_semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)

# Enable CORS for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.on_event("startup")
async def startup_event():
    """Validate configuration and start background tasks on startup."""
    # Validate OpenRouter API key if not in preview mode
    try:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            logger.warning(
                "OPENROUTER_API_KEY not set. Assembly analysis will use fallback mode. "
                "To enable AI-powered assembly, add OPENROUTER_API_KEY to .env"
            )
    except Exception as e:
        logger.error(f"Configuration validation error: {e}")
    
    # Start background cleanup task
    asyncio.create_task(cleanup_old_jobs())
    logger.info("Job cleanup task started")


async def cleanup_old_jobs():
    """Periodically remove old jobs from memory to prevent memory leaks."""
    while True:
        try:
            await asyncio.sleep(300)  # Run cleanup every 5 minutes
            now = datetime.now(timezone.utc)
            cutoff_time = now - timedelta(minutes=MAX_JOB_AGE_MINUTES)
            
            removed_count = 0
            for job_dict in [jobs, parts_2d_jobs, assembly_analysis_jobs]:
                expired_job_ids = []
                for job_id, job in job_dict.items():
                    try:
                        completed_at = job.get("completed_at")
                        if completed_at:
                            completed_time = datetime.fromisoformat(completed_at)
                            if completed_time < cutoff_time:
                                expired_job_ids.append(job_id)
                    except Exception as e:
                        logger.warning(f"Error checking job expiration: {e}")
                
                for job_id in expired_job_ids:
                    del job_dict[job_id]
                    removed_count += 1
            
            if removed_count > 0:
                logger.info(f"Cleaned up {removed_count} expired jobs")
        except Exception as e:
            logger.error(f"Error in job cleanup: {e}")


@app.get("/")
async def root():
    return {"message": "STEP to 3D Mesh API", "version": "1.0.0"}


async def process_step_job(job_id: str, filename: str, content: bytes, tolerance: float):
    """Process STEP file and convert to mesh."""
    async with job_semaphore:  # Limit concurrent jobs
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
            logger.error(f"Error processing job {job_id}: {exc}")
        finally:
            jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()


async def process_parts_2d_job(job_id: str, filename: str, content: bytes, tolerance: float):
    """Extract and process 2D parts from STEP file."""
    async with job_semaphore:  # Limit concurrent jobs
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
            logger.error(f"Error processing 2D parts job {job_id}: {exc}")
        finally:
            parts_2d_jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()


async def process_assembly_analysis_job(
    job_id: str,
    filename: str,
    content: bytes,
    tolerance: float,
    preview_only: bool,
    model: str,
):
    """Generate assembly analysis from STEP file."""
    async with job_semaphore:  # Limit concurrent jobs
        started_at = datetime.now(timezone.utc).isoformat()
        assembly_analysis_jobs[job_id]["status"] = "processing"
        assembly_analysis_jobs[job_id]["progress"] = 10
        assembly_analysis_jobs[job_id]["started_at"] = started_at

        try:
            analysis_data = await asyncio.to_thread(
                process_step_to_assembly_analysis,
                content,
                tolerance,
                preview_only,
                model,
            )
            assembly_analysis_jobs[job_id]["progress"] = 90

            assembly_analysis_jobs[job_id]["result"] = build_assembly_analysis_api_response(
                analysis_data=analysis_data,
                filename=filename,
                file_size_bytes=len(content),
                tolerance=tolerance,
                preview_only=preview_only,
            )
            assembly_analysis_jobs[job_id]["status"] = "completed"
            assembly_analysis_jobs[job_id]["progress"] = 100
        except Exception as exc:
            assembly_analysis_jobs[job_id]["status"] = "failed"
            assembly_analysis_jobs[job_id]["progress"] = 100
            assembly_analysis_jobs[job_id]["error"] = str(exc)
            logger.error(f"Error processing assembly analysis job {job_id}: {exc}")
        finally:
            assembly_analysis_jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()


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


def build_assembly_analysis_api_response(
    analysis_data: dict,
    filename: str,
    file_size_bytes: int,
    tolerance: float,
    preview_only: bool,
) -> dict:
    stats = {
        "filename": filename,
        "file_size_bytes": file_size_bytes,
        "tolerance": tolerance,
        "preview_only": preview_only,
        **analysis_data.get("stats", {}),
    }

    return {
        "success": True,
        "mode": analysis_data.get("mode", "full_analysis"),
        "parts_2d": analysis_data.get("parts_2d", []),
        "solids": analysis_data.get("solids", []),
        "assembly_steps": analysis_data.get("assembly_steps", []),
        "model_preview_svg": analysis_data.get("model_preview_svg", ""),
        "stats": stats,
    }


@app.post("/api/step/upload")
async def upload_step_file_async(
    file: UploadFile = File(...),
    tolerance: float = Query(0.01, ge=0.001, le=1.0),
):
    """Upload STEP file and start async mesh processing."""
    if not file.filename or (
        not file.filename.lower().endswith(".step") and not file.filename.lower().endswith(".stp")
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Only .step and .stp files are supported.",
        )

    content = await file.read()
    
    # Validate file size
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum file size is {MAX_FILE_SIZE_BYTES // 1024 // 1024} MB.",
        )
    
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
    """Stream upload job progress events to frontend."""
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        last_status = None
        last_progress = None

        try:
            while True:
                try:
                    current_job = jobs.get(job_id)
                    if not current_job:
                        payload = {"success": False, "job_id": job_id, "status": "not_found"}
                        yield f"event: failed\ndata: {json.dumps(payload)}\n\n"
                        break

                    status = current_job.get("status", "unknown")
                    progress = current_job.get("progress", 0)

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
                except (KeyError, TypeError) as e:
                    logger.error(f"Error accessing job state: {e}")
                    payload = {"success": False, "error": "Job state error"}
                    yield f"event: error\ndata: {json.dumps(payload)}\n\n"
                    break
        except Exception as e:
            logger.error(f"Event stream error: {e}")

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
    """Upload STEP file and start async 2D parts extraction."""
    if not file.filename or (
        not file.filename.lower().endswith(".step") and not file.filename.lower().endswith(".stp")
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Only .step and .stp files are supported.",
        )

    content = await file.read()
    
    # Validate file size
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum file size is {MAX_FILE_SIZE_BYTES // 1024 // 1024} MB.",
        )
    
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
    """Stream parts 2D job progress events to frontend."""
    job = parts_2d_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        last_status = None
        last_progress = None

        try:
            while True:
                try:
                    current_job = parts_2d_jobs.get(job_id)
                    if not current_job:
                        payload = {"success": False, "job_id": job_id, "status": "not_found"}
                        yield f"event: failed\ndata: {json.dumps(payload)}\n\n"
                        break

                    status = current_job.get("status", "unknown")
                    progress = current_job.get("progress", 0)

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
                except (KeyError, TypeError) as e:
                    logger.error(f"Error accessing job state: {e}")
                    payload = {"success": False, "error": "Job state error"}
                    yield f"event: error\ndata: {json.dumps(payload)}\n\n"
                    break
        except Exception as e:
            logger.error(f"Event stream error: {e}")

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
    Upload and process a STEP file synchronously.
    
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
        
        # Validate file size
        if len(content) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum file size is {MAX_FILE_SIZE_BYTES // 1024 // 1024} MB."
            )
        
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
        logger.error(f"Error processing file {file.filename}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing file: {str(e)}"
        )


@app.post("/api/step/assembly-analysis")
async def upload_step_file_assembly_analysis(
    file: UploadFile = File(...),
    tolerance: float = Query(0.01, ge=0.001, le=1.0),
    preview_only: bool = Query(False),
    model: str = Query("openrouter/auto"),
):
    """
    Upload STEP file and start async assembly analysis.
    
    Parameters:
    - file: STEP/STP file
    - tolerance: Mesh tolerance (0.001-1.0)
    - preview_only: If true, only show preview without AI analysis
    - model: OpenRouter model ID (default: openrouter/auto)
    
    Returns:
        JSON object containing:
        - parts_2d: Extracted and grouped parts with 2D SVGs
        - assembly_steps: Step-by-step assembly instructions
        - model_preview_svg: Quick preview of assembled model
        - stats: Analysis statistics
    """
    if not file.filename or (
        not file.filename.lower().endswith(".step")
        and not file.filename.lower().endswith(".stp")
    ):
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Only .step and .stp files are supported.",
        )

    content = await file.read()
    
    # Validate file size
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum file size is {MAX_FILE_SIZE_BYTES // 1024 // 1024} MB.",
        )
    
    if not content:
        raise HTTPException(status_code=400, detail="File is empty")

    job_id = str(uuid4())
    assembly_analysis_jobs[job_id] = {
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
        "preview_only": preview_only,
        "model": model,
    }

    asyncio.create_task(
        process_assembly_analysis_job(
            job_id, file.filename, content, tolerance, preview_only, model
        )
    )

    return JSONResponse(
        content={
            "success": True,
            "job_id": job_id,
            "status": "queued",
            "status_url": f"/api/step/assembly-analysis/{job_id}",
            "events_url": f"/api/step/assembly-analysis/{job_id}/events",
        },
        status_code=202,
    )


@app.get("/api/step/assembly-analysis/{job_id}")
async def get_assembly_analysis_job_status(job_id: str):
    job = assembly_analysis_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JSONResponse(content=build_job_status_payload(job))


@app.get("/api/step/assembly-analysis/{job_id}/events")
async def stream_assembly_analysis_job_events(job_id: str, request: Request):
    """Stream assembly analysis job progress events to frontend."""
    job = assembly_analysis_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        last_status = None
        last_progress = None

        try:
            while True:
                try:
                    current_job = assembly_analysis_jobs.get(job_id)
                    if not current_job:
                        payload = {"success": False, "job_id": job_id, "status": "not_found"}
                        yield f"event: failed\ndata: {json.dumps(payload)}\n\n"
                        break

                    status = current_job.get("status", "unknown")
                    progress = current_job.get("progress", 0)

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
                except (KeyError, TypeError) as e:
                    logger.error(f"Error accessing job state: {e}")
                    payload = {"success": False, "error": "Job state error"}
                    yield f"event: error\ndata: {json.dumps(payload)}\n\n"
                    break
        except Exception as e:
            logger.error(f"Event stream error: {e}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/step/export/pdf/{job_id}")
async def export_assembly_pdf(job_id: str):
    """
    Export assembly analysis results to PDF.
    
    Requires that the assembly analysis job with job_id has completed successfully.
    
    Args:
        job_id: ID of completed assembly analysis job
    
    Returns:
        PDF file as binary attachment
    """
    job = assembly_analysis_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Assembly job not found")
    
    if job["status"] != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job status is {job['status']}, expected 'completed'"
        )
    
    result = job.get("result")
    if not result:
        raise HTTPException(status_code=400, detail="No assembly data available for export")
    
    # Validate required fields
    required_fields = ["parts_2d", "assembly_steps"]
    missing = [f for f in required_fields if not result.get(f)]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Incomplete assembly data: missing {', '.join(missing)}"
        )
    
    try:
        pdf_bytes = export_assembly_to_pdf(result)
        return StreamingResponse(
            iter([pdf_bytes]),
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=assembly_instructions.pdf"}
        )
    except Exception as e:
        logger.error(f"PDF generation failed for job {job_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"PDF generation failed: {str(e)}"
        )
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)
