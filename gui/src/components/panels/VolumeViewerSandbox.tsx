/**
 * VolumeViewerSandbox - Development sandbox for volume visualization
 * 
 * MVP: Lists fixtures, compiles to blob, displays metadata + 3D isosurface
 */

import { useState, useEffect, useCallback, Suspense, useRef, useMemo } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Grid } from '@react-three/drei';
import * as THREE from 'three';
import { generateIsosurface } from '../../utils/marchingCubes';
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

interface IsosurfaceMeshProps {
  volumeData: Float32Array;
  metadata: VolumeMetadata;
  isovalue: number;
  color: string;
  opacity: number;
  meshKey: number;
  onMeshGenerated?: (nVertices: number, nTriangles: number) => void;
  onError?: (error: string) => void;
}

function IsosurfaceMesh({ 
  volumeData, 
  metadata, 
  isovalue, 
  color, 
  opacity,
  meshKey,
  onMeshGenerated,
  onError,
}: IsosurfaceMeshProps) {
  const meshRef = useRef<THREE.Mesh>(null);
  const geometryRef = useRef<THREE.BufferGeometry | null>(null);
  const materialRef = useRef<THREE.MeshStandardMaterial | null>(null);
  
  const geometry = useMemo(() => {
    // Dispose old geometry
    if (geometryRef.current) {
      geometryRef.current.dispose();
    }
    
    try {
      const result = generateIsosurface(
        volumeData,
        metadata.grid_shape,
        metadata.origin_cart,
        metadata.grid_vectors_cart,
        metadata.data_order,
        isovalue
      );
      
      const geom = new THREE.BufferGeometry();
      geom.setAttribute('position', new THREE.BufferAttribute(result.positions, 3));
      geom.setAttribute('normal', new THREE.BufferAttribute(result.normals, 3));
      geom.setIndex(new THREE.BufferAttribute(result.indices, 1));
      
      geometryRef.current = geom;
      
      const nVertices = result.positions.length / 3;
      const nTriangles = result.indices.length / 3;
      
      if (onMeshGenerated) {
        onMeshGenerated(nVertices, nTriangles);
      }
      
      return geom;
    } catch (e) {
      const errorMsg = e instanceof Error ? e.message : String(e);
      console.error('Failed to generate isosurface:', e);
      if (onError) {
        onError(errorMsg);
      }
      return new THREE.BufferGeometry();
    }
  }, [volumeData, metadata, isovalue, meshKey, onMeshGenerated, onError]);
  
  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (geometryRef.current) {
        geometryRef.current.dispose();
      }
      if (materialRef.current) {
        materialRef.current.dispose();
      }
    };
  }, []);
  
  return (
    <mesh key={meshKey} ref={meshRef} geometry={geometry}>
      <meshStandardMaterial
        ref={materialRef}
        color={color}
        opacity={opacity}
        transparent={opacity < 1}
        side={THREE.DoubleSide}
      />
    </mesh>
  );
}

