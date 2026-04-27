"use client";

import { FormEvent, useMemo, useState, useEffect } from "react";
import { Canvas } from "@react-three/fiber";
import { Bounds, OrbitControls } from "@react-three/drei";
import * as THREE from "three";

type GeometryData = {
  vertices: number[];
  normals: number[];
  indices: number[];
};

type PartMetadata = {
  part_id: string;
  name: string;
  bounds: [number, number, number, number, number, number];
  vertex_count: number;
  triangle_count: number;
  index_start: number;
  index_count: number;
};

type UploadResponse = {
  success: boolean;
  geometry: GeometryData;
  parts_metadata: PartMetadata[];
  stats: {
    filename: string;
    file_size_bytes: number;
    vertex_count: number;
    triangle_count: number;
    tolerance: number;
    part_count: number;
  };
};

type AsyncUploadResponse = {
  success: boolean;
  job_id: string;
  status: "queued";
  status_url: string;
  events_url: string;
};

type JobEventPayload = {
  success: boolean;
  job_id: string;
  filename: string;
  status: "queued" | "processing" | "completed" | "failed";
  progress: number;
  error?: string;
  result?: UploadResponse;
};

// Parts 2D types
type Part2D = {
  group_id: string;
  name: string;
  category: "panel" | "connector" | "other";
  quantity: number;
  quantity_label: string;
  part_ids: string[];
  dimensions: [number, number, number];
  svg: string;
  view_box: [number, number, number, number];
};

type Parts2DResponse = {
  success: boolean;
  parts_2d: Part2D[];
  solids: Array<{
    part_id: string;
    category: string;
    is_small: boolean;
    dimensions: [number, number, number];
    volume: number;
  }>;
  stats: {
    solids_count: number;
    groups_count: number;
    category_counts: { panel: number; connector: number; other: number };
    projection: string;
    group_tolerance: number;
  };
};

// Assembly Analysis types
type PartRole = {
  [partIndex: string]: string;
};

type AssemblyStep = {
  stepNumber: number;
  title: string;
  description: string;
  partIndices: number[];
  partRoles: PartRole;
  contextPartIndices: number[];
  exploded_svg?: string;
  visual_assets?: {
    exploded_view: boolean;
    context_parts_visible: boolean;
  };
};

type AssemblyAnalysisResponse = {
  success: boolean;
  mode: "preview_only" | "full_analysis";
  parts_2d: Part2D[];
  assembly_steps: AssemblyStep[];
  model_preview_svg: string;
  stats: {
    assembly_steps_count: number;
    total_parts_groups: number;
    total_individual_parts: number;
  };
};

type JobEventPayloadParts2D = Omit<JobEventPayload, "result"> & {
  result?: Parts2DResponse;
};

type JobEventPayloadAssembly = Omit<JobEventPayload, "result"> & {
  result?: AssemblyAnalysisResponse;
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8002";

function ModelMesh({ geometry }: { geometry: GeometryData }) {
  const meshGeometry = useMemo(() => {
    const g = new THREE.BufferGeometry();

    const positions = new Float32Array(geometry.vertices);
    const normals = new Float32Array(geometry.normals);
    const indices = new Uint32Array(geometry.indices);

    g.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    g.setAttribute("normal", new THREE.BufferAttribute(normals, 3));
    g.setIndex(new THREE.BufferAttribute(indices, 1));

    g.computeBoundingBox();
    const box = g.boundingBox;
    if (box) {
      const size = new THREE.Vector3();
      box.getSize(size);
      const maxSize = Math.max(size.x, size.y, size.z);
      if (maxSize > 0) {
        g.center();
        const scale = 2 / maxSize;
        g.scale(scale, scale, scale);
      }
    }

    g.computeBoundingSphere();

    return g;
  }, [geometry]);

  return (
    <mesh geometry={meshGeometry} castShadow receiveShadow>
      <meshStandardMaterial color="#5f8f7a" metalness={0.2} roughness={0.65} />
    </mesh>
  );
}

// Tab navigation component
function TabNav({
  activeTab,
  onTabChange,
}: {
  activeTab: "mesh" | "parts2d" | "assembly";
  onTabChange: (tab: "mesh" | "parts2d" | "assembly") => void;
}) {
  const tabs = [
    { id: "mesh", label: "3D Mesh", color: "yellow" },
    { id: "parts2d", label: "Components", color: "yellow" },
    { id: "assembly", label: "Assembly Guide", color: "yellow" },
  ] as const;

  return (
    <div className="mx-4 mt-4 grid gap-2 rounded-3xl border border-slate-200/80 bg-slate-100/80 p-2 shadow-sm shadow-slate-200/60 sm:grid-cols-3">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          onClick={() => onTabChange(tab.id)}
          className={`relative overflow-hidden rounded-2xl px-4 py-3 text-sm font-semibold transition-all duration-200 ${
            activeTab === tab.id
              ? "bg-white text-slate-950 shadow-md ring-1 ring-amber-200/80"
              : "text-slate-500 hover:bg-white/70 hover:text-slate-900"
          }`}
        >
          <span className="relative z-10">{tab.label}</span>
          {activeTab === tab.id && (
            <span className="absolute inset-x-4 bottom-2 h-1 rounded-full bg-gradient-to-r from-amber-500 via-yellow-500 to-orange-500" />
          )}
        </button>
      ))}
    </div>
  );
}

