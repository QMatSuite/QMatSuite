/**
 * StructureViewer3D - 3D ball-and-stick viewer for crystal structures
 * 
 * Uses react-three-fiber for WebGL rendering with Three.js
 */

import { useRef, useMemo, useState } from 'react';
import { Canvas, useThree } from '@react-three/fiber';
import { OrbitControls, Line, Text } from '@react-three/drei';
import * as THREE from 'three';
import type { StructureVisData, AtomVisData, BondVisData } from '../../types/qv';
import './StructureViewer3D.css';

// =============================================================================
// Types
// =============================================================================

interface StructureViewer3DProps {
  data: StructureVisData | null;
  isLoading?: boolean;
  showBonds?: boolean;
  showUnitCell?: boolean;
  showLabels?: boolean;
  atomScale?: number;
  bondScale?: number;
}

interface AtomProps {
  atom: AtomVisData;
  scale: number;
  showLabel?: boolean;
}

interface BondProps {
  bond: BondVisData;
  scale: number;
}

interface UnitCellProps {
  matrix: number[][];
}

interface BoxFrameProps {
  bounds: [number, number, number, number, number, number];
}

// =============================================================================
// Atom Component
// =============================================================================

function Atom({ atom, scale, showLabel }: AtomProps) {
  const meshRef = useRef<THREE.Mesh>(null);
  const [hovered, setHovered] = useState(false);
  
  // Parse color from hex string
  const color = useMemo(() => new THREE.Color(atom.color), [atom.color]);
  
  return (
    <group position={atom.cart_coords}>
      <mesh
        ref={meshRef}
        onPointerOver={() => setHovered(true)}
        onPointerOut={() => setHovered(false)}
      >
        <sphereGeometry args={[atom.radius * scale, 32, 32]} />
        <meshStandardMaterial 
          color={hovered ? '#ffffff' : color}
          metalness={0.3}
          roughness={0.4}
        />
      </mesh>
      {showLabel && (
        <Text
          position={[0, atom.radius * scale + 0.3, 0]}
          fontSize={0.3}
          color="#ffffff"
          anchorX="center"
          anchorY="bottom"
        >
          {atom.element}
        </Text>
      )}
    </group>
  );
}

// =============================================================================
// Bond Component
// =============================================================================

function Bond({ bond, scale }: BondProps) {
  const start = useMemo(() => new THREE.Vector3(...bond.coord1), [bond.coord1]);
  const end = useMemo(() => new THREE.Vector3(...bond.coord2), [bond.coord2]);
  
  // Calculate cylinder transformation
  const midpoint = useMemo(() => {
    return new THREE.Vector3().addVectors(start, end).multiplyScalar(0.5);
  }, [start, end]);
  
  const direction = useMemo(() => {
    return new THREE.Vector3().subVectors(end, start);
  }, [start, end]);
  
  const length = useMemo(() => direction.length(), [direction]);
  
  // Create quaternion for rotation
  const quaternion = useMemo(() => {
    const orientation = new THREE.Quaternion();
    const axis = new THREE.Vector3(0, 1, 0);
    orientation.setFromUnitVectors(axis, direction.clone().normalize());
    return orientation;
  }, [direction]);
  
  return (
    <mesh position={midpoint} quaternion={quaternion}>
      <cylinderGeometry args={[0.08 * scale, 0.08 * scale, length, 16]} />
      <meshStandardMaterial color="#888888" metalness={0.2} roughness={0.6} />
    </mesh>
  );
}

// =============================================================================
// Unit Cell Component
// =============================================================================

