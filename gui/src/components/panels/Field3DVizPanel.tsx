/**
 * Field3DVizPanel — production 3D isosurface viewer for Field3D analysis objects.
 *
 * Flow:
 * 1. Metadata card rendered from bundle (preview + stats) — no grid load needed.
 * 2. "Load Full Grid" → RPC get_field3d_grid → scratch read → Float32Array.
 * 3. Three.js Canvas with IsosurfaceMesh + atom/cell overlays.
 */

import { Suspense, useCallback, useRef, useState } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';

import { useQVClient } from '../../hooks/useQVClient';
import type { PrimitiveBundleData } from '../../types/qv';
import { normalizeProjectRoot } from '../../utils/pathUtils';
import type { VolumeStats } from '../../utils/marchingCubes';
import { IsosurfaceMesh, type IsosurfaceMetadata } from '../three/IsosurfaceMesh';
import { AtomOverlay, UnitCellOverlay } from './VolumeOverlay';

interface Field3DVizPanelProps {
  availableObjectTypes: string[];
  selectedObjectType: string | null;
  onSelectObjectType: (objectType: string) => void;
  loading: boolean;
  error: string | null;
  bundle: PrimitiveBundleData | null;
  canPin: boolean;
  pinReason: string | null;
  pinMessage: string | null;
  pinning: boolean;
  onPin: () => Promise<void>;
  projectRoot: string;
  runUlid: string | null;
}

interface GridState {
  data: Float32Array;
  metadata: IsosurfaceMetadata;
  calcDir: string;
  valueMin: number;
  valueMax: number;
  valueMean: number;
  fieldKind: string;
}

