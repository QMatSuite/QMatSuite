/**
 * Part C: Overlay components for Volume Viewer
 * - XSF: Atoms + Unit Cell
 * - BXSF: Brillouin Zone box
 */

import { useMemo } from 'react';

interface AtomOverlayProps {
  atoms: Array<{ element: string; position: [number, number, number] }>;
  visible: boolean;
}

export function AtomOverlay({ atoms, visible }: AtomOverlayProps) {
  if (!visible || !atoms || atoms.length === 0) {
    return null;
  }
  
  // Element colors (simple mapping)
  const elementColors: Record<string, number> = {
    'Ga': 0xcccccc, // Gray
    'As': 0xff8000, // Orange
    'C': 0x333333,  // Black
    'Pb': 0x666699, // Dark gray
    'Cu': 0xcc8033, // Copper
  };
  
  return (
    <group>
      {atoms.map((atom, idx) => {
        const [x, y, z] = atom.position;
        const color = elementColors[atom.element] || 0xb0b0b0;
        return (
          <mesh key={idx} position={[x, y, z]}>
            <sphereGeometry args={[0.25, 16, 16]} />
            <meshStandardMaterial
              color={color}
              metalness={0.3}
              roughness={0.7}
            />
          </mesh>
        );
      })}
    </group>
  );
}

interface UnitCellOverlayProps {
  latticeVectors: [[number, number, number], [number, number, number], [number, number, number]];
  origin: [number, number, number];
  visible: boolean;
}

export function UnitCellOverlay({ latticeVectors, origin, visible }: UnitCellOverlayProps) {
  const edges = useMemo(() => {
    if (!visible || !latticeVectors) {
      return { positions: new Float32Array(0), indices: new Uint16Array(0) };
    }
    
    const [a1, a2, a3] = latticeVectors;
    const [ox, oy, oz] = origin;
    
    // 8 corners of parallelepiped
    const corners: Array<[number, number, number]> = [
      [ox, oy, oz], // 0
      [ox + a1[0], oy + a1[1], oz + a1[2]], // 1
      [ox + a1[0] + a2[0], oy + a1[1] + a2[1], oz + a1[2] + a2[2]], // 2
      [ox + a2[0], oy + a2[1], oz + a2[2]], // 3
      [ox + a3[0], oy + a3[1], oz + a3[2]], // 4
      [ox + a1[0] + a3[0], oy + a1[1] + a3[1], oz + a1[2] + a3[2]], // 5
      [ox + a1[0] + a2[0] + a3[0], oy + a1[1] + a2[1] + a3[1], oz + a1[2] + a2[2] + a3[2]], // 6
      [ox + a2[0] + a3[0], oy + a2[1] + a3[1], oz + a2[2] + a3[2]], // 7
    ];
    
    // 12 edges of parallelepiped
    const edgePairs: Array<[number, number]> = [
      [0, 1], [1, 2], [2, 3], [3, 0], // Bottom face
      [4, 5], [5, 6], [6, 7], [7, 4], // Top face
      [0, 4], [1, 5], [2, 6], [3, 7], // Vertical edges
    ];
    
    const positions = new Float32Array(corners.length * 3);
    corners.forEach((corner, idx) => {
      positions[idx * 3] = corner[0];
      positions[idx * 3 + 1] = corner[1];
      positions[idx * 3 + 2] = corner[2];
    });
    
    const indices = new Uint16Array(edgePairs.length * 2);
    edgePairs.forEach(([i, j], idx) => {
      indices[idx * 2] = i;
      indices[idx * 2 + 1] = j;
    });
    
    return { positions, indices };
  }, [latticeVectors, origin, visible]);
  
  if (!visible || !latticeVectors) {
    return null;
  }
  
  return (
    <lineSegments>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={edges.positions.length / 3}
          array={edges.positions}
          itemSize={3}
        />
        <bufferAttribute
          attach="index"
          count={edges.indices.length}
          array={edges.indices}
          itemSize={1}
        />
      </bufferGeometry>
      <lineBasicMaterial color={0x00ff00} linewidth={2} />
    </lineSegments>
  );
}

interface BrillouinZoneOverlayProps {
  origin: [number, number, number];
  reciprocalVectors: [[number, number, number], [number, number, number], [number, number, number]];
  visible: boolean;
}

export function BrillouinZoneOverlay({ origin, reciprocalVectors, visible }: BrillouinZoneOverlayProps) {
  const edges = useMemo(() => {
    if (!visible || !reciprocalVectors) {
      return { positions: new Float32Array(0), indices: new Uint16Array(0) };
    }
    
    const [b1, b2, b3] = reciprocalVectors;
    const [ox, oy, oz] = origin;
    
    // 8 corners of reciprocal parallelepiped
    const corners: Array<[number, number, number]> = [
      [ox, oy, oz], // 0
      [ox + b1[0], oy + b1[1], oz + b1[2]], // 1
      [ox + b1[0] + b2[0], oy + b1[1] + b2[1], oz + b1[2] + b2[2]], // 2
      [ox + b2[0], oy + b2[1], oz + b2[2]], // 3
      [ox + b3[0], oy + b3[1], oz + b3[2]], // 4
      [ox + b1[0] + b3[0], oy + b1[1] + b3[1], oz + b1[2] + b3[2]], // 5
      [ox + b1[0] + b2[0] + b3[0], oy + b1[1] + b2[1] + b3[1], oz + b1[2] + b2[2] + b3[2]], // 6
      [ox + b2[0] + b3[0], oy + b2[1] + b3[1], oz + b2[2] + b3[2]], // 7
    ];
    
    // 12 edges of parallelepiped
    const edgePairs: Array<[number, number]> = [
      [0, 1], [1, 2], [2, 3], [3, 0], // Bottom face
      [4, 5], [5, 6], [6, 7], [7, 4], // Top face
      [0, 4], [1, 5], [2, 6], [3, 7], // Vertical edges
    ];
    
    const positions = new Float32Array(corners.length * 3);
    corners.forEach((corner, idx) => {
      positions[idx * 3] = corner[0];
      positions[idx * 3 + 1] = corner[1];
      positions[idx * 3 + 2] = corner[2];
    });
    
    const indices = new Uint16Array(edgePairs.length * 2);
    edgePairs.forEach(([i, j], idx) => {
      indices[idx * 2] = i;
      indices[idx * 2 + 1] = j;
    });
    
    return { positions, indices };
  }, [origin, reciprocalVectors, visible]);
  
  if (!visible || !reciprocalVectors) {
    return null;
  }
  
  return (
    <lineSegments>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          count={edges.positions.length / 3}
          array={edges.positions}
          itemSize={3}
        />
        <bufferAttribute
          attach="index"
          count={edges.indices.length}
          array={edges.indices}
          itemSize={1}
        />
      </bufferGeometry>
      <lineBasicMaterial color={0xff00ff} linewidth={2} />
    </lineSegments>
  );
}