function UnitCell({ matrix }: UnitCellProps) {
  // Extract lattice vectors
  const a = useMemo(() => new THREE.Vector3(...matrix[0]), [matrix]);
  const b = useMemo(() => new THREE.Vector3(...matrix[1]), [matrix]);
  const c = useMemo(() => new THREE.Vector3(...matrix[2]), [matrix]);
  
  // Calculate all 8 corners of the unit cell
  const corners = useMemo(() => {
    const o = new THREE.Vector3(0, 0, 0);
    return [
      o.clone(),                                    // 0: origin
      o.clone().add(a),                             // 1: a
      o.clone().add(b),                             // 2: b
      o.clone().add(c),                             // 3: c
      o.clone().add(a).add(b),                      // 4: a+b
      o.clone().add(a).add(c),                      // 5: a+c
      o.clone().add(b).add(c),                      // 6: b+c
      o.clone().add(a).add(b).add(c),               // 7: a+b+c
    ];
  }, [a, b, c]);
  
  // Define the 12 edges of the unit cell
  const edges = useMemo(() => [
    // Bottom face
    [corners[0], corners[1]], // 0->1 (a)
    [corners[0], corners[2]], // 0->2 (b)
    [corners[1], corners[4]], // 1->4 (b)
    [corners[2], corners[4]], // 2->4 (a)
    // Top face
    [corners[3], corners[5]], // 3->5 (a)
    [corners[3], corners[6]], // 3->6 (b)
    [corners[5], corners[7]], // 5->7 (b)
    [corners[6], corners[7]], // 6->7 (a)
    // Vertical edges
    [corners[0], corners[3]], // 0->3 (c)
    [corners[1], corners[5]], // 1->5 (c)
    [corners[2], corners[6]], // 2->6 (c)
    [corners[4], corners[7]], // 4->7 (c)
  ], [corners]);
  
  return (
    <group>
      {edges.map((edge, idx) => (
        <Line
          key={idx}
          points={[edge[0].toArray(), edge[1].toArray()]}
          color="#4a90d9"
          lineWidth={1.5}
          dashed
          dashSize={0.1}
          gapSize={0.05}
        />
      ))}
    </group>
  );
}

// =============================================================================
// Box Frame Component (for Box mode)
// =============================================================================

function BoxFrame({ bounds }: BoxFrameProps) {
  const [xmin, xmax, ymin, ymax, zmin, zmax] = bounds;
  
  // Calculate all 8 corners of the axis-aligned box
  const corners = useMemo(() => {
    return [
      new THREE.Vector3(xmin, ymin, zmin),  // 0: origin
      new THREE.Vector3(xmax, ymin, zmin),  // 1: +x
      new THREE.Vector3(xmin, ymax, zmin),  // 2: +y
      new THREE.Vector3(xmin, ymin, zmax),  // 3: +z
      new THREE.Vector3(xmax, ymax, zmin),  // 4: +x+y
      new THREE.Vector3(xmax, ymin, zmax),  // 5: +x+z
      new THREE.Vector3(xmin, ymax, zmax),  // 6: +y+z
      new THREE.Vector3(xmax, ymax, zmax),  // 7: +x+y+z
    ];
  }, [xmin, xmax, ymin, ymax, zmin, zmax]);
  
  // Define the 12 edges of the box
  const edges = useMemo(() => [
    // Bottom face
    [corners[0], corners[1]], // 0->1 (x)
    [corners[0], corners[2]], // 0->2 (y)
    [corners[1], corners[4]], // 1->4 (y)
    [corners[2], corners[4]], // 2->4 (x)
    // Top face
    [corners[3], corners[5]], // 3->5 (x)
    [corners[3], corners[6]], // 3->6 (y)
    [corners[5], corners[7]], // 5->7 (y)
    [corners[6], corners[7]], // 6->7 (x)
    // Vertical edges
    [corners[0], corners[3]], // 0->3 (z)
    [corners[1], corners[5]], // 1->5 (z)
    [corners[2], corners[6]], // 2->6 (z)
    [corners[4], corners[7]], // 4->7 (z)
  ], [corners]);
  
  return (
    <group>
      {edges.map((edge, idx) => (
        <Line
          key={idx}
          points={[edge[0].toArray(), edge[1].toArray()]}
          color="#ff6b6b"
          lineWidth={1.5}
          dashed
          dashSize={0.1}
          gapSize={0.05}
        />
      ))}
    </group>
  );
}

// =============================================================================
// Camera Controller - Auto-fit to structure (only on structure change)
// =============================================================================