export function Field3DVizPanel({
  availableObjectTypes,
  selectedObjectType,
  onSelectObjectType,
  loading,
  error,
  bundle,
  canPin,
  pinReason,
  pinMessage,
  pinning,
  onPin,
  projectRoot,
  runUlid,
}: Field3DVizPanelProps) {
  const qv = useQVClient();

  const [gridState, setGridState] = useState<GridState | null>(null);
  const [gridLoading, setGridLoading] = useState(false);
  const [gridError, setGridError] = useState<string | null>(null);

  const [isovalue, setIsovalue] = useState(0);
  const [showPlusMinusIso, setShowPlusMinusIso] = useState(false);
  const [opacity, setOpacity] = useState(0.6);
  const [showAtoms, setShowAtoms] = useState(true);
  const [showCell, setShowCell] = useState(true);

  const meshKeyRef = useRef(0);
  const [meshStats, setMeshStats] = useState<{ triangles: number; stats: VolumeStats | null }>({
    triangles: 0,
    stats: null,
  });

  // Extract bundle metadata
  const volumeMeta = bundle?.render_meta?.extra?.volume_metadata as Record<string, unknown> | undefined;
  const fieldKind = bundle?.render_meta?.extra?.field_kind as string | undefined;
  const discoveredFiles = bundle?.render_meta?.extra?.discovered_files as string[] | undefined;
  const nGridPoints = bundle?.render_meta?.extra?.n_grid_points as number | undefined;
  const lattice = bundle?.arrays?.lattice as number[][] | undefined;

  // Atom positions from bundle (if available)
  const structureAtoms = volumeMeta?.structure_atoms as
    | Array<{ element: string; position: [number, number, number] }>
    | undefined;
  const latticeVectors = (lattice ?? volumeMeta?.lattice_vectors_cart) as
    | [[number, number, number], [number, number, number], [number, number, number]]
    | undefined;

  const handleLoadGrid = useCallback(async () => {
    const normalizedRoot = normalizeProjectRoot(projectRoot);
    if (!normalizedRoot || !runUlid) {
      setGridError('Missing project path or run ID');
      return;
    }

    setGridLoading(true);
    setGridError(null);
    meshKeyRef.current += 1;

    try {
      // Step 1: RPC to materialize grid to .scratch/
      const response = await qv.call('get_field3d_grid', {
        project_root: normalizedRoot,
        run_ulid: runUlid,
      });

      if (!response.ok || !response.data) {
        setGridError(response.error?.message ?? 'Failed to materialize field3d grid');
        return;
      }

      const meta = response.data;

      // Step 2: Read binary grid via Electron IPC
      const buffer = await (window as any).qv.readScratchFile(
        meta.calc_dir,
        '.scratch/field3d/active.f32',
      );
      const gridData = new Float32Array(buffer);

      // Validate size
      const expectedSize = meta.grid_shape[0] * meta.grid_shape[1] * meta.grid_shape[2];
      if (gridData.length !== expectedSize) {
        setGridError(
          `Grid size mismatch: got ${gridData.length}, expected ${expectedSize}`,
        );
        return;
      }

      const isosurfaceMeta: IsosurfaceMetadata = {
        grid_shape: meta.grid_shape,
        origin_cart: meta.origin_cart,
        grid_vectors_cart: meta.grid_vectors_cart,
        data_order: meta.data_order as 'fortran_i_fastest' | 'c_k_fastest',
      };

      // Set default isovalue (0.2 * max_abs, py4vasp convention)
      const maxAbs = Math.max(Math.abs(meta.value_min), Math.abs(meta.value_max));
      const defaultIso = maxAbs > 0 ? 0.2 * maxAbs : 0;
      setIsovalue(defaultIso);

      setGridState({
        data: gridData,
        metadata: isosurfaceMeta,
        calcDir: meta.calc_dir,
        valueMin: meta.value_min,
        valueMax: meta.value_max,
        valueMean: meta.value_mean,
        fieldKind: meta.field_kind,
      });
    } catch (e) {
      setGridError(e instanceof Error ? e.message : String(e));
    } finally {
      setGridLoading(false);
    }
  }, [projectRoot, runUlid, qv]);

  if (availableObjectTypes.length === 0) {
    return (
      <div className="analysis-surface__placeholder" data-testid="qv-analysis-no-objects">
        No analysis object is available for this step in the current run.
      </div>
    );
  }

  return (
    <div className="analysis-viz" data-testid="qv-analysis-field3d-panel">
      {/* Object type tiles */}
      <div className="analysis-viz__controls">
        <div className="analysis-viz__tiles">
          {availableObjectTypes.map((objectType) => {
            const active = objectType === selectedObjectType;
            return (
              <button
                key={objectType}
                className={`analysis-viz__tile${active ? ' analysis-viz__tile--active' : ''}`}
                onClick={() => onSelectObjectType(objectType)}
                type="button"
              >
                {objectType}
              </button>
            );
          })}
        </div>
      </div>

      {loading ? <div className="analysis-surface__placeholder" data-testid="qv-analysis-loading">Loading analysis...</div> : null}
      {error ? <div className="analysis-surface__error" data-testid="qv-analysis-error">{error}</div> : null}

      {!loading && !error && bundle ? (
        <>
          {/* Metadata card */}
          <div className="analysis-viz__field3d-card" data-testid="qv-analysis-field3d-card">
            <h4>Field3D{fieldKind ? ` (${fieldKind})` : ''}</h4>
            <table className="analysis-viz__field3d-table">
              <tbody>
                {fieldKind ? <tr><td>Kind</td><td>{fieldKind}</td></tr> : null}
                {volumeMeta?.grid_shape ? (
                  <tr><td>Grid</td><td>{String(volumeMeta.grid_shape)}</td></tr>
                ) : null}
                {nGridPoints != null ? (
                  <tr><td>Points</td><td>{nGridPoints.toLocaleString()}</td></tr>
                ) : null}
                {volumeMeta?.value_min != null ? (
                  <tr><td>Min</td><td>{Number(volumeMeta.value_min).toExponential(4)}</td></tr>
                ) : null}
                {volumeMeta?.value_max != null ? (
                  <tr><td>Max</td><td>{Number(volumeMeta.value_max).toExponential(4)}</td></tr>
                ) : null}
                {volumeMeta?.value_mean != null ? (
                  <tr><td>Mean</td><td>{Number(volumeMeta.value_mean).toExponential(4)}</td></tr>
                ) : null}
                {discoveredFiles ? (
                  <tr><td>Files</td><td>{discoveredFiles.join(', ')}</td></tr>
                ) : null}
              </tbody>
            </table>
          </div>

          {/* Load Full Grid button or 3D canvas */}
          {!gridState ? (
            <div className="field3d-viz__load-section">
              <button
                className="field3d-viz__load-btn"
                data-testid="qv-field3d-load-grid"
                disabled={gridLoading || !runUlid}
                onClick={() => void handleLoadGrid()}
                type="button"
              >
                {gridLoading ? 'Loading Grid...' : 'Load Full Grid for 3D Rendering'}
              </button>
              {gridError ? (
                <div className="field3d-viz__error">{gridError}</div>
              ) : null}
            </div>
          ) : (
            <>
              {/* 3D Canvas */}
              <div className="field3d-viz__canvas-container">
                <Canvas camera={{ position: [8, 8, 8], fov: 50 }} frameloop="demand">
                  <Suspense fallback={null}>
                    <ambientLight intensity={0.5} />
                    <directionalLight position={[10, 10, 5]} intensity={0.8} />

                    {showAtoms && structureAtoms ? (
                      <AtomOverlay atoms={structureAtoms} visible={showAtoms} />
                    ) : null}

                    {showCell && latticeVectors ? (
                      <UnitCellOverlay
                        latticeVectors={latticeVectors}
                        origin={gridState.metadata.origin_cart}
                        visible={showCell}
                      />
                    ) : null}

                    {/* Positive isosurface (blue) */}
                    <IsosurfaceMesh
                      volumeData={gridState.data}
                      metadata={gridState.metadata}
                      isovalue={isovalue}
                      color="hsl(210, 70%, 50%)"
                      opacity={opacity}
                      meshKey={meshKeyRef.current}
                      compileSeq={meshKeyRef.current}
                      onMeshGenerated={(_nV, nT, stats) => {
                        setMeshStats({ triangles: nT, stats: stats ?? null });
                      }}
                    />

                    {/* Negative isosurface (red) */}
                    {showPlusMinusIso ? (
                      <IsosurfaceMesh
                        volumeData={gridState.data}
                        metadata={gridState.metadata}
                        isovalue={-isovalue}
                        color="hsl(0, 70%, 50%)"
                        opacity={opacity}
                        meshKey={meshKeyRef.current + 1000}
                        compileSeq={meshKeyRef.current}
                        onMeshGenerated={(_nV, nT) => {
                          setMeshStats((prev) => ({
                            triangles: prev.triangles + nT,
                            stats: prev.stats,
                          }));
                        }}
                      />
                    ) : null}

                    <OrbitControls />
                  </Suspense>
                </Canvas>
                {meshStats.triangles === 0 && (
                  <div className="field3d-viz__canvas-warning">
                    0 triangles (adjust isovalue)
                  </div>
                )}
              </div>

              {/* Controls */}
              <div className="field3d-viz__controls">
                <div className="field3d-viz__control-row">
                  <label>
                    Isovalue:
                    <input
                      type="range"
                      min={gridState.valueMin}
                      max={gridState.valueMax}
                      step={Math.abs(gridState.valueMax - gridState.valueMin) / 200 || 0.001}
                      value={isovalue}
                      onChange={(e) => setIsovalue(parseFloat(e.target.value))}
                    />
                    <span className="field3d-viz__value">{isovalue.toExponential(3)}</span>
                  </label>
                </div>
                <div className="field3d-viz__control-row">
                  <label>
                    <input
                      type="checkbox"
                      checked={showPlusMinusIso}
                      onChange={(e) => setShowPlusMinusIso(e.target.checked)}
                    />
                    +/- iso (dual surface)
                  </label>
                </div>
                <div className="field3d-viz__control-row">
                  <label>
                    Opacity:
                    <input
                      type="range"
                      min={0.05}
                      max={1.0}
                      step={0.05}
                      value={opacity}
                      onChange={(e) => setOpacity(parseFloat(e.target.value))}
                    />
                    <span className="field3d-viz__value">{opacity.toFixed(2)}</span>
                  </label>
                </div>
                <div className="field3d-viz__control-row">
                  <label>
                    <input
                      type="checkbox"
                      checked={showAtoms}
                      onChange={(e) => setShowAtoms(e.target.checked)}
                      disabled={!structureAtoms || structureAtoms.length === 0}
                    />
                    Show atoms{structureAtoms ? ` (${structureAtoms.length})` : ''}
                  </label>
                </div>
                <div className="field3d-viz__control-row">
                  <label>
                    <input
                      type="checkbox"
                      checked={showCell}
                      onChange={(e) => setShowCell(e.target.checked)}
                      disabled={!latticeVectors}
                    />
                    Show unit cell
                  </label>
                </div>
                <div className="field3d-viz__stats">
                  Triangles: {meshStats.triangles}
                  {meshStats.stats?.nActiveCubes ? ` | Active cubes: ${meshStats.stats.nActiveCubes}` : ''}
                </div>
              </div>
            </>
          )}

          {/* Pin + Provenance */}
          <div className="analysis-viz__pin">
            <button disabled={!canPin || pinning} onClick={() => void onPin()} type="button">
              {pinning ? 'Pinning...' : 'Pin to History'}
            </button>
            {!canPin && pinReason ? <span>{pinReason}</span> : null}
            {pinMessage ? <span>{pinMessage}</span> : null}
          </div>
          <details className="analysis-viz__provenance">
            <summary>Provenance</summary>
            <pre>{JSON.stringify(bundle.provenance_meta, null, 2)}</pre>
          </details>
        </>
      ) : null}
    </div>
  );
}
