# Frontend - STEP Analyzer UI

Next.js frontend for analyzing STEP CAD files with 3D mesh visualization, parts extraction, and assembly instruction generation.

## Features

- **3D Mesh Viewer**: Upload STEP files and view triangulated meshes in Three.js
- **Parts 2D Extraction**: Extract individual parts and display as isometric 2D SVG drawings
- **Assembly Instructions**: Generate step-by-step assembly guides with AI analysis (via OpenRouter)
- **Responsive UI**: Mobile-friendly tab-based interface with real-time progress tracking

## Requirements

- Node.js 18+ (recommended)
- npm or pnpm
- Backend API running on http://localhost:8002

## Setup

```bash
cd frontend
npm install
# or
pnpm install
```

## Development

```bash
npm run dev
```

Server starts on `http://localhost:3000`.

## Build & Production

```bash
npm run build
npm run start
```

## Environment Variables

Create `.env.local` if your backend is on a different URL:

```env
NEXT_PUBLIC_API_URL=http://localhost:8002
```

## Tabs

### 1. 3D Mesh
- View triangulated STEP model in 3D
- Orbit controls for navigation
- Real-time model statistics
- Adjustable mesh tolerance

### 2. Parts 2D
- Grid of extracted parts with isometric SVG drawings
- Part categories: panels, connectors, other
- Part quantities and dimensions
- Statistics: solids count, groups, category breakdown

### 3. Assembly Instructions
- Step-by-step assembly guide
- **Modes**:
  - **Preview Only**: Fast preview without AI analysis
  - **Full Analysis**: AI-powered step generation (requires OpenRouter API key in backend)
- Exploded view SVGs for each step
- Part roles and relationships
- Context-aware assembly sequence

## UI Components

### TabNav
Navigation between the three views.

### Parts2DViewer
Grid of part cards with:
- Isometric SVG preview
- Part name and category
- Quantity labels
- Dimensions

### AssemblyViewer
- Step list sidebar
- Detailed step information
- Part preview thumbnails
- Exploded view diagram
- Part roles in assembly

## API Integration

Connects to three main backend endpoints:

1. **POST `/api/step/upload`** - 3D mesh generation
2. **POST `/api/step/parts-2d`** - Parts extraction and 2D SVG generation
3. **POST `/api/step/assembly-analysis`** - Assembly instruction generation

All endpoints use:
- Async job processing with job IDs
- Server-Sent Events (SSE) for real-time progress
- Tolerance parameter for mesh quality/performance trade-off

## Features Explained

### Tolerance Control
- **Lower** (0.001-0.01): More detailed mesh, heavier
- **Higher** (0.02-0.1): Lighter mesh, coarser

### Assembly Modes
- **Preview Only** (`preview_only=true`):
  - No AI analysis
  - Just extracts and groups parts
  - Very fast

- **Full Analysis** (`preview_only=false`):
  - Requires backend to have `OPENROUTER_API_KEY` set
  - AI generates optimal assembly sequence
  - Creates exploded views
  - Returns detailed step-by-step guide with 6-8 steps typical

## Styling

Built with **Tailwind CSS v4** with custom green color palette:
- `#1f5f4a` - Primary dark green
- `#5f8f7a` - Medium green
- `#1e2522` - Very dark text
- `#56635d` - Medium gray
- `#ecf1ee` - Light background

## Browser Support

Modern browsers with WebGL support for Three.js:
- Chrome/Edge 90+
- Firefox 88+
- Safari 15+

## Troubleshooting

### "Failed to upload" errors
- Check backend is running on configured API_URL
- Verify STEP file format (.step or .stp)
- Check CORS settings if running on different domain

### Assembly steps not generating
- Ensure backend has valid OpenRouter API key
- Try "Preview Only" mode first
- Check browser console for error details

### 3D model not rendering
- Ensure WebGL is enabled in browser
- Try different browser
- Check if STEP file is valid

## Architecture

```
frontend/
├── app/
│   ├── page.tsx        # Main component with tabs
│   ├── layout.tsx
│   └── globals.css
├── package.json
└── tsconfig.json
```

The entire UI is in a single `page.tsx` file with:
- State management using React hooks
- SSE event handling for real-time updates
- Type-safe API integration with TypeScript
- Tailwind CSS styling
