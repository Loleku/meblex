import sys
from pathlib import Path

# Add the app directory to path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir))

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mesh_processor import process_step_to_mesh

app = FastAPI(title="STEP to Mesh API")

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


@app.post("/api/upload-step")
async def upload_step_file(file: UploadFile = File(...)):
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
        mesh_data = process_step_to_mesh(content, tolerance=0.01)
        
        # Prepare response
        response = {
            "success": True,
            "mesh": {
                "vertices": mesh_data["vertices"],
                "triangles": mesh_data["triangles"],
                "bounds": mesh_data["bounds"],
            },
            "stats": {
                "filename": file.filename,
                "file_size_bytes": len(content),
                "vertex_count": mesh_data["vertex_count"],
                "triangle_count": mesh_data["triangle_count"],
            }
        }
        
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
    uvicorn.run(app, host="0.0.0.0", port=8002, reload=True)