export function VolumeViewerSandbox() {
  const [fixtures, setFixtures] = useState<Fixture[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [compiledVolumes, setCompiledVolumes] = useState<Map<string, CompiledVolume>>(new Map());
  const [selectedFixture, setSelectedFixture] = useState<Fixture | null>(null);
  const [volumeData, setVolumeData] = useState<Float32Array | null>(null);
  const [isovalue, setIsovalue] = useState(0);
  const [showPlusMinusIso, setShowPlusMinusIso] = useState(false);
  const [isLoadingBlob, setIsLoadingBlob] = useState(false);
  
  // Request tracking for race condition prevention
  const requestIdRef = useRef(0);
  const latestRequestIdRef = useRef(0);
  const [requestId, setRequestId] = useState(0);
  const [meshKey, setMeshKey] = useState(0);
  
  // Debug state
  const [debugInfo, setDebugInfo] = useState<{
    selectedLabel: string | null;
    requestId: number;
    blobId: string | null;
    dims: [number, number, number] | null;
    valueRange: { min: number; max: number } | null;
    currentIso: number;
    trianglesCount: number;
  }>({
    selectedLabel: null,
    requestId: 0,
    blobId: null,
    dims: null,
    valueRange: null,
    currentIso: 0,
    trianglesCount: 0,
  });
  
  const loadBlob = useCallback(async (
    volume: CompiledVolume, 
    calcDir: string,
    currentRequestId: number
  ) => {
    setIsLoadingBlob(true);
    try {
      // Use preview blob for MVP
      const blobId = volume.preview_blob_id || volume.blob_id;
      
      console.log(`[onBlobReadStart] requestId=${currentRequestId} blobId=${blobId}`);
      
      // Read blob via preload API
      const buffer = await (window as any).qv.readBlob(blobId, calcDir);
      
      // Check if this request is still current
      if (currentRequestId !== latestRequestIdRef.current) {
        console.log(`[onStaleDiscarded] requestId=${currentRequestId} (latest=${latestRequestIdRef.current})`);
        return;
      }
      
      const data = new Float32Array(buffer);
      
      console.log(`[onBlobReadDone] requestId=${currentRequestId} byteLength=${buffer.byteLength}`);
      
      setVolumeData(data);
      setDebugInfo(prev => ({ ...prev, blobId }));
    } catch (e) {
      if (currentRequestId === latestRequestIdRef.current) {
        setError(`Failed to load blob: ${e}`);
      }
    } finally {
      if (currentRequestId === latestRequestIdRef.current) {
        setIsLoadingBlob(false);
      }
    }
  }, []);
  
  const loadFixtures = useCallback(async () => {
    try {
      const response = await (window as any).qv.request('list_wannier_3d_fixtures', {});
      if (response.ok && response.data?.fixtures) {
        setFixtures(response.data.fixtures);
      } else {
        setError(response.error?.message || 'Failed to load fixtures');
      }
    } catch (e) {
      setError(`Error loading fixtures: ${e}`);
    }
  }, []);
  
  const clearMesh = useCallback(() => {
    setVolumeData(null);
    setMeshKey(prev => prev + 1); // Force remount
    setDebugInfo(prev => ({ ...prev, trianglesCount: 0, blobId: null }));
  }, []);
  
  
  const compileFixture = useCallback(async (fixture: Fixture) => {
    // Increment request ID
    requestIdRef.current += 1;
    const currentRequestId = requestIdRef.current;
    latestRequestIdRef.current = currentRequestId;
    
    console.log(`[onSelect] label=${fixture.label} requestId=${currentRequestId}`);
    
    // Reset state
    setLoading(true);
    setError(null);
    clearMesh();
    setRequestId(currentRequestId);
    setDebugInfo({
      selectedLabel: fixture.label,
      requestId: currentRequestId,
      blobId: null,
      dims: null,
      valueRange: null,
      currentIso: 0,
      trianglesCount: 0,
    });
    
    // Use a temporary calc_dir (sandbox output)
    const calcDir = '/tmp/qv-sandbox-volume';
    
    try {
      const response = await (window as any).qv.request('compile_fixture_volume', {
        file_path: fixture.path,
        calc_dir: calcDir,
      });
      
      // Check if this request is still current
      if (currentRequestId !== latestRequestIdRef.current) {
        console.log(`[onStaleDiscarded] requestId=${currentRequestId} (latest=${latestRequestIdRef.current})`);
        return;
      }
      
      if (response.ok && response.data) {
        const volume = response.data as CompiledVolume;
        
        console.log(`[onCompileDone] label=${fixture.label} requestId=${currentRequestId} blobId=${volume.preview_blob_id || volume.blob_id}`);
        
        setCompiledVolumes(prev => new Map(prev).set(fixture.id, volume));
        setSelectedFixture(fixture);
        setDebugInfo(prev => ({
          ...prev,
          dims: volume.metadata.grid_shape,
          valueRange: volume.metadata.value_min !== undefined && volume.metadata.value_max !== undefined
            ? { min: volume.metadata.value_min, max: volume.metadata.value_max }
            : null,
        }));
        
        // Load preview blob
        await loadBlob(volume, calcDir, currentRequestId);
        
        // Check again after blob load
        if (currentRequestId !== latestRequestIdRef.current) {
          return;
        }
        
        // Set initial isovalue (adaptive)
        if (volume.metadata.value_min !== undefined && volume.metadata.value_max !== undefined) {
          if (volume.metadata.value_max === volume.metadata.value_min) {
            setError('Volume has constant value (no variation)');
            setIsovalue(volume.metadata.value_min);
          } else {
            // Default: 20% from min
            const defaultIso = volume.metadata.value_min + 0.2 * (volume.metadata.value_max - volume.metadata.value_min);
            setIsovalue(defaultIso);
            setDebugInfo(prev => ({ ...prev, currentIso: defaultIso }));
          }
        } else if (volume.metadata.value_mean !== undefined) {
          setIsovalue(volume.metadata.value_mean);
          setDebugInfo(prev => ({ ...prev, currentIso: volume.metadata.value_mean! }));
        }
      } else {
        if (currentRequestId === latestRequestIdRef.current) {
          setError(response.error?.message || 'Failed to compile volume');
        }
      }
    } catch (e) {
      if (currentRequestId === latestRequestIdRef.current) {
        setError(`Error compiling volume: ${e}`);
      }
    } finally {
      if (currentRequestId === latestRequestIdRef.current) {
        setLoading(false);
      }
    }
  }, [loadBlob, clearMesh]);
  
  // Load fixtures on mount
  useEffect(() => {
    loadFixtures();
  }, [loadFixtures]);
  
  const selectedVolume = selectedFixture ? compiledVolumes.get(selectedFixture.id) : null;
  
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
                {fixtures.map(fixture => {
              const isCompiled = compiledVolumes.has(fixture.id);
              return (
                <div
                  key={fixture.id}
                  className={`volume-viewer-sandbox-fixture-item ${selectedFixture?.id === fixture.id ? 'selected' : ''} ${isCompiled ? 'compiled' : ''}`}
                  onClick={() => {
                    if (!isCompiled) {
                      compileFixture(fixture);
                    } else {
                      // Re-compile to ensure fresh state
                      compileFixture(fixture);
                    }
                  }}
                >
                  <div className="fixture-name">{fixture.label}</div>
                  <div className="fixture-type">{fixture.kind.toUpperCase()}</div>
                  {isCompiled && <div className="fixture-status">✓ Compiled</div>}
                </div>
              );
            })}
          </div>
        </div>
        
        <div className="volume-viewer-sandbox-main">
          {loading && <div className="volume-viewer-loading">Compiling...</div>}
          
          {selectedVolume && (
            <div className="volume-viewer-sandbox-content">
              {/* Debug Panel */}
              <div className="volume-viewer-debug">
                <h4>Debug Info</h4>
                <div className="debug-row">
                  <span className="debug-label">Fixture:</span>
                  <span className="debug-value">{debugInfo.selectedLabel || 'none'}</span>
                </div>
                <div className="debug-row">
                  <span className="debug-label">Request ID:</span>
                  <span className="debug-value">{debugInfo.requestId}</span>
                </div>
                <div className="debug-row">
                  <span className="debug-label">Blob ID:</span>
                  <span className="debug-value">{debugInfo.blobId || 'none'}</span>
                </div>
                <div className="debug-row">
                  <span className="debug-label">Dims:</span>
                  <span className="debug-value">
                    {debugInfo.dims ? `${debugInfo.dims[0]}×${debugInfo.dims[1]}×${debugInfo.dims[2]}` : 'none'}
                  </span>
                </div>
                <div className="debug-row">
                  <span className="debug-label">Value Range:</span>
                  <span className="debug-value">
                    {debugInfo.valueRange 
                      ? `${debugInfo.valueRange.min.toFixed(4)} .. ${debugInfo.valueRange.max.toFixed(4)}`
                      : 'none'}
                  </span>
                </div>
                <div className="debug-row">
                  <span className="debug-label">Current ISO:</span>
                  <span className="debug-value">{debugInfo.currentIso.toFixed(4)}</span>
                </div>
                <div className="debug-row">
                  <span className="debug-label">Triangles:</span>
                  <span className="debug-value">{debugInfo.trianglesCount}</span>
                </div>
              </div>
              
              {/* 3D Canvas */}
              <div className="volume-viewer-canvas-container">
                <Canvas camera={{ position: [5, 5, 5], fov: 50 }}>
                  <Suspense fallback={null}>
                    <ambientLight intensity={0.5} />
                    <directionalLight position={[10, 10, 5]} intensity={0.8} />
                    <Grid args={[10, 10]} />
                    
                    {volumeData && !isLoadingBlob && (
                      <>
                        <IsosurfaceMesh
                          volumeData={volumeData}
                          metadata={selectedVolume.metadata}
                          isovalue={isovalue}
                          color="#4a90e2"
                          opacity={0.8}
                          meshKey={meshKey}
                          onMeshGenerated={(_nVertices, nTriangles) => {
                            console.log(`[onMeshDone] requestId=${requestId} nTriangles=${nTriangles}`);
                            setDebugInfo(prev => ({ ...prev, trianglesCount: nTriangles }));
                          }}
                          onError={(err) => {
                            console.error(`[onMeshError] requestId=${requestId} error=${err}`);
                            setError(`Mesh generation failed: ${err}`);
                          }}
                        />
                        {showPlusMinusIso && (
                          <IsosurfaceMesh
                            volumeData={volumeData}
                            metadata={selectedVolume.metadata}
                            isovalue={-isovalue}
                            color="#e24a4a"
                            opacity={0.6}
                            meshKey={meshKey + 1000} // Different key for second mesh
                            onMeshGenerated={(_nVertices, nTriangles) => {
                              // Only update if this is the latest request
                              if (requestId === latestRequestIdRef.current) {
                                setDebugInfo(prev => ({ ...prev, trianglesCount: prev.trianglesCount + nTriangles }));
                              }
                            }}
                            onError={(err) => {
                              if (requestId === latestRequestIdRef.current) {
                                setError(`Mesh generation failed (negative iso): ${err}`);
                              }
                            }}
                          />
                        )}
                      </>
                    )}
                    
                    <OrbitControls />
                  </Suspense>
                </Canvas>
                
                {isLoadingBlob && (
                  <div className="volume-viewer-canvas-loading">Loading blob...</div>
                )}
                
                {volumeData && !isLoadingBlob && debugInfo.trianglesCount === 0 && (
                  <div className="volume-viewer-canvas-warning">
                    0 triangles (adjust iso value)
                  </div>
                )}
              </div>
              
              {/* Controls */}
              <div className="volume-viewer-controls">
                <div className="volume-viewer-control-row">
                  <label>
                    Isovalue:
                    <input
                      type="range"
                      min={debugInfo.valueRange?.min ?? (selectedVolume.metadata.value_min ?? -1)}
                      max={debugInfo.valueRange?.max ?? (selectedVolume.metadata.value_max ?? 1)}
                      step={(() => {
                        const min = debugInfo.valueRange?.min ?? (selectedVolume.metadata.value_min ?? -1);
                        const max = debugInfo.valueRange?.max ?? (selectedVolume.metadata.value_max ?? 1);
                        return Math.abs(max - min) / 100;
                      })()}
                      value={isovalue}
                      onChange={(e) => {
                        const newIso = parseFloat(e.target.value);
                        setIsovalue(newIso);
                        setDebugInfo(prev => ({ ...prev, currentIso: newIso }));
                      }}
                      disabled={!volumeData}
                    />
                    <span className="volume-viewer-control-value">{isovalue.toFixed(4)}</span>
                  </label>
                  {debugInfo.valueRange && (
                    <div className="volume-viewer-iso-warning">
                      {isovalue < debugInfo.valueRange.min || isovalue > debugInfo.valueRange.max ? (
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
                      disabled={!volumeData}
                    />
                    ±iso (dual surface)
                  </label>
                </div>
              </div>
              
              {/* Metadata panel */}
              <div className="volume-viewer-sandbox-metadata">
              <h3>Metadata: {selectedVolume.artifact_id}</h3>
              <div className="metadata-section">
                <h4>Grid Info</h4>
                <pre>{JSON.stringify({
                  grid_shape: selectedVolume.metadata.grid_shape,
                  coordinate_system: selectedVolume.metadata.coordinate_system,
                  data_order: selectedVolume.metadata.data_order,
                }, null, 2)}</pre>
              </div>
              
              <div className="metadata-section">
                <h4>Blob IDs</h4>
                <pre>{JSON.stringify({
                  blob_id: selectedVolume.blob_id,
                  preview_blob_id: selectedVolume.preview_blob_id,
                }, null, 2)}</pre>
              </div>
              
              {selectedVolume.n_bands !== undefined && (
                <div className="metadata-section">
                  <h4>Fermi Surface Info</h4>
                  <pre>{JSON.stringify({
                    n_bands: selectedVolume.n_bands,
                    band_index: selectedVolume.band_index,
                    fermi_energy: selectedVolume.fermi_energy,
                  }, null, 2)}</pre>
                </div>
              )}
              
              <div className="metadata-section">
                <h4>Full Metadata</h4>
                <pre>{JSON.stringify(selectedVolume.metadata, null, 2)}</pre>
              </div>
              </div>
            </div>
          )}
          
          {!selectedVolume && !loading && (
            <div className="volume-viewer-sandbox-placeholder">
              Select a fixture to compile and view metadata
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

