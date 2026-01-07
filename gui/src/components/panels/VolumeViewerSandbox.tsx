/**
 * VolumeViewerSandbox - Development sandbox for volume visualization
 * 
 * MVP: Lists fixtures, compiles to blob, displays metadata + 3D isosurface
 */

import { useState, useEffect, useCallback, Suspense, useRef, useMemo } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import { OrbitControls, Grid } from '@react-three/drei';
import * as THREE from 'three';
import { useQVClient } from '../../hooks/useQVClient';
import { generateIsosurface } from '../../utils/marchingCubes';
import './VolumeViewerSandbox.css';

interface Fixture {
  id: string;
  name: string;
  file_path: string;
  type: 'xsf' | 'bxsf';
  example_dir: string;
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
}

function IsosurfaceMesh({ volumeData, metadata, isovalue, color, opacity }: IsosurfaceMeshProps) {
  const meshRef = useRef<THREE.Mesh>(null);
  
  const geometry = useMemo(() => {
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
      
      return geom;
    } catch (e) {
      console.error('Failed to generate isosurface:', e);
      return new THREE.BufferGeometry();
    }
  }, [volumeData, metadata, isovalue]);
  
  return (
    <mesh ref={meshRef} geometry={geometry}>
      <meshStandardMaterial
        color={color}
        opacity={opacity}
        transparent={opacity < 1}
        side={THREE.DoubleSide}
      />
    </mesh>
  );
}

export function VolumeViewerSandbox() {
  const qv = useQVClient();
  const [fixtures, setFixtures] = useState<Fixture[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [compiledVolumes, setCompiledVolumes] = useState<Map<string, CompiledVolume>>(new Map());
  const [selectedFixture, setSelectedFixture] = useState<Fixture | null>(null);
  const [volumeData, setVolumeData] = useState<Float32Array | null>(null);
  const [isovalue, setIsovalue] = useState(0);
  const [showPlusMinusIso, setShowPlusMinusIso] = useState(false);
  const [isLoadingBlob, setIsLoadingBlob] = useState(false);
  
  // Load fixtures on mount
  useEffect(() => {
    loadFixtures();
  }, []);
  
  const loadFixtures = useCallback(async () => {
    try {
      const response = await qv.request('list_wannier_3d_fixtures', {});
      if (response.ok && response.data?.fixtures) {
        setFixtures(response.data.fixtures);
      } else {
        setError(response.error?.message || 'Failed to load fixtures');
      }
    } catch (e) {
      setError(`Error loading fixtures: ${e}`);
    }
  }, [qv]);
  
  const compileFixture = useCallback(async (fixture: Fixture) => {
    setLoading(true);
    setError(null);
    setVolumeData(null);
    
    // Use a temporary calc_dir (sandbox output)
    const calcDir = '/tmp/qv-sandbox-volume';
    
    try {
      const response = await qv.request('compile_fixture_volume', {
        file_path: fixture.file_path,
        calc_dir: calcDir,
      });
      
      if (response.ok && response.data) {
        const volume = response.data as CompiledVolume;
        setCompiledVolumes(prev => new Map(prev).set(fixture.id, volume));
        setSelectedFixture(fixture);
        
        // Load preview blob
        await loadBlob(volume, calcDir);
        
        // Set initial isovalue
        if (volume.metadata.value_mean !== undefined) {
          setIsovalue(volume.metadata.value_mean);
        } else if (volume.metadata.value_max !== undefined && volume.metadata.value_min !== undefined) {
          setIsovalue((volume.metadata.value_max + volume.metadata.value_min) / 2);
        }
      } else {
        setError(response.error?.message || 'Failed to compile volume');
      }
    } catch (e) {
      setError(`Error compiling volume: ${e}`);
    } finally {
      setLoading(false);
    }
  }, [qv]);
  
  const loadBlob = useCallback(async (volume: CompiledVolume, calcDir: string) => {
    setIsLoadingBlob(true);
    try {
      // Use preview blob for MVP
      const blobId = volume.preview_blob_id || volume.blob_id;
      
      // Read blob via preload API
      const buffer = await (window as any).qv.readBlob(blobId, calcDir);
      const data = new Float32Array(buffer);
      
      setVolumeData(data);
    } catch (e) {
      setError(`Failed to load blob: ${e}`);
    } finally {
      setIsLoadingBlob(false);
    }
  }, []);
  
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
                      setSelectedFixture(fixture);
                    }
                  }}
                >
                  <div className="fixture-name">{fixture.name}</div>
                  <div className="fixture-type">{fixture.type.toUpperCase()}</div>
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
                        />
                        {showPlusMinusIso && (
                          <IsosurfaceMesh
                            volumeData={volumeData}
                            metadata={selectedVolume.metadata}
                            isovalue={-isovalue}
                            color="#e24a4a"
                            opacity={0.6}
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
              </div>
              
              {/* Controls */}
              <div className="volume-viewer-controls">
                <div className="volume-viewer-control-row">
                  <label>
                    Isovalue:
                    <input
                      type="range"
                      min={selectedVolume.metadata.value_min || -1}
                      max={selectedVolume.metadata.value_max || 1}
                      step={(Math.abs((selectedVolume.metadata.value_max || 1) - (selectedVolume.metadata.value_min || -1))) / 100}
                      value={isovalue}
                      onChange={(e) => setIsovalue(parseFloat(e.target.value))}
                      disabled={!volumeData}
                    />
                    <span className="volume-viewer-control-value">{isovalue.toFixed(4)}</span>
                  </label>
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