interface CameraControllerProps {
  atoms: AtomVisData[];
  structureId: string | null;  // Only reset camera when this changes
}

function CameraController({ atoms, structureId }: CameraControllerProps) {
  const { camera } = useThree();
  const lastStructureId = useRef<string | null>(null);
  
  useMemo(() => {
    // Only reset camera when structure ID changes (not on supercell/boundary changes)
    if (atoms.length === 0) return;
    if (structureId === lastStructureId.current) return;
    
    lastStructureId.current = structureId;
    
    // Calculate bounding box
    let minX = Infinity, minY = Infinity, minZ = Infinity;
    let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity;
    
    for (const atom of atoms) {
      const [x, y, z] = atom.cart_coords;
      minX = Math.min(minX, x); maxX = Math.max(maxX, x);
      minY = Math.min(minY, y); maxY = Math.max(maxY, y);
      minZ = Math.min(minZ, z); maxZ = Math.max(maxZ, z);
    }
    
    // Calculate center and size
    const centerX = (minX + maxX) / 2;
    const centerY = (minY + maxY) / 2;
    const centerZ = (minZ + maxZ) / 2;
    const size = Math.max(maxX - minX, maxY - minY, maxZ - minZ);
    
    // Position camera
    const distance = size * 2;
    camera.position.set(centerX + distance, centerY + distance * 0.5, centerZ + distance);
    camera.lookAt(centerX, centerY, centerZ);
  }, [atoms, camera, structureId]);
  
  return null;
}

// =============================================================================
// Scene Content
// =============================================================================

interface SceneProps {
  data: StructureVisData;
  showBonds: boolean;
  showUnitCell: boolean;
  showLabels: boolean;
  atomScale: number;
  bondScale: number;
  structureId: string | null;
  boxBounds?: [number, number, number, number, number, number] | null;
}

function Scene({ data, showBonds, showUnitCell, showLabels, atomScale, bondScale, structureId, boxBounds }: SceneProps) {
  const allAtoms = useMemo(() => {
    const atoms = [...data.atoms];
    if (data.boundary_atoms) {
      atoms.push(...data.boundary_atoms);
    }
    return atoms;
  }, [data.atoms, data.boundary_atoms]);
  
  return (
    <>
      {/* Lighting */}
      <ambientLight intensity={0.5} />
      <directionalLight position={[10, 10, 5]} intensity={1} />
      <directionalLight position={[-10, -10, -5]} intensity={0.3} />
      
      {/* Atoms */}
      {allAtoms.map((atom, idx) => (
        <Atom 
          key={`atom-${idx}`} 
          atom={atom} 
          scale={atomScale}
          showLabel={showLabels}
        />
      ))}
      
      {/* Bonds */}
      {showBonds && data.bonds.map((bond, idx) => (
        <Bond key={`bond-${idx}`} bond={bond} scale={bondScale} />
      ))}
      
      {/* Unit Cell or Box Frame */}
      {showUnitCell && data.lattice && (
        data.display_mode === 'box' && boxBounds ? (
          <BoxFrame bounds={boxBounds} />
        ) : (
          <UnitCell matrix={data.lattice.matrix} />
        )
      )}
      
      {/* Camera Controller - only reset on structure change */}
      <CameraController atoms={allAtoms} structureId={structureId} />
      
      {/* Controls */}
      <OrbitControls 
        enablePan={true}
        enableZoom={true}
        enableRotate={true}
        minDistance={1}
        maxDistance={100}
      />
    </>
  );
}

// =============================================================================
// Main Component
// =============================================================================

interface StructureViewer3DPropsExtended extends StructureViewer3DProps {
  structureId?: string | null;
  onSupercellChange?: (supercell: [number, number, number]) => void;
  onRepeatBoundaryChange?: (repeatBoundary: boolean) => void;
  onDisplayModeChange?: (mode: 'primitive' | 'supercell' | 'conventional' | 'box') => void;
  onBoxBoundsChange?: (bounds: [number, number, number, number, number, number] | null) => void;
  currentDisplayMode?: 'primitive' | 'supercell' | 'conventional' | 'box';
  currentBoxBounds?: [number, number, number, number, number, number] | null;
}

