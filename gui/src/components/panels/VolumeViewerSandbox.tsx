/**
 * VolumeViewerSandbox - Development sandbox for volume visualization
 * 
 * MVP: Lists fixtures, compiles to blob, displays metadata + 3D isosurface
 */

import { useState, useEffect, useCallback, Suspense, useRef } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Grid } from '@react-three/drei';
import type { VolumeStats } from '../../utils/marchingCubes';
import { inferEnergyReference, type EnergyReferenceResult } from '../../utils/energyReference';
import { IsosurfaceMesh } from '../three/IsosurfaceMesh';
import { AtomOverlay, UnitCellOverlay, BrillouinZoneOverlay } from './VolumeOverlay';
import './VolumeViewerSandbox.css';

interface Fixture {
  id: string;
  label: string;
  path: string;
  kind: 'xsf' | 'bxsf';
}

interface VolumeMetadata {
  grid_shape: [number, number, number];
  coordinate_system: string;
  origin_cart: [number, number, number];
  grid_vectors_cart: [[number, number, number], [number, number, number], [number, number, number]];
  data_order: 'fortran_i_fastest' | 'c_k_fastest';
  length_units: string;
  value_units: string;
  value_min?: number;
  value_max?: number;
  value_mean?: number;
  preview_grid_shape?: [number, number, number]; // Preview dimensions (if preview blob exists)
  preview_downsample_factor?: number;
  // Part C: Structure overlay
  structure_atoms?: Array<{ element: string; position: [number, number, number] }>;
  lattice_vectors_cart?: [[number, number, number], [number, number, number], [number, number, number]];
  // Part B: BXSF coordinate system
  reciprocal_convention?: string; // "2pi" or "unknown"
}

interface CompiledVolume {
  artifact_id: string;
  kind: string;
  metadata: VolumeMetadata;
  blob_id: string;
  preview_blob_id?: string;
  n_bands?: number;
  band_index?: number;
  fermi_energy?: number;
}

// P0: Atomic compiled volume state
interface CompiledVolumeState {
  key: string; // `${fixturePath}|${kind}|${resolution}|${bandIndex}`
  seq: number;
  fixture: Fixture;
  volume: CompiledVolume;
  blobId: string;
  blobData: Float32Array;
  dims: [number, number, number];
  data_order: 'fortran_i_fastest' | 'c_k_fastest';
  valueRange: { min: number; max: number } | null;
  bbox?: { min: [number, number, number]; max: [number, number, number]; center: [number, number, number]; maxExtent: number };
  kind: string;
  fermi_energy?: number;
  bandIndex?: number;
  resolution: 'preview' | 'full';
  energy_reference?: EnergyReferenceResult;
  // Part B: BXSF coordinate system debug
  grid_vectors?: [[number, number, number], [number, number, number], [number, number, number]]; // Original b1,b2,b3
  grid_step_vectors?: [[number, number, number], [number, number, number], [number, number, number]]; // db1, db2, db3
  vector_lengths?: [number, number, number]; // |b1|, |b2|, |b3|
  // Part C: Structure overlay
  structure_atoms?: Array<{ element: string; position: [number, number, number] }>;
  lattice_vectors_cart?: [[number, number, number], [number, number, number], [number, number, number]];
}

// P0: Validate volume grid contract
function validateVolumeGrid(
  values: Float32Array,
  dims: [number, number, number],
  data_order: string,
  context: { key: string; seq: number; blobId: string }
): void {
  const expectedValues = dims[0] * dims[1] * dims[2];
  if (values.length !== expectedValues) {
    throw new Error(
      `Phase0 validation failed: values.length(${values.length}) != nx*ny*nz(${expectedValues}) ` +
      `for dims=[${dims.join(',')}], data_order=${data_order}, ` +
      `key=${context.key}, seq=${context.seq}, blobId=${context.blobId}`
    );
  }
}

