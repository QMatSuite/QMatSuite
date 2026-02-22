import { useCallback, useMemo, useState } from 'react';
import {
  CartesianGrid,
  Customized,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import type { PrimitiveBundleData } from '../../types/qms';

interface FatbandsVizPanelProps {
  availableObjectTypes: string[];
  selectedObjectType: string | null;
  onSelectObjectType: (objectType: string) => void;
  shiftToFermi: boolean;
  onShiftToFermiChange: (enabled: boolean) => void;
  loading: boolean;
  error: string | null;
  bundle: PrimitiveBundleData | null;
  canPin: boolean;
  pinReason: string | null;
  pinMessage: string | null;
  pinning: boolean;
  onPin: () => Promise<void>;
}

interface ProjectionLabels {
  atoms: string[];
  orbitals: string[];
}

export function FatbandsVizPanel({
  availableObjectTypes,
  selectedObjectType,
  onSelectObjectType,
  shiftToFermi,
  onShiftToFermiChange,
  loading,
  error,
  bundle,
  canPin,
  pinReason,
  pinMessage,
  pinning,
  onPin,
}: FatbandsVizPanelProps) {
  const [selectedAtom, setSelectedAtom] = useState(0);
  const [selectedOrbital, setSelectedOrbital] = useState(-1); // -1 = sum all orbitals
  const [widthScale, setWidthScale] = useState(0.5);

  const projectionLabels = useMemo<ProjectionLabels>(() => {
    const labels = bundle?.arrays?.projection_labels as ProjectionLabels | undefined;
    return labels ?? { atoms: [], orbitals: [] };
  }, [bundle?.arrays?.projection_labels]);

  // Eigenvalues: 2D [kpoints, bands] or 3D [spin, kpoints, bands]
  const eigenvalues = useMemo<number[][]>(() => {
    const raw = bundle?.arrays?.eigenvalues as number[][] | number[][][] | undefined;
    if (!raw?.length) return [];
    // If 3D, take first spin channel
    if (Array.isArray(raw[0]?.[0])) {
      return (raw as number[][][])[0];
    }
    return raw as number[][];
  }, [bundle?.arrays?.eigenvalues]);

  // K-distances
  const kDistances = useMemo<number[]>(() => {
    const raw = bundle?.arrays?.k_distances as number[] | undefined;
    return raw ?? [];
  }, [bundle?.arrays?.k_distances]);

  // Projections: 4D [kpoints, bands, atoms, orbitals]
  const projections = useMemo<number[][][][] | null>(() => {
    const raw = bundle?.arrays?.projections as number[][][][] | undefined;
    return raw ?? null;
  }, [bundle?.arrays?.projections]);

  const nKpoints = kDistances.length;
  const nBands = eigenvalues.length > 0 ? eigenvalues[0]?.length ?? 0 : 0;

  // Compute projection weights for selected atom/orbital
  const weights = useMemo<number[][] | null>(() => {
    if (!projections || nKpoints === 0 || nBands === 0) return null;
    // weights[k][band] = sum of selected projections
    const w: number[][] = [];
    for (let k = 0; k < nKpoints; k++) {
      w[k] = [];
      for (let b = 0; b < nBands; b++) {
        let val = 0;
        if (selectedOrbital === -1) {
          // Sum all orbitals for selected atom
          const nOrb = projections[k]?.[b]?.[selectedAtom]?.length ?? 0;
          for (let o = 0; o < nOrb; o++) {
            val += projections[k]?.[b]?.[selectedAtom]?.[o] ?? 0;
          }
        } else {
          val = projections[k]?.[b]?.[selectedAtom]?.[selectedOrbital] ?? 0;
        }
        w[k][b] = val;
      }
    }
    return w;
  }, [projections, nKpoints, nBands, selectedAtom, selectedOrbital]);

  // Build chart data for base bands
  const chartData = useMemo(() => {
    if (!eigenvalues.length || !kDistances.length) return [];
    return kDistances.map((kd, ki) => {
      const row: Record<string, number | null> = { x: kd };
      for (let b = 0; b < nBands; b++) {
        row[`b${b}`] = eigenvalues[ki]?.[b] ?? null;
      }
      return row;
    });
  }, [eigenvalues, kDistances, nBands]);

  const markers = bundle?.render_meta?.markers ?? [];
  const fermiEnergy = bundle?.render_meta?.reference_energy ?? null;
  const kpathLabels = markers.map((m) => m.label).filter(Boolean).join(' \u2192 ');

  // Custom SVG renderer for fat band overlay
  const FatbandOverlay = useCallback((props: any) => {
    if (!weights || !kDistances.length || !eigenvalues.length) return null;
    const { xAxisMap, yAxisMap } = props;
    const xAxis = xAxisMap?.[0] ?? xAxisMap?.['0'];
    const yAxis = yAxisMap?.[0] ?? yAxisMap?.['0'];
    if (!xAxis?.scale || !yAxis?.scale) return null;

    const paths: JSX.Element[] = [];
    for (let b = 0; b < nBands; b++) {
      // Build upper and lower edge arrays
      const upper: [number, number][] = [];
      const lower: [number, number][] = [];
      for (let k = 0; k < nKpoints; k++) {
        const e = eigenvalues[k]?.[b];
        const w = weights[k]?.[b] ?? 0;
        if (e == null) continue;
        const halfWidth = w * widthScale;
        const px = xAxis.scale(kDistances[k]);
        const pyUp = yAxis.scale(e + halfWidth);
        const pyDown = yAxis.scale(e - halfWidth);
        if (typeof px !== 'number' || typeof pyUp !== 'number' || typeof pyDown !== 'number') continue;
        upper.push([px, pyUp]);
        lower.push([px, pyDown]);
      }
      if (upper.length < 2) continue;

      // Build SVG path: upper edge forward, lower edge backward
      const pathParts: string[] = [];
      pathParts.push(`M ${upper[0][0]} ${upper[0][1]}`);
      for (let i = 1; i < upper.length; i++) {
        pathParts.push(`L ${upper[i][0]} ${upper[i][1]}`);
      }
      for (let i = lower.length - 1; i >= 0; i--) {
        pathParts.push(`L ${lower[i][0]} ${lower[i][1]}`);
      }
      pathParts.push('Z');

      paths.push(
        <path
          d={pathParts.join(' ')}
          fill="hsl(210 70% 50%)"
          fillOpacity={0.4}
          key={`fb-${b}`}
          stroke="none"
        />
      );
    }

    return <g className="fatband-overlay">{paths}</g>;
  }, [weights, kDistances, eigenvalues, nKpoints, nBands, widthScale]);

  if (availableObjectTypes.length === 0) {
    return (
      <div className="analysis-surface__placeholder" data-testid="qms-analysis-no-objects">
        No analysis object is available for this step in the current run.
      </div>
    );
  }

  return (
    <div className="analysis-viz">
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
        <label className="analysis-viz__transform">
          <input
            checked={shiftToFermi}
            onChange={(event) => onShiftToFermiChange(event.target.checked)}
            type="checkbox"
          />
          Shift to Fermi level
        </label>
      </div>

      {loading ? <div className="analysis-surface__placeholder" data-testid="qms-analysis-loading">Loading analysis...</div> : null}
      {error ? <div className="analysis-surface__error" data-testid="qms-analysis-error">{error}</div> : null}

      {!loading && !error && bundle ? (
        <>
          <div className="analysis-viz__info">
            {fermiEnergy != null ? (
              <span data-testid="qms-analysis-fermi">E_F = {fermiEnergy.toFixed(4)} eV</span>
            ) : null}
            {kpathLabels ? (
              <span data-testid="qms-analysis-kpath">{kpathLabels}</span>
            ) : null}
          </div>

          {/* Fatband controls */}
          <div className="fatband-viz__controls">
            {projectionLabels.atoms.length > 0 ? (
              <div className="fatband-viz__selector">
                <label>Atom: </label>
                <select
                  value={selectedAtom}
                  onChange={(e) => setSelectedAtom(Number(e.target.value))}
                >
                  {projectionLabels.atoms.map((atom, i) => (
                    <option key={atom} value={i}>{atom}</option>
                  ))}
                </select>
              </div>
            ) : null}
            {projectionLabels.orbitals.length > 0 ? (
              <div className="fatband-viz__selector">
                <label>Orbital: </label>
                <select
                  value={selectedOrbital}
                  onChange={(e) => setSelectedOrbital(Number(e.target.value))}
                >
                  <option value={-1}>All</option>
                  {projectionLabels.orbitals.map((orb, i) => (
                    <option key={orb} value={i}>{orb}</option>
                  ))}
                </select>
              </div>
            ) : null}
            <div className="fatband-viz__selector">
              <label>Width (eV): </label>
              <input
                max={2.0}
                min={0.1}
                onChange={(e) => setWidthScale(Number(e.target.value))}
                step={0.1}
                type="range"
                value={widthScale}
              />
              <span>{widthScale.toFixed(1)}</span>
            </div>
          </div>

          {/* Chart with fat band overlay */}
          <div className="analysis-viz__plot" data-testid="qms-analysis-fatbands-chart">
            <ResponsiveContainer height={420} width="100%">
              <LineChart data={chartData} margin={{ top: 18, right: 20, left: 16, bottom: 16 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="x"
                  label={{ value: 'k-path', position: 'insideBottom', offset: -10 }}
                  tick={{ fontSize: 11 }}
                  type="number"
                />
                <YAxis
                  label={{ angle: -90, position: 'insideLeft', value: 'Energy (eV)' }}
                  tick={{ fontSize: 11 }}
                  type="number"
                />
                <Tooltip />
                {/* Fatband SVG overlay */}
                <Customized component={FatbandOverlay} />
                {/* Base band lines (thin grey) */}
                {Array.from({ length: Math.min(nBands, 200) }, (_, b) => (
                  <Line
                    dataKey={`b${b}`}
                    dot={false}
                    key={`b${b}`}
                    stroke="#888"
                    strokeWidth={0.8}
                    type="linear"
                  />
                ))}
                {markers.map((marker) => (
                  <ReferenceLine
                    key={`${marker.label}-${marker.position}`}
                    label={marker.label}
                    stroke="#888"
                    strokeDasharray="4 4"
                    x={marker.position}
                  />
                ))}
                {fermiEnergy != null && !shiftToFermi ? (
                  <ReferenceLine
                    label="E_F"
                    stroke="#c44"
                    strokeDasharray="6 3"
                    y={fermiEnergy}
                  />
                ) : null}
              </LineChart>
            </ResponsiveContainer>
          </div>

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
