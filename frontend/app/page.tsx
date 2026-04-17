"use client";

import { FormEvent, useMemo, useState } from "react";
import { Canvas } from "@react-three/fiber";
import { Bounds, OrbitControls } from "@react-three/drei";
import * as THREE from "three";

type MeshData = {
  vertices: number[][];
  triangles: number[][];
  bounds: [number, number, number, number, number, number];
};

type UploadResponse = {
  success: boolean;
  mesh: MeshData;
  stats: {
    filename: string;
    file_size_bytes: number;
    vertex_count: number;
    triangle_count: number;
    tolerance: number;
  };
};

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8002";

function ModelMesh({ mesh }: { mesh: MeshData }) {
  const geometry = useMemo(() => {
    const g = new THREE.BufferGeometry();

    const positions = new Float32Array(mesh.vertices.flat());
    const indexValues = mesh.triangles.flat();
    const indices = new Uint32Array(indexValues);

    g.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    g.setIndex(new THREE.BufferAttribute(indices, 1));
    g.computeVertexNormals();

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
  }, [mesh]);

  return (
    <mesh geometry={geometry} castShadow receiveShadow>
      <meshStandardMaterial color="#5f8f7a" metalness={0.2} roughness={0.65} />
    </mesh>
  );
}

export default function Home() {
  const [file, setFile] = useState<File | null>(null);
  const [meshData, setMeshData] = useState<MeshData | null>(null);
  const [stats, setStats] = useState<UploadResponse["stats"] | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tolerance, setTolerance] = useState(0.01);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!file) {
      setError("Wybierz plik STEP (.step lub .stp).");
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const params = new URLSearchParams({ tolerance: tolerance.toString() });
      const response = await fetch(`${API_URL}/api/upload-step?${params.toString()}`, {
        method: "POST",
        body: formData,
      });

      const payload = (await response.json()) as UploadResponse | { detail?: string };

      if (!response.ok || !("success" in payload) || !payload.success) {
        const message =
          "detail" in payload && payload.detail
            ? payload.detail
            : "Nie udalo sie przetworzyc modelu.";
        throw new Error(message);
      }

      setMeshData(payload.mesh);
      setStats(payload.stats);
    } catch (err) {
      setMeshData(null);
      setStats(null);
      setError(err instanceof Error ? err.message : "Wystapil nieznany blad.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_20%_20%,#f4f7f5_0%,#e7ece9_40%,#d7ddd8_100%)] px-4 py-8 text-[#1e2522] sm:px-8">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-6">
        <header className="space-y-2">
          <h1 className="text-3xl font-semibold tracking-tight">STEP 3D Viewer</h1>
          <p className="text-sm text-[#3f4a45]">
            Wgraj plik STEP, backend zamieni go na siatke, a frontend wyrenderuje model w Three.js.
          </p>
        </header>

        <section className="rounded-2xl border border-white/60 bg-white/70 p-4 shadow-sm backdrop-blur sm:p-6">
          <form className="flex flex-col gap-4 sm:flex-row sm:items-center" onSubmit={onSubmit}>
            <input
              type="file"
              accept=".step,.stp"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              className="block w-full rounded-lg border border-[#c9d2cd] bg-white px-3 py-2 text-sm file:mr-4 file:cursor-pointer file:rounded-md file:border-0 file:bg-[#5f8f7a] file:px-3 file:py-2 file:text-sm file:font-medium file:text-white hover:file:bg-[#507a68]"
            />
            <button
              type="submit"
              disabled={isLoading}
              className="inline-flex items-center justify-center rounded-lg bg-[#1f5f4a] px-4 py-2 text-sm font-medium text-white transition hover:bg-[#194d3c] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isLoading ? "Przetwarzanie..." : "Wyslij i renderuj"}
            </button>
          </form>

          <div className="mt-4 flex flex-col gap-2 rounded-lg border border-[#c9d2cd] bg-[#f6f9f7] p-3 sm:flex-row sm:items-center sm:gap-4">
            <label htmlFor="tolerance" className="text-sm font-medium text-[#2c3833]">
              Tolerance: {tolerance.toFixed(3)}
            </label>
            <input
              id="tolerance"
              type="range"
              min={0.001}
              max={0.1}
              step={0.001}
              value={tolerance}
              onChange={(event) => setTolerance(Number(event.target.value))}
              className="w-full sm:max-w-xs"
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
                  const clamped = Math.min(1, Math.max(0.001, value));
                  setTolerance(clamped);
                }
              }}
              className="w-24 rounded border border-[#c9d2cd] bg-white px-2 py-1 text-sm"
            />
            <p className="text-xs text-[#56635d]">Nizsza wartosc = wiecej trojkatow, wyzsza = lzejsza siatka.</p>
          </div>

          {error ? <p className="mt-3 text-sm text-red-700">{error}</p> : null}

          {stats ? (
            <div className="mt-4 grid gap-2 text-sm text-[#3f4a45] sm:grid-cols-2 lg:grid-cols-4">
              <p>Plik: {stats.filename}</p>
              <p>Wierzcholki: {stats.vertex_count}</p>
              <p>Trojkaty: {stats.triangle_count}</p>
              <p>Rozmiar: {(stats.file_size_bytes / 1024).toFixed(1)} KB</p>
              <p>Tolerance: {stats.tolerance.toFixed(3)}</p>
            </div>
          ) : null}
        </section>

        <section className="h-[60vh] min-h-[360px] overflow-hidden rounded-2xl border border-[#c9d2cd] bg-[#ecf1ee] shadow-sm">
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

            {meshData ? (
              <Bounds fit clip observe margin={1.25}>
                <ModelMesh mesh={meshData} />
              </Bounds>
            ) : (
              <mesh position={[0, 0.5, 0]} castShadow receiveShadow>
                <boxGeometry args={[1, 1, 1]} />
                <meshStandardMaterial color="#b5c7bf" />
              </mesh>
            )}

            <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -1.2, 0]} receiveShadow>
              <planeGeometry args={[200, 200]} />
              <shadowMaterial opacity={0.22} />
            </mesh>

            <OrbitControls makeDefault target={[0, 0, 0]} />
          </Canvas>
        </section>
      </div>
    </main>
  );
}
