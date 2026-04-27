# M3BL3X - STEP Analyzer with Assembly Instructions

A full-stack application for analyzing STEP CAD files, extracting parts, and generating furniture assembly instructions with AI-powered step-by-step guides.

## Overview

M3BL3X transforms STEP 3D models into:
1. **3D Mesh Visualization** - Interactive Three.js viewer
2. **Parts Extraction** - Individual part extraction with 2D isometric SVG drawings (IKEA style)
3. **Assembly Instructions** - AI-generated step-by-step assembly sequences with exploded views

## Architecture

```
┌─────────────────────────────────────────────────────┐
│              Frontend (Next.js)                      │
│  - 3D Mesh Viewer (Three.js)                        │
│  - Parts 2D Grid                                    │
│  - Assembly Instructions Viewer                     │
└────────────────┬────────────────────────────────────┘
                 │ HTTP/SSE
                 ↓
┌─────────────────────────────────────────────────────┐
│          Backend (FastAPI)                          │
│  ├─ POST /api/step/upload (3D mesh)                │
│  ├─ POST /api/step/parts-2d (extract parts)        │
│  └─ POST /api/step/assembly-analysis (AI steps)    │
│                                                     │
│  Processors:                                        │
│  ├─ mesh_processor.py                              │
│  ├─ parts_2d_processor.py                          │
│  └─ assembly_analysis_processor.py                 │
└─────────────────────────────────────────────────────┘
```

## Tech Stack

**Backend:**
- Python 3.11+
- FastAPI + Uvicorn
- CadQuery + OCP (OpenCascade)
- OpenRouter API (AI model routing)
- NumPy (numerical computation)

**Frontend:**
- Next.js 16
- React 19
- Three.js + React Three Fiber
- Tailwind CSS v4
- TypeScript

## Quick Start

### Prerequisites
- Node.js 18+
- Python 3.11+
- Git

### 1. Clone Repository
```bash
git clone <repository>
cd m3bl3x
```

### 2. Backend Setup

```bash
cd backend
python -m pip install -r requirements.txt
```

Create `.env` file with OpenRouter API key (optional, for AI features):
```env
OPENROUTER_API_KEY=sk-or-v1-your-key-here
```

Start backend:
```bash
python main.py
```

Server runs on `http://localhost:8002`
- Swagger Docs: `http://localhost:8002/docs`
- ReDoc: `http://localhost:8002/redoc`

### 3. Frontend Setup

```bash
cd frontend
npm install
# or: pnpm install

npm run dev
```

Frontend runs on `http://localhost:3000`

## Usage

### Upload and Analyze STEP File

1. **Select File**: Choose `.step` or `.stp` file
2. **Set Tolerance**: Adjust mesh quality (lower = detailed, higher = light)
3. **Choose Analysis**:
   - **View 3D Mesh**: 3D visualization in Three.js
   - **Extract Parts 2D**: Get part drawings in isometric view
   - **Generate Assembly**: Create assembly instructions (with optional AI analysis)

### Assembly Modes

- **Preview Only**: Fast extraction without AI (for any backend)
- **Full Analysis**: AI-powered instruction generation (requires OpenRouter API key)

## API Endpoints

### 3D Mesh Generation
```bash
POST /api/step/upload?tolerance=0.02
```
Returns: 3D vertices, normals, indices for Three.js

### Parts Extraction & 2D SVG
```bash
POST /api/step/parts-2d?tolerance=0.02
```
Returns: Extracted parts grouped by similarity, 2D isometric SVGs

**Part Classification:**
- **Panels** - Large flat elements
- **Connectors** - Small fasteners (screws, pegs, etc.)
- **Other** - Miscellaneous components

**Grouping:** Identical parts grouped with 15% tolerance on dimensions

### Assembly Analysis
```bash
POST /api/step/assembly-analysis?tolerance=0.02&preview_only=false&model=openrouter/auto
```

Returns:
- Part list with 2D drawings
- Assembly steps (6-8 typical)
- Exploded views for each step
- Part roles and relationships

## Features

### Backend Features
✅ STEP file parsing with CadQuery  
✅ Solid extraction and classification  
✅ Part grouping by similarity (15% tolerance)  
✅ Isometric 2D SVG generation  
✅ AI-powered assembly sequence generation (OpenRouter)  
✅ Fallback heuristic-based sequences  
✅ Async job processing with SSE streaming  
✅ Real-time progress tracking  

