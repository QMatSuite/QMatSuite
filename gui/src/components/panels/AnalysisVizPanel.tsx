import { useCallback, useMemo, useState } from 'react';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import type { PrimitiveBundleData } from '../../types/qv';

interface AnalysisVizPanelProps {
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

/** Extract unique element prefixes from PDOS series names like "Ti_1 3d" -> "Ti" */
function extractElementGroups(seriesNames: string[]): string[] {
  const elements = new Set<string>();
  for (const name of seriesNames) {
    // Match pattern like "Ti_1 3d" or "atom_0 orb_1"
    const match = name.match(/^([A-Za-z]+)/);
    if (match) {
      elements.add(match[1]);
    }
  }
  return Array.from(elements);
}

export function AnalysisVizPanel({
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
}: AnalysisVizPanelProps) {
  const [showPdos, setShowPdos] = useState(true);
  const [hiddenElements, setHiddenElements] = useState<Set<string>>(new Set());

  const isDos = selectedObjectType === 'dos';
  const isConvergence = selectedObjectType === 'convergence';
  const isField3d = selectedObjectType === 'field3d';
  const showFermiControl = selectedObjectType === 'bands' || selectedObjectType === 'dos';

  // Identify PDOS series (names like "Ti_1 3d") vs total DOS series
  const { totalSeriesNames, pdosSeriesNames, elementGroups } = useMemo(() => {
    if (!isDos || !bundle?.series?.length) {
      return { totalSeriesNames: [] as string[], pdosSeriesNames: [] as string[], elementGroups: [] as string[] };
    }
    const total: string[] = [];
    const pdos: string[] = [];
    for (const s of bundle.series) {
      const name = s.name ?? '';
      if (name === 'Total DOS' || name === 'DOS up' || name === 'DOS down') {
        total.push(name);
      } else {
        pdos.push(name);
      }
    }
    return { totalSeriesNames: total, pdosSeriesNames: pdos, elementGroups: extractElementGroups(pdos) };
  }, [bundle?.series, isDos]);

  const hasPdos = pdosSeriesNames.length > 0;

  const toggleElement = useCallback((element: string) => {
    setHiddenElements((prev) => {
      const next = new Set(prev);
      if (next.has(element)) {
        next.delete(element);
      } else {
        next.add(element);
      }
      return next;
    });
  }, []);

  // Filter traces based on PDOS visibility + element filter
  const visibleTraces = useMemo(() => {
    if (!bundle?.series?.length) return [] as string[];
    const all = bundle.series.map((s, i) => s.name ?? `series_${i + 1}`);
    if (!isDos || !hasPdos) return all;

    return all.filter((name) => {
      // Always show total DOS
      if (totalSeriesNames.includes(name)) return true;
      // If PDOS hidden, skip PDOS series
      if (!showPdos) return false;
      // Filter by element
      const match = name.match(/^([A-Za-z]+)/);
      if (match && hiddenElements.has(match[1])) return false;
      return true;
    });
  }, [bundle?.series, isDos, hasPdos, showPdos, hiddenElements, totalSeriesNames]);

  const chartData = useMemo(() => {
    if (!bundle?.series?.length) {
      return [];
    }
    const primary = bundle.series[0];
    const maxLength = Math.max(...bundle.series.map((series) => series.y.length));
    return Array.from({ length: maxLength }, (_, index) => {
      const row: Record<string, number | null> = {
        x: primary.x[index] ?? index,
      };
      bundle.series.forEach((series, seriesIndex) => {
        const key = series.name ?? `series_${seriesIndex + 1}`;
        row[key] = series.y[index] ?? null;
      });
      return row;
    });
  }, [bundle?.series]);

  const markers = bundle?.render_meta.markers ?? [];
  const xAxisLabel = bundle?.render_meta.axis_labels?.x ?? 'x';
  const yAxisLabel = bundle?.render_meta.axis_labels?.y ?? 'y';
  const fermiEnergy = bundle?.render_meta.reference_energy ?? null;
  const kpathLabels = markers.map((m) => m.label).filter(Boolean).join(' \u2192 ');

  // Convergence extras
  const convergedStatus = isConvergence ? bundle?.render_meta?.extra?.converged : undefined;
  const algorithm = isConvergence ? (bundle?.render_meta?.extra?.algorithm as string) ?? '' : '';
  const nIonicSteps = isConvergence ? bundle?.render_meta?.extra?.n_ionic_steps : undefined;

  // Field3D extras
  const field3dExtra = isField3d ? bundle?.render_meta?.extra : null;

  if (availableObjectTypes.length === 0) {
    return (
      <div className="analysis-surface__placeholder" data-testid="qv-analysis-no-objects">
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
        {showFermiControl ? (
          <label className="analysis-viz__transform">
            <input
              checked={shiftToFermi}
              onChange={(event) => onShiftToFermiChange(event.target.checked)}
              type="checkbox"
            />
            Shift to Fermi level
          </label>
        ) : null}
      </div>

      {/* PDOS filter controls */}
      {isDos && hasPdos && !loading && !error && bundle ? (
        <div className="analysis-viz__pdos-controls">
          <label className="analysis-viz__transform">
            <input
              checked={showPdos}
              onChange={(e) => setShowPdos(e.target.checked)}
              type="checkbox"
            />
            Show PDOS
          </label>
          {showPdos && elementGroups.length > 1 ? (
            <div className="analysis-viz__element-filter">
              {elementGroups.map((el) => (
                <button
                  key={el}
                  className={`analysis-viz__element-btn${hiddenElements.has(el) ? ' analysis-viz__element-btn--hidden' : ''}`}
                  onClick={() => toggleElement(el)}
                  type="button"
                >
                  {el}
                </button>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}

      {loading ? <div className="analysis-surface__placeholder" data-testid="qv-analysis-loading">Loading analysis...</div> : null}
      {error ? <div className="analysis-surface__error" data-testid="qv-analysis-error">{error}</div> : null}

      {/* Field3D metadata card (no chart) */}
      {!loading && !error && bundle && isField3d ? (
        <>
          <div className="analysis-viz__field3d-card" data-testid="qv-analysis-field3d-card">
            <h4>Field3D</h4>
            {field3dExtra ? (
              <table className="analysis-viz__field3d-table">
                <tbody>
                  {field3dExtra.field_kind ? (
                    <tr><td>Kind</td><td>{String(field3dExtra.field_kind)}</td></tr>
                  ) : null}
                  {field3dExtra.grid_shape ? (
                    <tr><td>Grid</td><td>{String(field3dExtra.grid_shape)}</td></tr>
                  ) : null}
                  {field3dExtra.value_min != null ? (
                    <tr><td>Min</td><td>{Number(field3dExtra.value_min).toExponential(4)}</td></tr>
                  ) : null}
                  {field3dExtra.value_max != null ? (
                    <tr><td>Max</td><td>{Number(field3dExtra.value_max).toExponential(4)}</td></tr>
                  ) : null}
                  {field3dExtra.value_mean != null ? (
                    <tr><td>Mean</td><td>{Number(field3dExtra.value_mean).toExponential(4)}</td></tr>
                  ) : null}
                </tbody>
              </table>
            ) : <p>No field metadata available.</p>}
            <p className="analysis-viz__field3d-note">Full isosurface rendering requires Field3D extension (not yet available).</p>
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

      {/* Line chart for bands, dos, convergence, neb */}
      {!loading && !error && bundle && !isField3d ? (
        <>
          {/* Convergence info bar */}
          {isConvergence ? (
            <div className="analysis-viz__convergence-info" data-testid="qv-analysis-convergence-info">
              <span className={`analysis-viz__convergence-badge${convergedStatus ? ' analysis-viz__convergence-badge--ok' : ' analysis-viz__convergence-badge--no'}`}>
                {convergedStatus ? 'Converged' : 'Not converged'}
              </span>
              {algorithm ? <span>Algorithm: {algorithm}</span> : null}
              {nIonicSteps != null && Number(nIonicSteps) > 0 ? <span>Ionic steps: {String(nIonicSteps)}</span> : null}
            </div>
          ) : null}

          <div className="analysis-viz__info">
            {fermiEnergy != null ? (
              <span data-testid="qv-analysis-fermi">E_F = {fermiEnergy.toFixed(4)} eV</span>
            ) : null}
            {kpathLabels ? (
              <span data-testid="qv-analysis-kpath">{kpathLabels}</span>
            ) : null}
          </div>
          <div className="analysis-viz__plot" data-testid={`qv-analysis-${selectedObjectType ?? 'unknown'}-chart`}>
            <ResponsiveContainer height={420} width="100%">
              <LineChart data={chartData} margin={{ top: 18, right: 20, left: 16, bottom: 16 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="x"
                  label={{ value: xAxisLabel, position: 'insideBottom', offset: -10 }}
                  tick={{ fontSize: 11 }}
                  type="number"
                />
                <YAxis
                  label={{ angle: -90, position: 'insideLeft', value: yAxisLabel }}
                  tick={{ fontSize: 11 }}
                  type="number"
                />
                <Tooltip />
                {visibleTraces.length <= 15 ? <Legend /> : null}
                {visibleTraces.map((trace, idx) => (
                  <Line
                    dataKey={trace}
                    dot={false}
                    key={trace}
                    stroke={`hsl(${(idx * 43) % 360} 65% 45%)`}
                    strokeWidth={1.6}
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