export function VolumeViewerSandbox() {
  const [fixtures, setFixtures] = useState<Fixture[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // P0: Atomic compiled volume state (replaces scattered state)
  const [compiledVolume, setCompiledVolume] = useState<CompiledVolumeState | null>(null);
  
  // Separate UI state
  const [isovalue, setIsovalue] = useState(0);
  const [showPlusMinusIso, setShowPlusMinusIso] = useState(false);
  
  // Part C: Overlay visibility toggles
  const [showAtoms, setShowAtoms] = useState(true); // Default: on for XSF
  const [showCell, setShowCell] = useState(true); // Default: on for XSF
  const [showBZ, setShowBZ] = useState(true); // Default: on for BXSF
  
  // P0: Request sequence tracking
  const seqRef = useRef(0);
  const latestSeqRef = useRef(0);
  const latestKeyRef = useRef<string>('');
  const abortControllerRef = useRef<AbortController | null>(null);
  const meshKeyRef = useRef(0);
  
  // P2/P3: Resolution and band state (affects compile key)
  const [useFullResolution, setUseFullResolution] = useState(false);
  const [selectedBandIndex, setSelectedBandIndex] = useState<number | null>(null);
  
  // Debug stats (separate from compiled volume, updated by mesh callback)
  const [meshStats, setMeshStats] = useState<{
    trianglesCount: number;
    volumeStats: VolumeStats | null;
  }>({
    trianglesCount: 0,
    volumeStats: null,
  });

  // P0: Generate compile key (must include all parameters that affect result)
  const generateCompileKey = useCallback((fixture: Fixture, resolution: 'preview' | 'full', bandIndex?: number): string => {
    const band = bandIndex !== undefined ? `${bandIndex}` : 'default';
    return `${fixture.path}|${fixture.kind}|${resolution}|${band}`;
  }, []);

  // P0: Load blob with validation
  const loadBlob = useCallback(async (
    volume: CompiledVolume,
    calcDir: string,
    compileKey: string,
    seq: number,
    resolution: 'preview' | 'full',
    signal: AbortSignal
  ): Promise<{ blobId: string; data: Float32Array; dims: [number, number, number] }> => {
    // Check if aborted
    if (signal.aborted) {
      throw new Error('Request aborted');
    }
    
    // P3: Use full blob if requested, otherwise preview
    const blobId = (resolution === 'full' || !volume.preview_blob_id) ? volume.blob_id : volume.preview_blob_id;
    const isPreview = resolution === 'preview' && !!volume.preview_blob_id;
    
    // Determine which dims to use
    const dims: [number, number, number] = isPreview && volume.metadata.preview_grid_shape
      ? volume.metadata.preview_grid_shape as [number, number, number]
      : volume.metadata.grid_shape as [number, number, number];
    
    // Read blob via preload API
    const buffer = await (window as any).qms.readBlob(blobId, calcDir);
    
    // Check if aborted after async operation
    if (signal.aborted) {
      throw new Error('Request aborted');
    }
    
    // P0: Check if this response is still current
    if (seq !== latestSeqRef.current || compileKey !== latestKeyRef.current) {
      throw new Error(`Stale response: seq=${seq} (latest=${latestSeqRef.current}), key=${compileKey} (latest=${latestKeyRef.current})`);
    }
    
    const data = new Float32Array(buffer);
    
    // P0: Validate contract
    validateVolumeGrid(data, dims, volume.metadata.data_order, { key: compileKey, seq, blobId });
    
    return { blobId, data, dims };
  }, []);

  const loadFixtures = useCallback(async () => {
    try {
      const response = await (window as any).qms.request('list_wannier_3d_fixtures', {});
      if (response.ok && response.data?.fixtures) {
        setFixtures(response.data.fixtures);
      } else {
        setError(response.error?.message || 'Failed to load fixtures');
      }
    } catch (e) {
      setError(`Error loading fixtures: ${e}`);
    }
  }, []);

  // P0: Compile fixture with proper race condition handling
  const compileFixture = useCallback(async (
    fixture: Fixture,
    bandIndex?: number,
    resolution?: 'preview' | 'full'
  ) => {
    // Default to current resolution state if not provided
    const effectiveResolution = resolution ?? (useFullResolution ? 'full' : 'preview');
    // P0: Abort previous request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    
    // P0: Create new abort controller
    const abortController = new AbortController();
    abortControllerRef.current = abortController;
    
    // P0: Generate compile key
    const compileKey = generateCompileKey(fixture, effectiveResolution, bandIndex);
    
    // P0: Increment sequence
    seqRef.current += 1;
    const currentSeq = seqRef.current;
    latestSeqRef.current = currentSeq;
    latestKeyRef.current = compileKey;
    
    // Reset loading state
    setLoading(true);
    setError(null);
    setCompiledVolume(null);
    setMeshStats({ trianglesCount: 0, volumeStats: null });
    meshKeyRef.current += 1; // Force mesh remount
    
    // Use temporary calc_dir
    const calcDir = '/tmp/qms-sandbox-volume';
    
    try {
      // P2: Add band_index parameter for BXSF
      const payload: any = {
        file_path: fixture.path,
        calc_dir: calcDir,
      };
      if (fixture.kind === 'bxsf' && bandIndex !== undefined) {
        payload.band_index = bandIndex;
      }
      
      const response = await (window as any).qms.request('compile_fixture_volume', payload);
      
      // P0: Check if still current after async
      if (abortController.signal.aborted || currentSeq !== latestSeqRef.current || compileKey !== latestKeyRef.current) {
        console.log(`[compileFixture] Stale response discarded: seq=${currentSeq}, key=${compileKey}`);
        return;
      }
      
      if (!response.ok || !response.data) {
        if (currentSeq === latestSeqRef.current && compileKey === latestKeyRef.current) {
          setError(response.error?.message || 'Failed to compile volume');
        }
        return;
      }
      
      const volume = response.data as CompiledVolume;
      
      // P2: Set selected band index
      const effectiveBandIndex = fixture.kind === 'bxsf' ? (bandIndex ?? volume.band_index ?? 1) : undefined;
      if (effectiveBandIndex !== undefined) {
        setSelectedBandIndex(effectiveBandIndex);
      }
      
      // P1: Infer energy reference for BXSF
      let energyRef: EnergyReferenceResult | undefined = undefined;
      if (volume.kind === 'fermi_surface' && volume.metadata.value_min !== undefined && volume.metadata.value_max !== undefined) {
        energyRef = inferEnergyReference(
          volume.metadata.value_min,
          volume.metadata.value_max,
          volume.fermi_energy
        );
      }
      
      // Set initial isovalue
      let initialIso: number;
      if (energyRef) {
        initialIso = energyRef.effective_iso_default;
      } else if (volume.fermi_energy !== undefined && volume.kind === 'fermi_surface') {
        initialIso = volume.fermi_energy;
      } else if (volume.metadata.value_min !== undefined && volume.metadata.value_max !== undefined) {
        if (volume.metadata.value_max === volume.metadata.value_min) {
          setError('Volume has constant value (no variation)');
          initialIso = volume.metadata.value_min;
        } else {
          const min = volume.metadata.value_min;
          const max = volume.metadata.value_max;
          const maxAbs = Math.max(Math.abs(min), Math.abs(max));
          
          if (min >= 0) {
            initialIso = 0.2 * max;
          } else if (max <= 0) {
            initialIso = 0.2 * min;
          } else {
            initialIso = 0.2 * maxAbs;
          }
        }
      } else if (volume.metadata.value_mean !== undefined) {
        initialIso = volume.metadata.value_mean;
      } else {
        initialIso = 0;
      }
      
      setIsovalue(initialIso);
      
      // P0: Load blob atomically
      const { blobId, data, dims } = await loadBlob(volume, calcDir, compileKey, currentSeq, effectiveResolution, abortController.signal);
      
      // P0: Final check before setting state
      if (abortController.signal.aborted || currentSeq !== latestSeqRef.current || compileKey !== latestKeyRef.current) {
        console.log(`[compileFixture] Stale blob response discarded: seq=${currentSeq}, key=${compileKey}`);
        return;
      }
      
      // Part B: Calculate BXSF coordinate system info
      let gridVectors: [[number, number, number], [number, number, number], [number, number, number]] | undefined = undefined;
      let gridStepVectors: [[number, number, number], [number, number, number], [number, number, number]] | undefined = undefined;
      let vectorLengths: [number, number, number] | undefined = undefined;
      
      if (volume.kind === 'fermi_surface' && volume.metadata.grid_vectors_cart) {
        const [b1, b2, b3] = volume.metadata.grid_vectors_cart;
        gridVectors = [b1, b2, b3];
        
        // Calculate step vectors: db1 = b1/(nx-1), etc.
        const [nx, ny, nz] = dims;
        const db1: [number, number, number] = [b1[0] / (nx - 1), b1[1] / (nx - 1), b1[2] / (nx - 1)];
        const db2: [number, number, number] = [b2[0] / (ny - 1), b2[1] / (ny - 1), b2[2] / (ny - 1)];
        const db3: [number, number, number] = [b3[0] / (nz - 1), b3[1] / (nz - 1), b3[2] / (nz - 1)];
        gridStepVectors = [db1, db2, db3];
        
        // Calculate vector lengths
        const len1 = Math.sqrt(b1[0] * b1[0] + b1[1] * b1[1] + b1[2] * b1[2]);
        const len2 = Math.sqrt(b2[0] * b2[0] + b2[1] * b2[1] + b2[2] * b2[2]);
        const len3 = Math.sqrt(b3[0] * b3[0] + b3[1] * b3[1] + b3[2] * b3[2]);
        vectorLengths = [len1, len2, len3];
      }
      
      // Part C: Extract structure info for overlay
      const structureAtoms = volume.metadata.structure_atoms;
      const latticeVectors = volume.metadata.lattice_vectors_cart;
      
      // P0: Set atomic compiled volume state
      setCompiledVolume({
        key: compileKey,
        seq: currentSeq,
        fixture,
        volume,
        blobId,
        blobData: data,
        dims,
        data_order: volume.metadata.data_order,
        valueRange: volume.metadata.value_min !== undefined && volume.metadata.value_max !== undefined
          ? { min: volume.metadata.value_min, max: volume.metadata.value_max }
          : null,
        kind: volume.kind,
        fermi_energy: volume.fermi_energy,
        bandIndex: effectiveBandIndex,
        resolution: effectiveResolution,
        energy_reference: energyRef,
        // Part B: BXSF coordinate system
        grid_vectors: gridVectors,
        grid_step_vectors: gridStepVectors,
        vector_lengths: vectorLengths,
        // Part C: Structure overlay
        structure_atoms: structureAtoms,
        lattice_vectors_cart: latticeVectors,
      });
      
    } catch (e) {
      // Ignore abort errors
      if (e instanceof Error && e.message.includes('aborted')) {
        return;
      }
      
      // Only set error if still current
      if (currentSeq === latestSeqRef.current && compileKey === latestKeyRef.current) {
        setError(`Error: ${e instanceof Error ? e.message : String(e)}`);
      }
    } finally {
      if (currentSeq === latestSeqRef.current && compileKey === latestKeyRef.current) {
        setLoading(false);
      }
    }
  }, [generateCompileKey, loadBlob]); // P3: Don't include useFullResolution in deps to avoid recreating on every toggle

  // Load fixtures on mount
  useEffect(() => {
    loadFixtures();
  }, [loadFixtures]);

  // P3: Handle resolution toggle (must recompile)
  const handleResolutionToggle = useCallback((newUseFull: boolean) => {
    setUseFullResolution(newUseFull);
    if (compiledVolume) {
      const newResolution = newUseFull ? 'full' : 'preview';
      // Use current state directly (not from closure)
      compileFixture(
        compiledVolume.fixture,
        compiledVolume.bandIndex,
        newResolution
      );
    }
  }, [compiledVolume, compileFixture]);

  // P2: Handle band change (must recompile)
  const handleBandChange = useCallback((newBand: number) => {
    setSelectedBandIndex(newBand);
    if (compiledVolume && compiledVolume.fixture.kind === 'bxsf') {
      compileFixture(
        compiledVolume.fixture,
        newBand,
        compiledVolume.resolution
      );
    }
  }, [compiledVolume, compileFixture]);

  return (
    <div className="volume-viewer-sandbox">
      <div className="volume-viewer-sandbox-header">
        <h2>Volume Viewer Sandbox (MVP)</h2>
        <p>Test fixtures → compile → blob → metadata</p>
      </div>
      
      {error && (
        <div className="volume-viewer-sandbox-error">
          Error: {error}
        </div>
      )}
      
      <div className="volume-viewer-sandbox-layout">
        <div className="volume-viewer-sandbox-sidebar">
          <h3>Fixtures ({fixtures.length})</h3>
          <div className="volume-viewer-sandbox-fixture-list">
            {fixtures.map(fixture => (
              <div
                key={fixture.id}
                className={`volume-viewer-sandbox-fixture-item ${compiledVolume?.fixture.id === fixture.id ? 'selected' : ''}`}
                onClick={() => {
                  const bandIdx = fixture.kind === 'bxsf' ? (selectedBandIndex ?? 1) : undefined;
                  compileFixture(fixture, bandIdx, useFullResolution ? 'full' : 'preview');
                }}
              >
                <div className="fixture-name">{fixture.label}</div>
                <div className="fixture-type">{fixture.kind.toUpperCase()}</div>
                {compiledVolume?.fixture.id === fixture.id && (
                  <div className="fixture-status">✓ Loaded</div>
                )}
              </div>
            ))}
          </div>
        </div>
        
        <div className="volume-viewer-sandbox-main">
          {loading && <div className="volume-viewer-loading">Compiling...</div>}
          
          {compiledVolume && (
            <div className="volume-viewer-sandbox-content">
              {/* Debug Panel */}
              <div className="volume-viewer-debug">
                <h4>Debug Info</h4>
                <div className="debug-row">
                  <span className="debug-label">Fixture:</span>
                  <span className="debug-value">{compiledVolume.fixture.label}</span>
                </div>
                <div className="debug-row">
                  <span className="debug-label">Compile Key:</span>
                  <span className="debug-value" style={{ fontSize: '0.75em', wordBreak: 'break-all' }}>{compiledVolume.key}</span>
                </div>
                <div className="debug-row">
                  <span className="debug-label">Seq:</span>
                  <span className="debug-value">{compiledVolume.seq}</span>
                </div>
                <div className="debug-row">
                  <span className="debug-label">Blob ID:</span>
                  <span className="debug-value" style={{ fontSize: '0.75em' }}>{compiledVolume.blobId.slice(0, 8)}...</span>
                </div>
                <div className="debug-row">
                  <span className="debug-label">Dims:</span>
                  <span className="debug-value">
                    {compiledVolume.dims[0]}×{compiledVolume.dims[1]}×{compiledVolume.dims[2]} ({compiledVolume.resolution})
                  </span>
                </div>
                <div className="debug-row">
                  <span className="debug-label">Value Range:</span>
                  <span className="debug-value">
                    {compiledVolume.valueRange 
                      ? `${compiledVolume.valueRange.min.toFixed(4)} .. ${compiledVolume.valueRange.max.toFixed(4)}`
                      : '—'}
                  </span>
                </div>
                <div className="debug-row">
                  <span className="debug-label">Current ISO:</span>
                  <span className="debug-value">
                    {isovalue.toFixed(4)}
                  </span>
                </div>
                <div className="debug-row">
                  <span className="debug-label">Triangles:</span>
                  <span className="debug-value">{meshStats.trianglesCount}</span>
                </div>
                {compiledVolume.bbox && (
                  <>
                    <div className="debug-row">
                      <span className="debug-label">BBox Min:</span>
                      <span className="debug-value">
                        [{compiledVolume.bbox.min.map(v => v.toFixed(2)).join(', ')}]
                      </span>
                    </div>
                    <div className="debug-row">
                      <span className="debug-label">BBox Max:</span>
                      <span className="debug-value">
                        [{compiledVolume.bbox.max.map(v => v.toFixed(2)).join(', ')}]
                      </span>
                    </div>
                    <div className="debug-row">
                      <span className="debug-label">Center:</span>
                      <span className="debug-value">
                        [{compiledVolume.bbox.center.map(v => v.toFixed(2)).join(', ')}]
                      </span>
                    </div>
                    <div className="debug-row">
                      <span className="debug-label">Max Extent:</span>
                      <span className="debug-value">{compiledVolume.bbox.maxExtent.toFixed(2)}</span>
                    </div>
                  </>
                )}
                {/* P1: Energy reference info for BXSF */}
                {compiledVolume.fermi_energy !== undefined && (
                  <>
                    <div className="debug-row">
                      <span className="debug-label">Fermi Energy:</span>
                      <span className="debug-value">{compiledVolume.fermi_energy.toFixed(4)}</span>
                    </div>
                    {compiledVolume.energy_reference && (
                      <>
                        <div className="debug-row">
                          <span className="debug-label">Energy Reference:</span>
                          <span className="debug-value">{compiledVolume.energy_reference.reference}</span>
                        </div>
                        <div className="debug-row">
                          <span className="debug-label">ISO Default Reason:</span>
                          <span className="debug-value">Rule {compiledVolume.energy_reference.iso_default_reason}</span>
                        </div>
                      </>
                    )}
                  </>
                )}
                {meshStats.volumeStats && (
                  <>
                    <div className="debug-row">
                      <span className="debug-label">Active Cubes:</span>
                      <span className="debug-value">{meshStats.volumeStats.nActiveCubes}</span>
                    </div>
                  </>
                )}
                {/* Part B: BXSF coordinate system debug */}
                {compiledVolume.kind === 'fermi_surface' && compiledVolume.grid_vectors && (
                  <>
                    <div className="debug-row" style={{ marginTop: '8px', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '8px' }}>
                      <span className="debug-label">B1:</span>
                      <span className="debug-value" style={{ fontSize: '0.8em' }}>
                        [{compiledVolume.grid_vectors[0].map(v => v.toFixed(4)).join(', ')}]
                      </span>
                    </div>
                    <div className="debug-row">
                      <span className="debug-label">B2:</span>
                      <span className="debug-value" style={{ fontSize: '0.8em' }}>
                        [{compiledVolume.grid_vectors[1].map(v => v.toFixed(4)).join(', ')}]
                      </span>
                    </div>
                    <div className="debug-row">
                      <span className="debug-label">B3:</span>
                      <span className="debug-value" style={{ fontSize: '0.8em' }}>
                        [{compiledVolume.grid_vectors[2].map(v => v.toFixed(4)).join(', ')}]
                      </span>
                    </div>
                    {compiledVolume.vector_lengths && (
                      <>
                        <div className="debug-row">
                          <span className="debug-label">|B1|:</span>
                          <span className="debug-value">{compiledVolume.vector_lengths[0].toFixed(4)}</span>
                        </div>
                        <div className="debug-row">
                          <span className="debug-label">|B2|:</span>
                          <span className="debug-value">{compiledVolume.vector_lengths[1].toFixed(4)}</span>
                        </div>
                        <div className="debug-row">
                          <span className="debug-label">|B3|:</span>
                          <span className="debug-value">{compiledVolume.vector_lengths[2].toFixed(4)}</span>
                        </div>
                      </>
                    )}
                    {compiledVolume.grid_step_vectors && (
                      <>
                        <div className="debug-row">
                          <span className="debug-label">dB1:</span>
                          <span className="debug-value" style={{ fontSize: '0.75em' }}>
                            [{compiledVolume.grid_step_vectors[0].map(v => v.toFixed(6)).join(', ')}]
                          </span>
                        </div>
                        <div className="debug-row">
                          <span className="debug-label">dB2:</span>
                          <span className="debug-value" style={{ fontSize: '0.75em' }}>
                            [{compiledVolume.grid_step_vectors[1].map(v => v.toFixed(6)).join(', ')}]
                          </span>
                        </div>
                        <div className="debug-row">
                          <span className="debug-label">dB3:</span>
                          <span className="debug-value" style={{ fontSize: '0.75em' }}>
                            [{compiledVolume.grid_step_vectors[2].map(v => v.toFixed(6)).join(', ')}]
                          </span>
                        </div>
                      </>
                    )}
                  </>
                )}
              </div>
              
              {/* 3D Canvas */}
              <div className="volume-viewer-canvas-container">
                <Canvas camera={{ position: [5, 5, 5], fov: 50 }} frameloop="demand">
                  <Suspense fallback={null}>
                    <ambientLight intensity={0.5} />
                    <directionalLight position={[10, 10, 5]} intensity={0.8} />
                    <Grid args={[10, 10]} />
                    
                    {/* Part C: XSF Overlay - Atoms + Unit Cell */}
                    {compiledVolume.kind === 'volume' && (
                      <>
                        <AtomOverlay
                          atoms={compiledVolume.structure_atoms || []}
                          visible={showAtoms}
                        />
                        <UnitCellOverlay
                          latticeVectors={compiledVolume.lattice_vectors_cart || [[0,0,0], [0,0,0], [0,0,0]]}
                          origin={compiledVolume.volume.metadata.origin_cart}
                          visible={showCell && !!compiledVolume.lattice_vectors_cart}
                        />
                      </>
                    )}
                    
                    {/* Part C: BXSF Overlay - Brillouin Zone */}
                    {compiledVolume.kind === 'fermi_surface' && compiledVolume.grid_vectors && (
                      <BrillouinZoneOverlay
                        origin={compiledVolume.volume.metadata.origin_cart}
                        reciprocalVectors={compiledVolume.grid_vectors}
                        visible={showBZ}
                      />
                    )}
                    
                    <IsosurfaceMesh
                      volumeData={compiledVolume.blobData}
                      metadata={{
                        ...compiledVolume.volume.metadata,
                        grid_shape: compiledVolume.dims,
                      }}
                      isovalue={isovalue}
                      color="#4a90e2"
                      opacity={0.8}
                      meshKey={meshKeyRef.current}
                      compileSeq={compiledVolume.seq}
                      onMeshGenerated={(_nVertices, nTriangles, stats) => {
                        // P0: Only update if seq matches (prevent stale results)
                        if (compiledVolume.seq === latestSeqRef.current && compiledVolume.key === latestKeyRef.current) {
                          setMeshStats({
                            trianglesCount: nTriangles,
                            volumeStats: stats || null,
                          });
                          // Update bbox if available
                          if (stats?.bboxMin && stats?.bboxMax && stats?.center && stats?.maxExtent !== undefined) {
                            setCompiledVolume(prev => prev ? {
                              ...prev,
                              bbox: {
                                min: stats.bboxMin!,
                                max: stats.bboxMax!,
                                center: stats.center!,
                                maxExtent: stats.maxExtent!,
                              },
                            } : null);
                          }
                        }
                      }}
                      onError={(err) => {
                        if (compiledVolume.seq === latestSeqRef.current && compiledVolume.key === latestKeyRef.current) {
                          setError(`Mesh generation failed: ${err}`);
                        }
                      }}
                    />
                    {showPlusMinusIso && (
                      <IsosurfaceMesh
                        volumeData={compiledVolume.blobData}
                        metadata={{
                          ...compiledVolume.volume.metadata,
                          grid_shape: compiledVolume.dims,
                        }}
                        isovalue={-isovalue}
                        color="#e24a4a"
                        opacity={0.6}
                        meshKey={meshKeyRef.current + 1000}
                        compileSeq={compiledVolume.seq}
                        onMeshGenerated={(_nVertices, nTriangles, stats) => {
                          if (compiledVolume.seq === latestSeqRef.current && compiledVolume.key === latestKeyRef.current) {
                            setMeshStats(prev => ({
                              trianglesCount: prev.trianglesCount + nTriangles,
                              volumeStats: stats ? {
                                ...(prev.volumeStats || {}),
                                ...stats,
                              } : prev.volumeStats,
                            }));
                          }
                        }}
                        onError={(err) => {
                          if (compiledVolume.seq === latestSeqRef.current && compiledVolume.key === latestKeyRef.current) {
                            setError(`Mesh generation failed (negative iso): ${err}`);
                          }
                        }}
                      />
                    )}
                    
                    <OrbitControls 
                      onChange={() => {
                        // P3: Do nothing - frameloop="demand" handles this
                      }}
                    />
                  </Suspense>
                </Canvas>
                
                {meshStats.trianglesCount === 0 && (
                  <div className="volume-viewer-canvas-warning">
                    0 triangles (adjust iso value)
                  </div>
                )}
              </div>
              
              {/* Controls */}
              <div className="volume-viewer-controls">
                {/* P2: Band selector for BXSF */}
                {compiledVolume.kind === 'fermi_surface' && compiledVolume.volume.n_bands !== undefined && (
                  <div className="volume-viewer-control-row">
                    <label>
                      Band:
                      <select
                        value={compiledVolume.bandIndex ?? 1}
                        onChange={(e) => {
                          const newBand = parseInt(e.target.value, 10);
                          handleBandChange(newBand);
                        }}
                        disabled={loading}
                      >
                        {Array.from({ length: compiledVolume.volume.n_bands }, (_, i) => i + 1).map(bandNum => (
                          <option key={bandNum} value={bandNum}>
                            Band {bandNum}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                )}
                
                {/* P3: Resolution toggle */}
                <div className="volume-viewer-control-row">
                  <label>
                    <input
                      type="checkbox"
                      checked={compiledVolume.resolution === 'full'}
                      onChange={(e) => {
                        handleResolutionToggle(e.target.checked);
                      }}
                      disabled={loading}
                    />
                    Full Resolution (preview is faster)
                  </label>
                </div>
                
                <div className="volume-viewer-control-row">
                  <label>
                    Isovalue:
                    <input
                      type="range"
                      min={compiledVolume.valueRange?.min ?? -1}
                      max={compiledVolume.valueRange?.max ?? 1}
                      step={compiledVolume.valueRange ? Math.abs(compiledVolume.valueRange.max - compiledVolume.valueRange.min) / 100 : 0.01}
                      value={isovalue}
                      onChange={(e) => {
                        const newIso = parseFloat(e.target.value);
                        setIsovalue(newIso);
                        // B1: Debug iso change (throttled - only log on mouse up)
                      }}
                      onMouseUp={(e) => {
                        // B1: Log once when dragging stops
                        const newIso = parseFloat((e.target as HTMLInputElement).value);
                        console.debug(`[iso] setIso=${newIso.toFixed(4)}`);
                      }}
                      disabled={!compiledVolume}
                    />
                    <span className="volume-viewer-control-value">
                      {isovalue.toFixed(4)}
                    </span>
                    {/* P1: BXSF "Set iso=Ef" and "Set iso=0" buttons */}
                    {compiledVolume.fermi_energy !== undefined && compiledVolume.kind === 'fermi_surface' && (
                      <>
                        <button
                          onClick={() => setIsovalue(compiledVolume.fermi_energy!)}
                          className="volume-viewer-set-ef-button"
                          disabled={loading}
                        >
                          Set iso = Ef ({compiledVolume.fermi_energy.toFixed(4)})
                        </button>
                        <button
                          onClick={() => setIsovalue(0)}
                          className="volume-viewer-set-ef-button"
                          disabled={loading}
                        >
                          Set iso = 0
                        </button>
                      </>
                    )}
                  </label>
                  {compiledVolume.valueRange && (
                    <div className="volume-viewer-iso-warning">
                      {isovalue < compiledVolume.valueRange.min || isovalue > compiledVolume.valueRange.max ? (
                        <span className="iso-out-of-range">⚠ ISO out of range</span>
                      ) : null}
                    </div>
                  )}
                </div>
                <div className="volume-viewer-control-row">
                  <label>
                    <input
                      type="checkbox"
                      checked={showPlusMinusIso}
                      onChange={(e) => setShowPlusMinusIso(e.target.checked)}
                      disabled={!compiledVolume}
                    />
                    ±iso (dual surface)
                  </label>
                </div>
                
                {/* Part C: Overlay toggles */}
                {compiledVolume.kind === 'volume' && (
                  <>
                    <div className="volume-viewer-control-row">
                      <label>
                        <input
                          type="checkbox"
                          checked={showAtoms}
                          onChange={(e) => setShowAtoms(e.target.checked)}
                          disabled={!compiledVolume || !compiledVolume.structure_atoms || compiledVolume.structure_atoms.length === 0}
                        />
                        Show atoms {compiledVolume.structure_atoms && compiledVolume.structure_atoms.length > 0 ? `(${compiledVolume.structure_atoms.length})` : '(none)'}
                      </label>
                    </div>
                    <div className="volume-viewer-control-row">
                      <label>
                        <input
                          type="checkbox"
                          checked={showCell}
                          onChange={(e) => setShowCell(e.target.checked)}
                          disabled={!compiledVolume || !compiledVolume.lattice_vectors_cart}
                        />
                        Show unit cell
                      </label>
                    </div>
                  </>
                )}
                {compiledVolume.kind === 'fermi_surface' && (
                  <div className="volume-viewer-control-row">
                    <label>
                      <input
                        type="checkbox"
                        checked={showBZ}
                        onChange={(e) => setShowBZ(e.target.checked)}
                        disabled={!compiledVolume || !compiledVolume.grid_vectors}
                      />
                      Show BZ box
                    </label>
                  </div>
                )}
              </div>
              
              {/* Metadata panel */}
              <div className="volume-viewer-sandbox-metadata">
                <h3>Metadata: {compiledVolume.volume.artifact_id}</h3>
                <div className="metadata-section">
                  <h4>Grid Info</h4>
                  <pre>{JSON.stringify({
                    grid_shape: compiledVolume.dims,
                    coordinate_system: compiledVolume.volume.metadata.coordinate_system,
                    data_order: compiledVolume.data_order,
                  }, null, 2)}</pre>
                </div>
                
                {compiledVolume.volume.n_bands !== undefined && (
                  <div className="metadata-section">
                    <h4>Fermi Surface Info</h4>
                    <pre>{JSON.stringify({
                      n_bands: compiledVolume.volume.n_bands,
                      band_index: compiledVolume.bandIndex,
                      fermi_energy: compiledVolume.fermi_energy,
                    }, null, 2)}</pre>
                  </div>
                )}
              </div>
            </div>
          )}
          
          {!compiledVolume && !loading && (
            <div className="volume-viewer-sandbox-placeholder">
              Select a fixture to compile and view metadata
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