### Frontend Features
✅ Tab-based interface (3D, Parts, Assembly)  
✅ 3D model viewer with orbit controls  
✅ Parts grid with SVG previews  
✅ Step-by-step assembly guide  
✅ Exploded view diagrams  
✅ Real-time progress bars  
✅ Error handling  
✅ Mobile-responsive design  

## Configuration

### Backend
- **OPENROUTER_API_KEY**: Optional, enables AI assembly generation
- **Tolerance Range**: 0.001 - 1.0 (affects mesh detail)

### Frontend
- **NEXT_PUBLIC_API_URL**: Backend URL (default: http://localhost:8002)

## Environment Variables

**.env (Backend)**
```env
OPENROUTER_API_KEY=sk-or-v1-xxxxx  # Optional
```

**.env.local (Frontend)**
```env
NEXT_PUBLIC_API_URL=http://localhost:8002
```

## Development

### Running Tests

Backend smoke tests:
```bash
# Mesh processing
python backend/test_mesh.py assets/biurko/biurko\ standard.step --tolerance 0.02

# Parts extraction
python backend/test_parts_2d.py assets/biurko/biurko\ standard.step --tolerance 0.02

# Assembly analysis
python backend/test_assembly_analysis.py assets/biurko/biurko\ standard.step --tolerance 0.02
```

### File Structure

```
m3bl3x/
├── backend/
│   ├── app/
│   │   ├── mesh_processor.py
│   │   ├── parts_2d_processor.py
│   │   └── assembly_analysis_processor.py
│   ├── main.py
│   ├── requirements.txt
│   ├── README.md
│   └── test_*.py
├── frontend/
│   ├── app/
│   │   ├── page.tsx          # Main UI with tabs
│   │   ├── layout.tsx
│   │   └── globals.css
│   ├── package.json
│   ├── tsconfig.json
│   └── README.md
├── README.md
└── ...
```

## Performance

### Mesh Generation
- **Typical STEP file**: 2-5 seconds (tolerance 0.02)
- **Large assembly**: 5-10 seconds
- **Output**: 1000-10000 vertices, 2000-20000 triangles

### Parts Extraction
- **Part classification**: < 1 second
- **SVG generation**: < 2 seconds
- **Typical output**: 6-20 part groups

### Assembly Analysis
- **Preview mode**: < 1 second
- **Full analysis** (AI): 10-30 seconds (depends on model complexity)
- **Typical output**: 6-8 assembly steps

## Troubleshooting

### Backend won't start
```bash
# Check Python version
python --version  # Should be 3.11+

# Reinstall dependencies
pip install -r requirements.txt --upgrade

# Check if port 8002 is in use
lsof -i :8002  # macOS/Linux
netstat -ano | findstr :8002  # Windows
```

### Frontend "Failed to connect"
- Verify backend is running on `http://localhost:8002`
- Check `NEXT_PUBLIC_API_URL` in `.env.local`
- Clear browser cache

### Assembly steps not generating
- Ensure backend has `OPENROUTER_API_KEY` for AI features
- Try "Preview Only" mode first
- Check browser console for error details
- Verify STEP file is valid

### 3D model not rendering
- Check WebGL support: https://get.webgl.org/
- Try different browser
- Verify STEP file format

## API Examples

### cURL - Upload and view mesh
```bash
curl -X POST "http://localhost:8002/api/step/upload" \
  -F "file=@model.step" \
  -F "tolerance=0.02"
```

### JavaScript - Async mesh generation
```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);

const response = await fetch('http://localhost:8002/api/step/upload', {
  method: 'POST',
  body: formData
});

const job = await response.json();
const eventsUrl = job.events_url;

// Stream progress
const source = new EventSource(eventsUrl);
source.addEventListener('completed', (e) => {
  const result = JSON.parse(e.data).result;
  console.log('Mesh ready:', result.geometry);
  source.close();
});
```

## Contributing

1. Create feature branch: `git checkout -b feature/name`
2. Make changes
3. Test thoroughly
4. Commit: `git commit -m "feat: description"`
5. Push: `git push origin feature/name`
6. Create Pull Request

## License

MIT License - See LICENSE file for details

## Support

For issues and questions:
1. Check troubleshooting section
2. Review GitHub issues
3. Check backend and frontend README files
4. Enable debug logging

## Roadmap

- [ ] Support for multiple STEP files in single analysis
- [ ] Part customization and filtering
- [ ] Assembly time estimation
- [ ] BOM (Bill of Materials) export
- [ ] PDF generation for assembly instructions
- [ ] Multi-language support
- [ ] Real-time collaboration
- [ ] Advanced material/color management
