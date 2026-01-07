/**
 * VolumeViewerSandbox - Development sandbox for volume visualization
 * 
 * MVP: Lists fixtures, compiles to blob, displays metadata + 3D isosurface
 */

import { useState, useEffect, useCallback, Suspense } from 'react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Grid } from '@react-three/drei';
import { useQVClient } from '../../hooks/useQVClient';
import './VolumeViewerSandbox.css';

interface Fixture {
  id: string;
  name: string;
  file_path: string;
  type: 'xsf' | 'bxsf';
  example_dir: string;
}

interface CompiledVolume {
  artifact_id: string;
  kind: string;
  metadata: any;
  blob_id: string;
  preview_blob_id?: string;
  n_bands?: number;
  band_index?: number;
  fermi_energy?: number;
}

export function VolumeViewerSandbox() {
  const qv = useQVClient();
  const [fixtures, setFixtures] = useState<Fixture[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [compiledVolumes, setCompiledVolumes] = useState<Map<string, CompiledVolume>>(new Map());
  const [selectedFixture, setSelectedFixture] = useState<Fixture | null>(null);
  
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
    
    // Use a temporary calc_dir (sandbox output)
    // In production, this would be a real calculation directory
    const calcDir = '/tmp/qv-sandbox-volume';
    
    try {
      const response = await qv.request('compile_fixture_volume', {
        file_path: fixture.file_path,
        calc_dir: calcDir,
      });
      
      if (response.ok && response.data) {
        setCompiledVolumes(prev => new Map(prev).set(fixture.id, response.data as CompiledVolume));
        setSelectedFixture(fixture);
      } else {
        setError(response.error?.message || 'Failed to compile volume');
      }
    } catch (e) {
      setError(`Error compiling volume: ${e}`);
    } finally {
      setLoading(false);
    }
  }, [qv]);
  
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
                    <OrbitControls />
                  </Suspense>
                </Canvas>
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