export function StructureViewer3D({
  data,
  isLoading = false,
  showBonds = true,
  showUnitCell = true,
  showLabels = false,
  atomScale = 0.4,
  bondScale = 1.0,
  structureId = null,
  onSupercellChange,
  onRepeatBoundaryChange,
  onDisplayModeChange,
  onBoxBoundsChange,
  currentDisplayMode = 'primitive',
  currentBoxBounds = null,
}: StructureViewer3DPropsExtended) {
  const [localShowBonds, setLocalShowBonds] = useState(showBonds);
  const [localShowUnitCell, setLocalShowUnitCell] = useState(showUnitCell);
  const [localShowLabels, setLocalShowLabels] = useState(showLabels);
  const [localAtomScale, setLocalAtomScale] = useState(atomScale);
  const [supercellX, setSupercellX] = useState(1);
  const [supercellY, setSupercellY] = useState(1);
  const [supercellZ, setSupercellZ] = useState(1);
  const [repeatBoundary, setRepeatBoundary] = useState(true);
  const [displayMode, setDisplayMode] = useState<'primitive' | 'supercell' | 'conventional' | 'box'>(currentDisplayMode);
  const [boxBounds, setBoxBounds] = useState<[number, number, number, number, number, number] | null>(currentBoxBounds);
  
  // Get unique elements present in the structure
  const presentElements = useMemo(() => {
    if (!data) return [];
    const elements = new Set<string>();
    data.atoms.forEach(atom => elements.add(atom.element));
    if (data.boundary_atoms) {
      data.boundary_atoms.forEach(atom => elements.add(atom.element));
    }
    return Array.from(elements);
  }, [data]);
  
  const handleSupercellChange = (axis: 'x' | 'y' | 'z', value: number) => {
    const newX = axis === 'x' ? value : supercellX;
    const newY = axis === 'y' ? value : supercellY;
    const newZ = axis === 'z' ? value : supercellZ;
    
    if (axis === 'x') setSupercellX(value);
    if (axis === 'y') setSupercellY(value);
    if (axis === 'z') setSupercellZ(value);
    
    onSupercellChange?.([newX, newY, newZ]);
  };
  
  const handleRepeatBoundaryChange = (checked: boolean) => {
    setRepeatBoundary(checked);
    onRepeatBoundaryChange?.(checked);
  };
  
  const handleDisplayModeChange = (mode: 'primitive' | 'supercell' | 'conventional' | 'box') => {
    setDisplayMode(mode);
    // IMPORTANT: Do NOT mutate repeatBoundary state - preserve user preference
    // The effective boundary repeat will be computed in App.tsx
    onDisplayModeChange?.(mode);
  };
  
  const handleBoxBoundsChange = (bounds: [number, number, number, number, number, number] | null) => {
    setBoxBounds(bounds);
    onBoxBoundsChange?.(bounds);
  };
  
  if (isLoading) {
    return (
      <div className="structure-viewer-3d structure-viewer-3d--loading">
        <div className="loading-spinner" />
        <p>Loading 3D structure...</p>
      </div>
    );
  }
  
  if (!data) {
    return (
      <div className="structure-viewer-3d structure-viewer-3d--empty">
        <div className="panel-placeholder">
          <span className="panel-icon">🔮</span>
          <h3>No Structure Data</h3>
          <p>Select a structure to view its 3D visualization.</p>
        </div>
      </div>
    );
  }
  
  return (
    <div className="structure-viewer-3d">
      {/* Info Bar */}
      <div className="viewer-info">
        <span className="info-formula">{data.formula}</span>
        <span className="info-stat">{data.n_atoms} atoms</span>
        <span className="info-stat">{data.n_bonds} bonds</span>
        {data.supercell && data.supercell.some(s => s > 1) && (
          <span className="info-supercell">
            {data.supercell.join('×')} supercell
          </span>
        )}
      </div>
      
      {/* Controls Row 1: Display options */}
      <div className="viewer-controls">
        <label className="control-item">
          <input
            type="checkbox"
            checked={localShowBonds}
            onChange={(e) => setLocalShowBonds(e.target.checked)}
          />
          Bonds
        </label>
        <label className="control-item">
          <input
            type="checkbox"
            checked={localShowUnitCell}
            onChange={(e) => setLocalShowUnitCell(e.target.checked)}
          />
          Unit Cell
        </label>
        <label className="control-item">
          <input
            type="checkbox"
            checked={localShowLabels}
            onChange={(e) => setLocalShowLabels(e.target.checked)}
          />
          Labels
        </label>
        <label className="control-item control-item--slider">
          Size
          <input
            type="range"
            min="0.2"
            max="1.0"
            step="0.1"
            value={localAtomScale}
            onChange={(e) => setLocalAtomScale(parseFloat(e.target.value))}
          />
        </label>
      </div>
      
      {/* Controls Row 2: Display mode */}
      {onDisplayModeChange && (
        <div className="viewer-controls viewer-controls--mode">
          <label className="control-item">
            <span className="control-label">Display Mode:</span>
            <select
              value={displayMode}
              onChange={(e) => handleDisplayModeChange(e.target.value as 'primitive' | 'supercell' | 'conventional' | 'box')}
            >
              <option value="primitive">Primitive</option>
              <option value="supercell">Supercell</option>
              <option value="conventional">Conventional</option>
              <option value="box">Box</option>
            </select>
          </label>
        </div>
      )}
      
      {/* Controls Row 3: Supercell and boundary */}
      {(onSupercellChange || onRepeatBoundaryChange) && displayMode === 'supercell' && (
        <div className="viewer-controls viewer-controls--supercell">
          {onSupercellChange && (
            <div className="control-group">
              <span className="control-group-label">Supercell:</span>
              <label className="control-item control-item--number">
                a
                <input
                  type="number"
                  min="1"
                  max="5"
                  value={supercellX}
                  onChange={(e) => handleSupercellChange('x', parseInt(e.target.value) || 1)}
                />
              </label>
              <label className="control-item control-item--number">
                b
                <input
                  type="number"
                  min="1"
                  max="5"
                  value={supercellY}
                  onChange={(e) => handleSupercellChange('y', parseInt(e.target.value) || 1)}
                />
              </label>
              <label className="control-item control-item--number">
                c
                <input
                  type="number"
                  min="1"
                  max="5"
                  value={supercellZ}
                  onChange={(e) => handleSupercellChange('z', parseInt(e.target.value) || 1)}
                />
              </label>
            </div>
          )}
          {onRepeatBoundaryChange && (
            <label className="control-item">
              <input
                type="checkbox"
                checked={repeatBoundary}
                onChange={(e) => handleRepeatBoundaryChange(e.target.checked)}
              />
              Boundary Repeat
            </label>
          )}
        </div>
      )}
      
      {/* Controls Row 4: Box bounds (for box mode) */}
      {onBoxBoundsChange && displayMode === 'box' && (
        <div className="viewer-controls viewer-controls--box">
          <div className="control-group">
            <span className="control-group-label">Box Bounds (Å):</span>
            <label className="control-item control-item--number">
              X: <input
                type="number"
                step="0.1"
                value={boxBounds ? boxBounds[0].toFixed(1) : '0'}
                onChange={(e) => {
                  const val = parseFloat(e.target.value) || 0;
                  const newBounds: [number, number, number, number, number, number] = boxBounds 
                    ? [val, boxBounds[1], boxBounds[2], boxBounds[3], boxBounds[4], boxBounds[5]]
                    : [val, 10, 0, 10, 0, 10];
                  handleBoxBoundsChange(newBounds);
                }}
              />
              to <input
                type="number"
                step="0.1"
                value={boxBounds ? boxBounds[1].toFixed(1) : '10'}
                onChange={(e) => {
                  const val = parseFloat(e.target.value) || 10;
                  const newBounds: [number, number, number, number, number, number] = boxBounds 
                    ? [boxBounds[0], val, boxBounds[2], boxBounds[3], boxBounds[4], boxBounds[5]]
                    : [0, val, 0, 10, 0, 10];
                  handleBoxBoundsChange(newBounds);
                }}
              />
            </label>
            <label className="control-item control-item--number">
              Y: <input
                type="number"
                step="0.1"
                value={boxBounds ? boxBounds[2].toFixed(1) : '0'}
                onChange={(e) => {
                  const val = parseFloat(e.target.value) || 0;
                  const newBounds: [number, number, number, number, number, number] = boxBounds 
                    ? [boxBounds[0], boxBounds[1], val, boxBounds[3], boxBounds[4], boxBounds[5]]
                    : [0, 10, val, 10, 0, 10];
                  handleBoxBoundsChange(newBounds);
                }}
              />
              to <input
                type="number"
                step="0.1"
                value={boxBounds ? boxBounds[3].toFixed(1) : '10'}
                onChange={(e) => {
                  const val = parseFloat(e.target.value) || 10;
                  const newBounds: [number, number, number, number, number, number] = boxBounds 
                    ? [boxBounds[0], boxBounds[1], boxBounds[2], val, boxBounds[4], boxBounds[5]]
                    : [0, 10, 0, val, 0, 10];
                  handleBoxBoundsChange(newBounds);
                }}
              />
            </label>
            <label className="control-item control-item--number">
              Z: <input
                type="number"
                step="0.1"
                value={boxBounds ? boxBounds[4].toFixed(1) : '0'}
                onChange={(e) => {
                  const val = parseFloat(e.target.value) || 0;
                  const newBounds: [number, number, number, number, number, number] = boxBounds 
                    ? [boxBounds[0], boxBounds[1], boxBounds[2], boxBounds[3], val, boxBounds[5]]
                    : [0, 10, 0, 10, val, 10];
                  handleBoxBoundsChange(newBounds);
                }}
              />
              to <input
                type="number"
                step="0.1"
                value={boxBounds ? boxBounds[5].toFixed(1) : '10'}
                onChange={(e) => {
                  const val = parseFloat(e.target.value) || 10;
                  const newBounds: [number, number, number, number, number, number] = boxBounds 
                    ? [boxBounds[0], boxBounds[1], boxBounds[2], boxBounds[3], boxBounds[4], val]
                    : [0, 10, 0, 10, 0, val];
                  handleBoxBoundsChange(newBounds);
                }}
              />
            </label>
          </div>
        </div>
      )}
      
      {/* Controls Row 5: Boundary repeat (for other modes, static text in box mode) */}
      {onRepeatBoundaryChange && displayMode !== 'supercell' && (
        <div className="viewer-controls viewer-controls--boundary">
          {displayMode === 'box' ? (
            <div className="control-item" style={{ color: '#888', fontSize: '0.9em' }}>
              Boundary Repeat: disabled in Box mode
            </div>
          ) : (
            <label className="control-item">
              <input
                type="checkbox"
                checked={repeatBoundary}
                onChange={(e) => handleRepeatBoundaryChange(e.target.checked)}
              />
              Boundary Repeat
            </label>
          )}
        </div>
      )}
      
      {/* Canvas */}
      <div className="viewer-canvas">
        <Canvas
          camera={{ position: [10, 10, 10], fov: 50 }}
          gl={{ antialias: true, alpha: true }}
        >
          <Scene
            data={data}
            showBonds={localShowBonds}
            showUnitCell={localShowUnitCell}
            showLabels={localShowLabels}
            atomScale={localAtomScale}
            bondScale={bondScale}
            structureId={structureId}
            boxBounds={boxBounds}
          />
        </Canvas>
      </div>
      
      {/* Legend - only show elements present in the structure */}
      <div className="viewer-legend">
        {presentElements.map((element) => {
          const color = data.element_colors?.[element] || '#888888';
          return (
            <div key={element} className="legend-item">
              <span 
                className="legend-color" 
                style={{ background: color }}
              />
              <span className="legend-label">{element}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

