import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import type { PrimitiveBundleData, PrimitiveGeometryFrames } from '../../types/qv';

interface TrajectoryVizPanelProps {
  availableObjectTypes: string[];
  selectedObjectType: string | null;
  onSelectObjectType: (objectType: string) => void;
  loading: boolean;
  error: string | null;
  bundle: PrimitiveBundleData | null;
  canPin: boolean;
  pinReason: string | null;
  pinMessage: string | null;
  pinning: boolean;
  onPin: () => Promise<void>;
}

export function TrajectoryVizPanel({
  availableObjectTypes,
  selectedObjectType,
  onSelectObjectType,
  loading,
  error,
  bundle,
  canPin,
  pinReason,
  pinMessage,
  pinning,
  onPin,
}: TrajectoryVizPanelProps) {
  const [currentFrame, setCurrentFrame] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [fps, setFps] = useState(5);
  const [selectedObservable, setSelectedObservable] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const extra = bundle?.render_meta?.extra ?? {};
  const trajectoryType = (extra.trajectory_type as string) ?? 'relax';
  const nFrames = (extra.n_frames as number) ?? 0;
  const nAtoms = (extra.n_atoms as number) ?? 0;

  const geoFrames = bundle?.geometry_frames as PrimitiveGeometryFrames | null | undefined;
  const frameCount = geoFrames?.frames?.length ?? nFrames;

  // Observable series names for selector
  const observableNames = useMemo(() => {
    if (!bundle?.series?.length) return [];
    return bundle.series.map((s) => s.name ?? 'Observable');
  }, [bundle?.series]);

  // Chart data for the selected observable
  const chartData = useMemo(() => {
    if (!bundle?.series?.length || selectedObservable >= bundle.series.length) return [];
    const series = bundle.series[selectedObservable];
    return series.x.map((xVal, i) => ({
      x: xVal,
      y: series.y[i] ?? null,
    }));
  }, [bundle?.series, selectedObservable]);

  const activeSeries = bundle?.series?.[selectedObservable];
  const xLabel = activeSeries?.x_label ?? 'Step';
  const yLabel = activeSeries?.y_label ?? 'Value';
  const yUnit = activeSeries?.y_unit ?? '';

  // Current frame x-position for reference line
  const currentFrameX = useMemo(() => {
    if (!activeSeries || currentFrame >= activeSeries.x.length) return null;
    return activeSeries.x[currentFrame];
  }, [activeSeries, currentFrame]);

  // Frame info text
  const frameInfo = useMemo(() => {
    if (!geoFrames?.frames?.length || currentFrame >= geoFrames.frames.length) return null;
    const frame = geoFrames.frames[currentFrame];
    const lines: string[] = [];
    lines.push(`Frame ${currentFrame + 1} / ${geoFrames.frames.length}`);
    lines.push(`Atoms: ${frame.species.length}`);
    lines.push(`Species: ${[...new Set(frame.species)].join(', ')}`);
    if (frame.cell) {
      const a = frame.cell[0];
      const b = frame.cell[1];
      const c = frame.cell[2];
      const norm = (v: number[]) => Math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2);
      lines.push(`Cell: a=${norm(a).toFixed(3)}, b=${norm(b).toFixed(3)}, c=${norm(c).toFixed(3)} A`);
    }
    // Show current observable value
    if (activeSeries && currentFrame < activeSeries.y.length) {
      const val = activeSeries.y[currentFrame];
      if (val != null) {
        lines.push(`${activeSeries.y_label}: ${val.toFixed(6)} ${yUnit}`);
      }
    }
    return lines.join('\n');
  }, [geoFrames, currentFrame, activeSeries, yUnit]);

  // Playback
  useEffect(() => {
    if (playing && frameCount > 1) {
      intervalRef.current = setInterval(() => {
        setCurrentFrame((prev) => (prev + 1) % frameCount);
      }, 1000 / fps);
    }
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [playing, fps, frameCount]);

  // Reset frame when bundle changes
  useEffect(() => {
    setCurrentFrame(0);
    setPlaying(false);
  }, [bundle]);

  const togglePlay = useCallback(() => setPlaying((p) => !p), []);

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
      </div>

      {loading ? <div className="analysis-surface__placeholder" data-testid="qv-analysis-loading">Loading analysis...</div> : null}
      {error ? <div className="analysis-surface__error" data-testid="qv-analysis-error">{error}</div> : null}

      {!loading && !error && bundle ? (
        <>
          <div className="analysis-viz__info">
            <span>Type: {trajectoryType.toUpperCase()}</span>
            <span>Frames: {frameCount}</span>
            <span>Atoms: {nAtoms}</span>
          </div>

          {/* Observable selector */}
          {observableNames.length > 1 ? (
            <div className="trajectory-viz__observable-selector">
              <label>Observable: </label>
              <select
                value={selectedObservable}
                onChange={(e) => setSelectedObservable(Number(e.target.value))}
              >
                {observableNames.map((name, i) => (
                  <option key={name} value={i}>{name}</option>
                ))}
              </select>
            </div>
          ) : null}

          {/* Observable time-series chart */}
          {chartData.length > 0 ? (
            <div className="analysis-viz__plot" data-testid={`qv-analysis-${selectedObjectType ?? 'trajectory'}-chart`}>
              <ResponsiveContainer height={300} width="100%">
                <LineChart data={chartData} margin={{ top: 12, right: 20, left: 16, bottom: 16 }}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="x"
                    label={{ value: xLabel, position: 'insideBottom', offset: -10 }}
                    tick={{ fontSize: 11 }}
                    type="number"
                  />
                  <YAxis
                    label={{ angle: -90, position: 'insideLeft', value: `${yLabel} (${yUnit})` }}
                    tick={{ fontSize: 11 }}
                    type="number"
                  />
                  <Tooltip />
                  <Line
                    dataKey="y"
                    dot={false}
                    name={observableNames[selectedObservable]}
                    stroke="hsl(210 65% 45%)"
                    strokeWidth={1.8}
                    type="linear"
                  />
                  {currentFrameX != null ? (
                    <ReferenceLine
                      stroke="#c44"
                      strokeDasharray="4 3"
                      strokeWidth={2}
                      x={currentFrameX}
                    />
                  ) : null}
                </LineChart>
              </ResponsiveContainer>
            </div>
          ) : null}

          {/* Frame controls */}
          {frameCount > 1 ? (
            <div className="trajectory-viz__frame-controls">
              <button
                className="trajectory-viz__play-btn"
                onClick={togglePlay}
                type="button"
              >
                {playing ? 'Pause' : 'Play'}
              </button>
              <input
                className="trajectory-viz__slider"
                max={frameCount - 1}
                min={0}
                onChange={(e) => {
                  setCurrentFrame(Number(e.target.value));
                  setPlaying(false);
                }}
                type="range"
                value={currentFrame}
              />
              <span className="trajectory-viz__frame-counter">
                {currentFrame + 1} / {frameCount}
              </span>
              <label className="trajectory-viz__fps-control">
                FPS:
                <input
                  max={30}
                  min={1}
                  onChange={(e) => setFps(Number(e.target.value))}
                  type="number"
                  value={fps}
                />
              </label>
            </div>
          ) : null}

          {/* Frame info */}
          {frameInfo ? (
            <div className="trajectory-viz__frame-info">
              <pre>{frameInfo}</pre>
            </div>
          ) : null}

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