// Parts 2D viewer component
function Parts2DViewer({ parts, stats }: { parts: Part2D[]; stats: Parts2DResponse["stats"] }) {
  return (
    <div className="space-y-6 p-4 sm:p-6">
      <div className="relative overflow-hidden rounded-3xl border border-amber-200/70 bg-gradient-to-br from-amber-50 via-white to-orange-50 p-6 shadow-lg shadow-amber-100/60">
        <div className="pointer-events-none absolute -right-10 -top-10 h-32 w-32 rounded-full bg-amber-300/30 blur-3xl" />
        <div className="pointer-events-none absolute bottom-0 left-0 h-24 w-24 rounded-full bg-orange-300/20 blur-3xl" />
        <div className="relative space-y-5">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-amber-700">Component Summary</p>
              <h3 className="mt-1 text-2xl font-semibold text-slate-950">Clean 2D component sheets</h3>
            </div>
            <span className="w-fit rounded-full border border-amber-200 bg-white/80 px-3 py-1 text-xs font-semibold text-amber-700 shadow-sm">
              {stats.projection}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
            <div className="rounded-2xl border border-white/70 bg-white/90 p-4 shadow-sm shadow-amber-100/40">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Total Parts</p>
              <p className="mt-1 text-3xl font-bold text-slate-950">{stats.solids_count}</p>
            </div>
            <div className="rounded-2xl border border-white/70 bg-white/90 p-4 shadow-sm shadow-amber-100/40">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Groups</p>
              <p className="mt-1 text-3xl font-bold text-slate-950">{stats.groups_count}</p>
            </div>
            <div className="rounded-2xl border border-white/70 bg-white/90 p-4 shadow-sm shadow-amber-100/40">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Panels</p>
              <p className="mt-1 text-3xl font-bold text-slate-950">{stats.category_counts.panel}</p>
            </div>
            <div className="rounded-2xl border border-white/70 bg-white/90 p-4 shadow-sm shadow-amber-100/40">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Connectors</p>
              <p className="mt-1 text-3xl font-bold text-slate-950">{stats.category_counts.connector}</p>
            </div>
          </div>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {parts.map((part) => (
          <div
            key={part.group_id}
            className="group overflow-hidden rounded-3xl border border-slate-200/80 bg-white/90 p-4 shadow-sm shadow-slate-200/60 transition-all duration-200 hover:-translate-y-1 hover:border-amber-300 hover:shadow-xl hover:shadow-amber-100/40"
          >
            <div className="mb-4 flex items-start justify-between gap-3">
              <div className="min-w-0">
                <h4 className="truncate text-base font-semibold text-slate-950">{part.name}</h4>
                <p className="mt-1 text-xs text-slate-500">{part.part_ids.length} linked piece(s)</p>
              </div>
              <span className={`inline-flex shrink-0 items-center rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-wide text-white shadow-sm ${
                part.category === "panel"
                  ? "bg-gradient-to-r from-amber-500 to-orange-500"
                  : part.category === "connector"
                    ? "bg-gradient-to-r from-emerald-500 to-teal-500"
                    : "bg-gradient-to-r from-slate-500 to-slate-700"
              }`}>
                {part.quantity_label}
              </span>
            </div>
            <div className="space-y-2 text-sm">
              <p className="text-xs text-slate-600">
                <span className="font-semibold text-slate-700">Type:</span> <span className="capitalize font-medium text-slate-900">{part.category}</span>
              </p>
              <p className="text-xs text-slate-600">
                <span className="font-semibold text-slate-700">Size:</span> {part.dimensions[0].toFixed(1)} × {part.dimensions[1].toFixed(1)} × {part.dimensions[2].toFixed(1)}
              </p>
            </div>
            <div className="mt-4 overflow-hidden rounded-2xl border border-slate-200 bg-gradient-to-br from-slate-50 to-slate-100 p-3">
              <svg
                viewBox={`0 0 ${part.view_box[2]} ${part.view_box[3]}`}
                className="h-36 w-full"
                dangerouslySetInnerHTML={{ __html: part.svg }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// Assembly instructions viewer component
function AssemblyViewer({
  steps,
  parts,
  stats,
  mode,
}: {
  steps: AssemblyStep[];
  parts: Part2D[];
  stats: AssemblyAnalysisResponse["stats"];
  mode: "preview_only" | "full_analysis";
}) {
  const [selectedStep, setSelectedStep] = useState(0);
  const [isExporting, setIsExporting] = useState(false);

  const currentStep = steps[selectedStep];

  const handleExportPDF = async () => {
    const jobId = sessionStorage.getItem("lastAssemblyJobId");
    if (!jobId) {
      alert("No assembly job found. Please generate assembly instructions first.");
      return;
    }

    setIsExporting(true);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8002";
      const response = await fetch(`${apiUrl}/api/step/export/pdf/${jobId}`);

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "PDF export failed");
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "assembly_instructions.pdf";
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (error) {
      console.error("PDF export error:", error);
      alert(`Failed to export PDF: ${error instanceof Error ? error.message : "Unknown error"}`);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="space-y-5 p-4 sm:p-6">
      <div className="relative overflow-hidden rounded-3xl border border-amber-200/70 bg-gradient-to-br from-amber-50 via-white to-orange-50 p-6 shadow-lg shadow-amber-100/50">
        <div className="pointer-events-none absolute -left-10 top-0 h-24 w-24 rounded-full bg-amber-300/25 blur-3xl" />
        <div className="relative flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div className="max-w-2xl space-y-2">
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-amber-700">Assembly Instructions</p>
            <h3 className="text-2xl font-semibold text-slate-950">Step-by-step guide with visual context</h3>
            <p className="text-sm leading-6 text-slate-600">
              <span className="font-semibold text-slate-800">Mode:</span>{" "}
              <span className="capitalize text-amber-700">
                {mode === "preview_only" ? "Preview Mode" : "AI-Powered Full Analysis"}
              </span>
              <span className="mx-2 text-slate-300">•</span>
              <span className="font-semibold text-slate-800">Parts:</span> {stats.total_individual_parts}
              <span className="mx-2 text-slate-300">•</span>
              <span className="font-semibold text-slate-800">Groups:</span> {stats.total_parts_groups}
              <span className="mx-2 text-slate-300">•</span>
              <span className="font-semibold text-slate-800">Steps:</span> {stats.assembly_steps_count}
            </p>
          </div>
          <button
            onClick={handleExportPDF}
            disabled={isExporting || steps.length === 0}
            className="inline-flex items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-slate-950 via-slate-900 to-slate-800 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-slate-300/50 transition-all hover:-translate-y-0.5 hover:shadow-xl disabled:cursor-not-allowed disabled:opacity-50 whitespace-nowrap"
          >
            {isExporting ? (
              <>
                <span className="animate-spin">⏳</span>
                Exporting...
              </>
            ) : (
              <>
                <span>⬇</span>
                Export PDF
              </>
            )}
          </button>
        </div>
      </div>

      {steps.length === 0 ? (
        <div className="rounded-3xl border border-dashed border-slate-300 bg-white/85 p-10 text-center shadow-sm">
          <p className="mb-2 text-lg font-semibold text-slate-900">No assembly steps generated</p>
          <p className="text-sm text-slate-500">Try running the assembly generation with full analysis mode enabled.</p>
        </div>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
          <div className="rounded-3xl border border-slate-200/80 bg-white/90 overflow-hidden shadow-sm shadow-slate-200/60">
            <div className="border-b border-slate-200/80 bg-slate-50/80 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Assembly Steps</p>
            </div>
            <div className="max-h-[640px] overflow-y-auto p-2">
              {steps.map((step, index) => (
                <button
                  key={step.stepNumber}
                  onClick={() => setSelectedStep(index)}
                  className={`group w-full rounded-2xl px-4 py-3 text-left text-sm transition-all duration-200 ${
                    selectedStep === index
                      ? "bg-gradient-to-r from-amber-100 to-orange-50 text-slate-950 shadow-sm ring-1 ring-amber-200"
                      : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                  }`}
                >
                  <p className="flex items-start gap-3">
                    <span
                      className={`mt-0.5 inline-flex h-2.5 w-2.5 shrink-0 rounded-full ${
                        selectedStep === index ? "bg-amber-500" : "bg-slate-300 group-hover:bg-slate-400"
                      }`}
                    />
                    <span className="min-w-0">
                      <span className="block text-[11px] font-semibold uppercase tracking-[0.2em] text-slate-400">
                        Step {step.stepNumber}
                      </span>
                      <span className="mt-1 block font-medium">{step.title}</span>
                    </span>
                  </p>
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-4">
            {currentStep && (
              <>
                <div className="rounded-3xl border border-slate-200/80 bg-white/90 p-6 shadow-sm shadow-slate-200/60">
                  <div className="mb-5 flex items-start gap-4">
                    <span className="grid h-12 w-12 place-items-center rounded-2xl bg-gradient-to-br from-amber-100 to-orange-100 text-2xl shadow-sm">
                      ⚙
                    </span>
                    <div className="flex-1">
                      <h4 className="text-lg font-semibold text-slate-950">
                        Step {currentStep.stepNumber}: {currentStep.title}
                      </h4>
                      <p className="mt-2 text-sm leading-6 text-slate-600">{currentStep.description}</p>
                    </div>
                  </div>

                  <div className="mt-5 space-y-3 border-t border-slate-200 pt-5">
                    <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Components in this step</p>
                    <div className="space-y-3">
                      {currentStep.partIndices.map((partIdx) => {
                        const part = parts[partIdx];
                        return (
                          <div
                            key={partIdx}
                            className="flex items-center gap-4 rounded-2xl border border-amber-200/70 bg-gradient-to-r from-amber-50 to-white p-3 transition hover:border-amber-300 hover:shadow-sm"
                          >
                            <div className="flex h-20 w-20 shrink-0 items-center justify-center overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
                              {part && (
                                <svg
                                  viewBox={`0 0 ${part.view_box[2]} ${part.view_box[3]}`}
                                  className="h-full w-full"
                                  dangerouslySetInnerHTML={{ __html: part.svg }}
                                />
                              )}
                            </div>
                            <div className="min-w-0 flex-1">
                              <p className="font-semibold text-slate-950">{part?.name || `Component ${partIdx}`}</p>
                              <p className="mt-1 text-sm text-slate-600">
                                <strong>Role:</strong> {currentStep.partRoles[partIdx.toString()] || "component"}
                              </p>
                              {part && (
                                <p className="text-sm text-slate-600">
                                  <strong>Qty:</strong> {part.quantity_label}
                                </p>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {currentStep.contextPartIndices && currentStep.contextPartIndices.length > 0 && (
                    <div className="mt-5 space-y-3 border-t border-slate-200 pt-5">
                      <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Previously assembled context</p>
                      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                        {currentStep.contextPartIndices.map((partIdx) => {
                          const part = parts[partIdx];
                          if (!part) return null;
                          return (
                            <div
                              key={`context-${partIdx}`}
                              className="flex flex-col items-center gap-2 rounded-2xl border border-slate-200 bg-slate-50 p-3 opacity-85 transition hover:opacity-100 hover:shadow-sm"
                            >
                              <div className="h-14 w-14 overflow-hidden rounded-xl border border-slate-300 bg-white">
                                <svg
                                  viewBox={`0 0 ${part.view_box[2]} ${part.view_box[3]}`}
                                  className="h-full w-full"
                                  dangerouslySetInnerHTML={{ __html: part.svg }}
                                />
                              </div>
                              <p className="w-full truncate px-1 text-center text-xs font-medium text-slate-600">
                                {part.name}
                              </p>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>

                {currentStep.exploded_svg && (
                  <div className="rounded-3xl border border-slate-200/80 bg-white/90 p-6 shadow-sm shadow-slate-200/60">
                    <p className="mb-4 text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">Exploded View</p>
                    <div className="overflow-auto rounded-2xl border border-slate-200 bg-gradient-to-br from-slate-50 to-slate-100 p-4">
                      <svg
                        viewBox="0 0 500 400"
                        className="w-full"
                        dangerouslySetInnerHTML={{ __html: currentStep.exploded_svg }}
                      />
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [tolerance, setTolerance] = useState(0.02);
  const [activeTab, setActiveTab] = useState<"mesh" | "parts2d" | "assembly">("mesh");
  const [mode, setMode] = useState<"preview_only" | "full_analysis">("full_analysis");

  // Mesh state
  const [geometryData, setGeometryData] = useState<GeometryData | null>(null);
  const [partsMetadata, setPartsMetadata] = useState<PartMetadata[]>([]);
  const [meshStats, setMeshStats] = useState<UploadResponse["stats"] | null>(null);

  // Parts 2D state
  const [parts2D, setParts2D] = useState<Part2D[]>([]);
  const [parts2DStats, setParts2DStats] = useState<Parts2DResponse["stats"] | null>(null);

  // Assembly state
  const [assemblySteps, setAssemblySteps] = useState<AssemblyStep[]>([]);
  const [assemblyParts, setAssemblyParts] = useState<Part2D[]>([]);
  const [assemblyStats, setAssemblyStats] = useState<AssemblyAnalysisResponse["stats"] | null>(null);
  const [assemblyMode, setAssemblyMode] = useState<"preview_only" | "full_analysis">("full_analysis");

  // Loading state
  const [isLoading, setIsLoading] = useState(false);
  const [loadingPhase, setLoadingPhase] = useState<"mesh" | "parts2d" | "assembly" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);

  // Cleanup on component unmount
  useEffect(() => {
    return () => {
      // Clean up any ongoing operations
      setIsLoading(false);
      setLoadingPhase(null);
    };
  }, []);

  const handleSSEStream = (eventsUrl: string, onDataReceived: (payload: any) => void) => {
    return new Promise<void>((resolve, reject) => {
      const url = eventsUrl.startsWith("http") ? eventsUrl : `${API_URL}${eventsUrl}`;
      const source = new EventSource(url);
      let lastEventTime = Date.now();
      
      // Set timeout for SSE connection (30 seconds of inactivity)
      const timeout = setTimeout(() => {
        if (Date.now() - lastEventTime > 30000) {
          source.close();
          reject(new Error("SSE connection timeout: no updates for 30 seconds. The server may be overloaded."));
        }
      }, 30000);

      const handleEvent = (event: MessageEvent<string>) => {
        try {
          lastEventTime = Date.now();
          const payload = JSON.parse(event.data);
          onDataReceived(payload);

          if (payload.status === "completed" || payload.status === "failed") {
            source.close();
            clearTimeout(timeout);
            if (payload.status === "failed") {
              reject(new Error(payload.error ?? "Processing failed"));
            } else {
              resolve();
            }
          }
        } catch (err) {
          source.close();
          clearTimeout(timeout);
          reject(new Error(`Failed to parse event data: ${err instanceof Error ? err.message : "Unknown error"}`));
        }
      };

      source.addEventListener("queued", handleEvent as EventListener);
      source.addEventListener("progress", handleEvent as EventListener);
      source.addEventListener("completed", handleEvent as EventListener);
      source.addEventListener("failed", handleEvent as EventListener);
      source.addEventListener("error", handleEvent as EventListener);

      source.onerror = () => {
        source.close();
        clearTimeout(timeout);
        
        if (source.readyState === EventSource.CLOSED) {
          reject(new Error("Server closed the connection"));
        } else if (source.readyState === EventSource.CONNECTING) {
          reject(new Error("Failed to connect to server"));
        } else {
          reject(new Error("SSE connection error"));
        }
      };
    });
  };

  const fetchWithRetry = async (
    url: string,
    options: RequestInit,
    maxRetries = 3
  ): Promise<Response> => {
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
      try {
        const response = await fetch(url, options);
        if (response.ok) return response;
        
        // Don't retry on 4xx errors (client error)
        if (response.status >= 400 && response.status < 500) {
          return response;
        }
      } catch (error) {
        if (attempt === maxRetries) throw error;
        // Exponential backoff
        await new Promise(resolve => 
          setTimeout(resolve, Math.pow(2, attempt - 1) * 1000)
        );
      }
    }
    throw new Error("Max retries exceeded");
  };

  const uploadMesh = async () => {
    if (!file) {
      setError("Please select a STEP file");
      return;
    }

    setIsLoading(true);
    setError(null);
    setLoadingPhase("mesh");
    setProgress(0);
    setJobStatus("queued");

    try {
      const formData = new FormData();
      formData.append("file", file);
      const params = new URLSearchParams({ tolerance: tolerance.toString() });

      const response = await fetchWithRetry(
        `${API_URL}/api/step/upload?${params.toString()}`,
        {
          method: "POST",
          body: formData,
        }
      );

      const payload = (await response.json()) as AsyncUploadResponse | { detail?: string };

      if (!response.ok || !("success" in payload) || !payload.success) {
        throw new Error(
          "detail" in payload && payload.detail
            ? payload.detail
            : "Failed to upload mesh"
        );
      }

      await handleSSEStream(payload.events_url, (payload: JobEventPayload) => {
        setJobStatus(payload.status);
        setProgress(payload.progress);
        if (payload.status === "completed" && payload.result) {
          setGeometryData(payload.result.geometry);
          setPartsMetadata(payload.result.parts_metadata ?? []);
          setMeshStats(payload.result.stats);
        }
      });

      setActiveTab("mesh");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setGeometryData(null);
      setPartsMetadata([]);
      setMeshStats(null);
    } finally {
      setIsLoading(false);
      setLoadingPhase(null);
    }
  };

  const uploadParts2D = async () => {
    if (!file) {
      setError("Please select a STEP file");
      return;
    }

    setIsLoading(true);
    setError(null);
    setLoadingPhase("parts2d");
    setProgress(0);
    setJobStatus("queued");

    try {
      const formData = new FormData();
      formData.append("file", file);
      const params = new URLSearchParams({ tolerance: tolerance.toString() });

      const response = await fetchWithRetry(
        `${API_URL}/api/step/parts-2d?${params.toString()}`,
        {
          method: "POST",
          body: formData,
        }
      );

      const payload = (await response.json()) as AsyncUploadResponse | { detail?: string };

      if (!response.ok || !("success" in payload) || !payload.success) {
        throw new Error(
          "detail" in payload && payload.detail
            ? payload.detail
            : "Failed to extract parts"
        );
      }

      await handleSSEStream(payload.events_url, (payload: JobEventPayloadParts2D) => {
        setJobStatus(payload.status);
        setProgress(payload.progress);
        if (payload.status === "completed" && payload.result) {
          setParts2D(payload.result.parts_2d);
          setParts2DStats(payload.result.stats);
        }
      });

      setActiveTab("parts2d");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setParts2D([]);
      setParts2DStats(null);
    } finally {
      setIsLoading(false);
      setLoadingPhase(null);
    }
  };

  const uploadAssembly = async () => {
    if (!file) {
      setError("Please select a STEP file");
      return;
    }

    setIsLoading(true);
    setError(null);
    setLoadingPhase("assembly");
    setProgress(0);
    setJobStatus("queued");
    setAssemblyMode(mode);

    try {
      const formData = new FormData();
      formData.append("file", file);
      const params = new URLSearchParams({
        tolerance: tolerance.toString(),
        preview_only: mode === "preview_only" ? "true" : "false",
      });

      const response = await fetchWithRetry(
        `${API_URL}/api/step/assembly-analysis?${params.toString()}`,
        {
          method: "POST",
          body: formData,
        }
      );

      const payload = (await response.json()) as AsyncUploadResponse | { detail?: string };

      if (!response.ok || !("success" in payload) || !payload.success) {
        throw new Error(
          "detail" in payload && payload.detail
            ? payload.detail
            : "Failed to analyze assembly"
        );
      }

      // Save job ID for PDF export
      const jobId = "job_id" in payload ? payload.job_id : "";
      if (jobId) {
        sessionStorage.setItem("lastAssemblyJobId", jobId);
      }

      await handleSSEStream(payload.events_url, (payload: JobEventPayloadAssembly) => {
        setJobStatus(payload.status);
        setProgress(payload.progress);
        if (payload.status === "completed" && payload.result) {
          setAssemblySteps(payload.result.assembly_steps);
          setAssemblyParts(payload.result.parts_2d);
          setAssemblyStats(payload.result.stats);
        }
      });

      setActiveTab("assembly");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setAssemblySteps([]);
      setAssemblyParts([]);
      setAssemblyStats(null);
    } finally {
      setIsLoading(false);
      setLoadingPhase(null);
    }
  };

  return (
    <main className="min-h-screen px-4 py-6 text-slate-900 sm:px-6 lg:px-8">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">
        <header className="rounded-[2rem] border border-white/70 bg-white/70 px-6 py-6 shadow-lg shadow-slate-200/50 backdrop-blur-md sm:px-8">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
            <div className="space-y-3">
              <div className="inline-flex items-center gap-2 rounded-full border border-amber-200 bg-amber-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em] text-amber-700">
                CAD Assembly Studio
              </div>
              <div className="flex flex-wrap items-baseline gap-3">
                <h1 className="bg-gradient-to-r from-slate-950 via-amber-800 to-amber-600 bg-clip-text text-4xl font-semibold tracking-tight text-transparent sm:text-5xl">
                  Meblex
                </h1>
                <span className="text-sm font-medium text-slate-500">Assembly Instructions Generator</span>
              </div>
              <p className="max-w-2xl text-sm leading-6 text-slate-600 sm:text-base">
                Transform STEP files into polished previews, 2D component sheets, and assembly instructions with a cleaner, more readable workflow.
              </p>
            </div>
            <div className="grid grid-cols-3 gap-3 text-right text-xs text-slate-500 sm:text-sm">
              <div className="rounded-2xl border border-slate-200 bg-white/80 px-4 py-3 shadow-sm">
                <p className="font-semibold text-slate-900">3 views</p>
                <p>Mesh, parts, guide</p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white/80 px-4 py-3 shadow-sm">
                <p className="font-semibold text-slate-900">Fast</p>
                <p>Streamed progress</p>
              </div>
              <div className="rounded-2xl border border-slate-200 bg-white/80 px-4 py-3 shadow-sm">
                <p className="font-semibold text-slate-900">Polished</p>
                <p>Export-ready output</p>
              </div>
            </div>
          </div>
        </header>

        {/* Controls Section */}
        <section className="rounded-[2rem] border border-white/70 bg-white/75 p-5 shadow-lg shadow-slate-200/50 backdrop-blur-md sm:p-6">
          <div className="space-y-6">
            <div className="space-y-3">
              <label className="text-sm font-semibold text-slate-700">Upload STEP file</label>
              <div className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-slate-50/90 p-3 sm:flex-row sm:items-center">
                <input
                  type="file"
                  accept=".step,.stp"
                  onChange={(event) => {
                    setFile(event.target.files?.[0] ?? null);
                    setError(null);
                  }}
                  className="block flex-1 rounded-2xl border border-slate-300 bg-white px-4 py-3 text-sm text-slate-700 file:mr-4 file:cursor-pointer file:rounded-full file:border-0 file:bg-slate-950 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-white hover:file:bg-amber-700 transition-all"
                />
                <div className="whitespace-nowrap rounded-2xl border border-dashed border-slate-300 bg-white px-4 py-3 text-sm font-medium text-slate-600">
                  {file ? file.name : "No file selected"}
                </div>
              </div>
            </div>

            {/* Tolerance control */}
            <div className="space-y-3">
              <label htmlFor="tolerance" className="text-sm font-semibold text-slate-700">
                Mesh Tolerance: {tolerance.toFixed(3)}
              </label>
              <div className="flex flex-col gap-3 rounded-2xl border border-slate-200 bg-white p-4 sm:flex-row sm:items-center sm:gap-4">
                <input
                  id="tolerance"
                  type="range"
                  min={0.001}
                  max={0.1}
                  step={0.001}
                  value={tolerance}
                  onChange={(event) => setTolerance(Number(event.target.value))}
                  className="h-2 flex-1 cursor-pointer rounded-lg bg-slate-200 accent-amber-600"
                />
                <input
                  type="number"
                  min={0.001}
                  max={1}
                  step={0.001}
                  value={tolerance}
                  onChange={(event) => {
                    const value = Number(event.target.value);
                    if (!Number.isNaN(value)) {
                      setTolerance(Math.min(1, Math.max(0.001, value)));
                    }
                  }}
                  className="w-24 rounded-xl border border-slate-300 bg-slate-50 px-3 py-2 text-sm font-medium text-slate-900 focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-200"
                />
              </div>
              <p className="text-xs text-slate-500">Higher tolerance means a simpler mesh. Lower tolerance keeps more detail.</p>
            </div>

            {/* Assembly mode control (only for assembly tab) */}
            {activeTab === "assembly" && (
              <div className="space-y-3">
                <label className="text-sm font-semibold text-slate-700">Assembly Analysis Mode</label>
                <div className="grid gap-3 rounded-2xl border border-slate-200 bg-white p-4 lg:grid-cols-2">
                  <label className="flex cursor-pointer items-start gap-3 rounded-2xl border border-slate-200 bg-slate-50/80 p-4 transition hover:border-amber-300 hover:bg-amber-50/70">
                    <input
                      type="radio"
                      name="mode"
                      value="preview_only"
                      checked={mode === "preview_only"}
                      onChange={(e) => setMode(e.target.value as "preview_only" | "full_analysis")}
                      className="mt-1 h-4 w-4 accent-amber-600"
                    />
                    <span>
                      <span className="block text-sm font-semibold text-slate-900">Preview Mode</span>
                      <span className="block text-xs text-slate-500">Basic component layout</span>
                    </span>
                  </label>
                  <label className="flex cursor-pointer items-start gap-3 rounded-2xl border border-slate-200 bg-slate-50/80 p-4 transition hover:border-amber-300 hover:bg-amber-50/70">
                    <input
                      type="radio"
                      name="mode"
                      value="full_analysis"
                      checked={mode === "full_analysis"}
                      onChange={(e) => setMode(e.target.value as "preview_only" | "full_analysis")}
                      className="mt-1 h-4 w-4 accent-amber-600"
                    />
                    <span>
                      <span className="block text-sm font-semibold text-slate-900">Full Analysis</span>
                      <span className="block text-xs text-slate-500">AI-powered assembly</span>
                    </span>
                  </label>
                </div>
              </div>
            )}

            {/* Action buttons */}
            <div className="grid gap-3 grid-cols-1 sm:grid-cols-3">
              <button
                onClick={uploadMesh}
                disabled={isLoading}
                className="flex items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-yellow-600 to-yellow-500 px-4 py-3 text-sm font-semibold text-white transition hover:from-yellow-500 hover:to-yellow-400 disabled:cursor-not-allowed disabled:opacity-50 shadow-md hover:shadow-lg"
              >
                {isLoading && loadingPhase === "mesh" ? (
                  <>
                    <span className="animate-spin">⚙️</span>
                    Processing...
                  </>
                ) : (
                  <>
                    <span>📐</span>
                    View 3D Mesh
                  </>
                )}
              </button>
              <button
                onClick={uploadParts2D}
                disabled={isLoading}
                className="flex items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-yellow-500 to-yellow-600 px-4 py-3 text-sm font-semibold text-white transition hover:from-yellow-400 hover:to-yellow-500 disabled:cursor-not-allowed disabled:opacity-50 shadow-md hover:shadow-lg"
              >
                {isLoading && loadingPhase === "parts2d" ? (
                  <>
                    <span className="animate-spin">⚙️</span>
                    Extracting...
                  </>
                ) : (
                  <>
                    <span>📋</span>
                    Extract Parts 2D
                  </>
                )}
              </button>
              <button
                onClick={uploadAssembly}
                disabled={isLoading}
                className="flex items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-yellow-500 to-yellow-600 px-4 py-3 text-sm font-semibold text-white transition hover:from-yellow-400 hover:to-yellow-500 disabled:cursor-not-allowed disabled:opacity-50 shadow-md hover:shadow-lg"
              >
                {isLoading && loadingPhase === "assembly" ? (
                  <>
                    <span className="animate-spin">⚙️</span>
                    Analyzing...
                  </>
                ) : (
                  <>
                    <span>🔧</span>
                    Generate Assembly
                  </>
                )}
              </button>
            </div>

            {/* Progress bar */}
            {isLoading && (
              <div className="rounded-lg border-2 border-yellow-200 bg-gradient-to-r from-yellow-50 to-amber-50 p-4 space-y-2">
                <p className="text-sm font-semibold text-yellow-900 flex items-center gap-2">
                  <span className="animate-spin text-lg">⚙️</span>
                  {loadingPhase && (
                    <>
                      {loadingPhase === "mesh" && "Processing 3D mesh"}
                      {loadingPhase === "parts2d" && "Extracting components"}
                      {loadingPhase === "assembly" && "Analyzing assembly sequence"}
                    </>
                  )}{" "}
                  • {progress}%
                </p>
                <div className="h-3 w-full overflow-hidden rounded-full bg-yellow-100 border border-yellow-200">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-yellow-400 to-yellow-600 transition-all shadow-md"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </div>
            )}

            {/* Error message */}
            {error && (
              <div className="rounded-lg border-2 border-red-300 bg-gradient-to-r from-red-50 to-pink-50 p-4 text-sm text-red-800 font-medium flex items-start gap-3">
                <span className="text-xl">⚠️</span>
                <div>{error}</div>
              </div>
            )}
          </div>
        </section>

        {/* Content tabs */}
        <section className="rounded-xl border border-slate-200 bg-white/80 shadow-md overflow-hidden backdrop-blur-sm">
          <TabNav activeTab={activeTab} onTabChange={setActiveTab} />

          <div className="p-6">
            {activeTab === "mesh" && (
              <>
                {geometryData ? (
                  <div className="space-y-4">
                    {meshStats && (
                      <div className="grid gap-2 text-sm text-[#3f4a45] sm:grid-cols-2 lg:grid-cols-4">
                        <p>File: {meshStats.filename}</p>
                        <p>Vertices: {meshStats.vertex_count}</p>
                        <p>Triangles: {meshStats.triangle_count}</p>
                        <p>Size: {(meshStats.file_size_bytes / 1024).toFixed(1)} KB</p>
                      </div>
                    )}
                    <div className="h-[60vh] min-h-[360px] overflow-hidden rounded-lg border border-[#c9d2cd] bg-[#ecf1ee]">
                      <Canvas camera={{ position: [3, 2, 3], fov: 50 }} shadows>
                        <color attach="background" args={["#ecf1ee"]} />
                        <ambientLight intensity={0.6} />
                        <directionalLight
                          position={[3, 5, 3]}
                          intensity={1}
                          castShadow
                          shadow-mapSize-width={1024}
                          shadow-mapSize-height={1024}
                        />
                        <gridHelper args={[10, 20, "#9aa9a1", "#cad4cf"]} />
                        <Bounds fit clip observe margin={1.25}>
                          <ModelMesh geometry={geometryData} />
                        </Bounds>
                        <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -1.2, 0]} receiveShadow>
                          <planeGeometry args={[200, 200]} />
                          <shadowMaterial opacity={0.22} />
                        </mesh>
                        <OrbitControls makeDefault target={[0, 0, 0]} />
                      </Canvas>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-12 text-[#56635d]">
                    <p>Upload and process a STEP file to view the 3D mesh.</p>
                  </div>
                )}
              </>
            )}

            {activeTab === "parts2d" && (
              <>
                {parts2D.length > 0 && parts2DStats ? (
                  <Parts2DViewer parts={parts2D} stats={parts2DStats} />
                ) : (
                  <div className="text-center py-12 text-[#56635d]">
                    <p>Extract parts to view 2D isometric drawings.</p>
                  </div>
                )}
              </>
            )}

            {activeTab === "assembly" && (
              <>
                {assemblyParts.length > 0 && assemblyStats ? (
                  <AssemblyViewer
                    steps={assemblySteps}
                    parts={assemblyParts}
                    stats={assemblyStats}
                    mode={assemblyMode}
                  />
                ) : (
                  <div className="text-center py-12 text-[#56635d]">
                    <p>Generate assembly instructions to view step-by-step guide.</p>
                  </div>
                )}
              </>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}
