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
// Camera Controller - Auto-fit to structure
// =============================================================================

function CameraController({ atoms }: { atoms: AtomVisData[] }) {
  const { camera } = useThree();
  
  useMemo(() => {
    if (atoms.length === 0) return;
    
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
  }, [atoms, camera]);
  
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
}

function Scene({ data, showBonds, showUnitCell, showLabels, atomScale, bondScale }: SceneProps) {
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
      
      {/* Unit Cell */}
      {showUnitCell && data.lattice && (
        <UnitCell matrix={data.lattice.matrix} />
      )}
      
      {/* Camera Controller */}
      <CameraController atoms={allAtoms} />
      
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
  onSupercellChange?: (supercell: [number, number, number]) => void;
  onRepeatBoundaryChange?: (repeatBoundary: boolean) => void;
}

export function StructureViewer3D({
  data,
  isLoading = false,
  showBonds = true,
  showUnitCell = true,
  showLabels = false,
  atomScale = 0.4,
  bondScale = 1.0,
  onSupercellChange,
  onRepeatBoundaryChange,
}: StructureViewer3DPropsExtended) {
  const [localShowBonds, setLocalShowBonds] = useState(showBonds);
  const [localShowUnitCell, setLocalShowUnitCell] = useState(showUnitCell);
  const [localShowLabels, setLocalShowLabels] = useState(showLabels);
  const [localAtomScale, setLocalAtomScale] = useState(atomScale);
  const [supercellX, setSupercellX] = useState(1);
  const [supercellY, setSupercellY] = useState(1);
  const [supercellZ, setSupercellZ] = useState(1);
  const [repeatBoundary, setRepeatBoundary] = useState(false);
  
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
      
      {/* Controls Row 2: Supercell and boundary */}
      {(onSupercellChange || onRepeatBoundaryChange) && (
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

