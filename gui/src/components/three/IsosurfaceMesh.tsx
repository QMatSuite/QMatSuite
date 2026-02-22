/**
 * IsosurfaceMesh — shared Three.js isosurface component.
 *
 * Extracted from VolumeViewerSandbox for reuse by both the sandbox
 * and the production Field3DVizPanel.
 */

import { useEffect, useMemo, useRef } from 'react';
import * as THREE from 'three';
import { generateIsosurface, type VolumeStats } from '../../utils/marchingCubes';

export interface IsosurfaceMetadata {
  grid_shape: [number, number, number];
  origin_cart: [number, number, number];
  grid_vectors_cart: [[number, number, number], [number, number, number], [number, number, number]];
  data_order: 'fortran_i_fastest' | 'c_k_fastest';
}

export interface IsosurfaceMeshProps {
  volumeData: Float32Array;
  metadata: IsosurfaceMetadata;
  isovalue: number;
  color: string;
  opacity: number;
  meshKey: number;
  compileSeq: number;
  onMeshGenerated?: (nVertices: number, nTriangles: number, stats?: VolumeStats) => void;
  onError?: (error: string) => void;
}

export function IsosurfaceMesh({
  volumeData,
  metadata,
  isovalue,
  color,
  opacity,
  meshKey,
  compileSeq,
  onMeshGenerated,
  onError,
}: IsosurfaceMeshProps) {
  const meshRef = useRef<THREE.Mesh>(null);
  const geometryRef = useRef<THREE.BufferGeometry | null>(null);
  const materialRef = useRef<THREE.MeshStandardMaterial | null>(null);
  const lastSeqRef = useRef<number>(-1);
  const lastIsoRef = useRef<number | null>(null);

  const geometry = useMemo(() => {
    const isStaleCompile = compileSeq < lastSeqRef.current;
    const isSameIso = lastIsoRef.current !== null && Math.abs(lastIsoRef.current - isovalue) < 1e-10;

    if (isStaleCompile && isSameIso) {
      return geometryRef.current || new THREE.BufferGeometry();
    }

    if (compileSeq > lastSeqRef.current) {
      lastSeqRef.current = compileSeq;
    }
    lastIsoRef.current = isovalue;

    if (geometryRef.current) {
      geometryRef.current.dispose();
    }

    try {
      const dims = metadata.grid_shape;
      const stats: { current: VolumeStats } = { current: { nNaN: 0, nInf: 0, nLess: 0, nGreater: 0, nEq: 0, nActiveCubes: 0 } };

      const result = generateIsosurface(
        volumeData,
        dims,
        metadata.origin_cart,
        metadata.grid_vectors_cart,
        metadata.data_order,
        isovalue,
        stats,
      );

      const debugMc = typeof localStorage !== 'undefined' && localStorage.getItem('qms_mc_debug') === '1';
      if (process.env.NODE_ENV === 'development') {
        if (debugMc && stats.current.nActiveCubes > 0) {
          console.debug(`[MC] seq=${compileSeq} iso=${isovalue.toFixed(4)} triangles=${result.indices.length / 3} activeCubes=${stats.current.nActiveCubes}`);
        }
      }

      if (onMeshGenerated) {
        const nVertices = result.positions.length / 3;
        const nTriangles = result.indices.length / 3;
        onMeshGenerated(nVertices, nTriangles, stats.current);
      }

      const geom = new THREE.BufferGeometry();
      geom.setAttribute('position', new THREE.BufferAttribute(result.positions, 3));
      geom.setAttribute('normal', new THREE.BufferAttribute(result.normals, 3));
      geom.setIndex(new THREE.BufferAttribute(result.indices, 1));

      geometryRef.current = geom;
      return geom;
    } catch (e) {
      const errorMsg = e instanceof Error ? e.message : String(e);
      console.error(`[MC Error] seq=${compileSeq} iso=${isovalue.toFixed(4)}:`, errorMsg);
      if (onError) {
        onError(errorMsg);
      }
      return new THREE.BufferGeometry();
    }
  }, [volumeData, metadata, isovalue, meshKey, compileSeq, onMeshGenerated, onError]);

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

  useEffect(() => {
    if (meshRef.current && geometry) {
      const oldGeom = meshRef.current.geometry;
      meshRef.current.geometry = geometry;
      if (oldGeom && oldGeom !== geometry && oldGeom !== geometryRef.current) {
        oldGeom.dispose();
      }
    }
  }, [geometry]);

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
