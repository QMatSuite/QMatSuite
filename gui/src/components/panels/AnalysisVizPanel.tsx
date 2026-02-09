import { useMemo } from 'react';
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
  const traces = useMemo(
    () => (bundle?.series ?? []).map((series, index) => series.name ?? `series_${index + 1}`),
    [bundle?.series],
  );

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
  const kpathLabels = markers.map((m) => m.label).filter(Boolean).join(' → ');

  if (availableObjectTypes.length === 0) {
    return (
      <div className="analysis-surface__placeholder">
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

      {loading ? <div className="analysis-surface__placeholder">Loading analysis...</div> : null}
      {error ? <div className="analysis-surface__error">{error}</div> : null}
      {!loading && !error && bundle ? (
        <>
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
                <Legend />
                {traces.map((trace, idx) => (
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
