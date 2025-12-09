/**
 * AnalysisPanel - Combined analysis views for SCF, DOS, and Band structure
 * 
 * Uses Recharts for plotting scientific data.
 */

import { useState, useMemo, useEffect, useCallback, useRef } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
  AreaChart,
  Area,
} from 'recharts';
import type { 
  ScfConvergenceData, 
  DosData, 
  BandStructureData,
  WorkflowInfo,
  AnalysisStatus,
} from '../../types/qv';
import './AnalysisPanel.css';

// =============================================================================
// Types
// =============================================================================

// Use local type for UI state, re-export from types for consistency
type AnalysisTypeUI = 'scf' | 'dos' | 'bands';

// Analysis panel state
type AnalysisState = 'idle' | 'analyzing' | 'ready' | 'error';

interface AnalysisPanelProps {
  workflows: WorkflowInfo[] | null;
  selectedWorkflow: WorkflowInfo | null;
  projectRoot: string;
  onSelectWorkflow: (workflow: WorkflowInfo) => void;
  onLoadScf: (workflow: WorkflowInfo, step: string) => Promise<ScfConvergenceData | null>;
  onLoadDos: (workflow: WorkflowInfo) => Promise<DosData | null>;
  onLoadBands: (workflow: WorkflowInfo) => Promise<BandStructureData | null>;
  autoAnalysis?: boolean;
}

// =============================================================================
// SCF Convergence Chart
// =============================================================================

interface ScfChartProps {
  data: ScfConvergenceData | null;
  isLoading?: boolean;
}

export function ScfConvergenceChart({ data, isLoading }: ScfChartProps) {
  const [showAccuracy, setShowAccuracy] = useState(true);
  
  const chartData = useMemo(() => {
    if (!data?.iterations) return [];
    return data.iterations.map((it) => ({
      iteration: it.iteration,
      energy: it.total_energy_ry,
      accuracy: it.scf_accuracy_ry,
      logAccuracy: it.scf_accuracy_ry > 0 ? Math.log10(it.scf_accuracy_ry) : -15,
    }));
  }, [data]);
  
  if (isLoading) {
    return (
      <div className="chart-container chart-container--loading">
        <div className="loading-spinner" />
        <p>Loading SCF data...</p>
      </div>
    );
  }
  
  if (!data) {
    return (
      <div className="chart-container chart-container--empty">
        <div className="chart-placeholder">
          <span className="chart-icon">📉</span>
          <h3>No SCF Data</h3>
          <p>Select a workflow and SCF step to view convergence.</p>
        </div>
      </div>
    );
  }
  
  return (
    <div className="chart-container">
      <div className="chart-header">
        <h3 className="chart-title">SCF Convergence</h3>
        <div className="chart-info">
          <span className={`status-badge ${data.converged ? 'status-badge--success' : 'status-badge--error'}`}>
            {data.converged ? '✓ Converged' : '✗ Not Converged'}
          </span>
          <span className="info-item">{data.n_iterations} iterations</span>
        </div>
      </div>
      
      <div className="chart-controls">
        <label className="control-item">
          <input
            type="checkbox"
            checked={showAccuracy}
            onChange={(e) => setShowAccuracy(e.target.checked)}
          />
          Show SCF Accuracy (log scale)
        </label>
      </div>
      
      <div className="chart-wrapper">
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis 
              dataKey="iteration" 
              stroke="#94a3b8"
              label={{ value: 'Iteration', position: 'insideBottom', offset: -5, fill: '#94a3b8' }}
            />
            <YAxis 
              yAxisId="energy"
              stroke="#6366f1"
              label={{ value: 'Energy (Ry)', angle: -90, position: 'insideLeft', fill: '#6366f1' }}
            />
            {showAccuracy && (
              <YAxis 
                yAxisId="accuracy"
                orientation="right"
                stroke="#10b981"
                label={{ value: 'log₁₀(Accuracy)', angle: 90, position: 'insideRight', fill: '#10b981' }}
              />
            )}
            <Tooltip 
              contentStyle={{ 
                background: '#1e293b', 
                border: '1px solid #334155',
                borderRadius: '6px',
              }}
              labelStyle={{ color: '#f1f5f9' }}
            />
            <Legend />
            <Line 
              yAxisId="energy"
              type="monotone" 
              dataKey="energy" 
              stroke="#6366f1" 
              strokeWidth={2}
              dot={{ fill: '#6366f1', r: 4 }}
              name="Total Energy (Ry)"
            />
            {showAccuracy && (
              <Line 
                yAxisId="accuracy"
                type="monotone" 
                dataKey="logAccuracy" 
                stroke="#10b981" 
                strokeWidth={2}
                dot={{ fill: '#10b981', r: 3 }}
                name="log₁₀(Accuracy)"
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
      
      <div className="chart-stats">
        <div className="stat-item">
          <span className="stat-label">Final Energy</span>
          <span className="stat-value">{data.total_energy_ry?.toFixed(8)} Ry</span>
        </div>
        {data.fermi_energy_ev && (
          <div className="stat-item">
            <span className="stat-label">Fermi Energy</span>
            <span className="stat-value">{data.fermi_energy_ev.toFixed(4)} eV</span>
          </div>
        )}
        <div className="stat-item">
          <span className="stat-label">Calculation Type</span>
          <span className="stat-value">{data.calculation_type}</span>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// DOS Chart
// =============================================================================

interface DosChartProps {
  data: DosData | null;
  isLoading?: boolean;
}

export function DosChart({ data, isLoading }: DosChartProps) {
  const [shiftFermi, setShiftFermi] = useState(true);
  const [showIDos, setShowIDos] = useState(false);
  
  const chartData = useMemo(() => {
    if (!data?.energies_ev) return [];
    
    const fermiShift = shiftFermi && data.fermi_energy_ev ? data.fermi_energy_ev : 0;
    
    return data.energies_ev.map((e, i) => ({
      energy: e - fermiShift,
      dos: data.dos_states_per_ev[i],
      idos: data.idos?.[i] ?? 0,
    }));
  }, [data, shiftFermi]);
  
  if (isLoading) {
    return (
      <div className="chart-container chart-container--loading">
        <div className="loading-spinner" />
        <p>Loading DOS data...</p>
      </div>
    );
  }
  
  if (!data) {
    return (
      <div className="chart-container chart-container--empty">
        <div className="chart-placeholder">
          <span className="chart-icon">📊</span>
          <h3>No DOS Data</h3>
          <p>Select a workflow with DOS calculation to view density of states.</p>
        </div>
      </div>
    );
  }
  
  return (
    <div className="chart-container">
      <div className="chart-header">
        <h3 className="chart-title">Density of States</h3>
        <div className="chart-info">
          <span className="info-item">{data.n_points} points</span>
        </div>
      </div>
      
      <div className="chart-controls">
        <label className="control-item">
          <input
            type="checkbox"
            checked={shiftFermi}
            onChange={(e) => setShiftFermi(e.target.checked)}
            disabled={!data.fermi_energy_ev}
          />
          Shift to Fermi Level
        </label>
        <label className="control-item">
          <input
            type="checkbox"
            checked={showIDos}
            onChange={(e) => setShowIDos(e.target.checked)}
          />
          Show Integrated DOS
        </label>
      </div>
      
      <div className="chart-wrapper">
        <ResponsiveContainer width="100%" height={350}>
          <AreaChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis 
              dataKey="energy" 
              stroke="#94a3b8"
              label={{ 
                value: shiftFermi ? 'E - E_F (eV)' : 'Energy (eV)', 
                position: 'insideBottom', 
                offset: -5, 
                fill: '#94a3b8' 
              }}
              domain={['auto', 'auto']}
            />
            <YAxis 
              yAxisId="dos"
              stroke="#6366f1"
              label={{ value: 'DOS (states/eV)', angle: -90, position: 'insideLeft', fill: '#6366f1' }}
            />
            {showIDos && (
              <YAxis 
                yAxisId="idos"
                orientation="right"
                stroke="#f59e0b"
                label={{ value: 'Integrated DOS', angle: 90, position: 'insideRight', fill: '#f59e0b' }}
              />
            )}
            <Tooltip 
              contentStyle={{ 
                background: '#1e293b', 
                border: '1px solid #334155',
                borderRadius: '6px',
              }}
              labelStyle={{ color: '#f1f5f9' }}
              formatter={(value: number, name: string) => [value.toFixed(4), name]}
              labelFormatter={(value: number) => `E = ${value.toFixed(3)} eV`}
            />
            <Legend />
            {data.fermi_energy_ev && (
              <ReferenceLine 
                x={0} 
                stroke="#ef4444" 
                strokeDasharray="5 5"
                label={{ value: 'E_F', fill: '#ef4444', position: 'top' }}
                yAxisId="dos"
              />
            )}
            <Area 
              yAxisId="dos"
              type="monotone" 
              dataKey="dos" 
              stroke="#6366f1" 
              fill="#6366f1"
              fillOpacity={0.3}
              strokeWidth={2}
              name="DOS"
            />
            {showIDos && (
              <Line 
                yAxisId="idos"
                type="monotone" 
                dataKey="idos" 
                stroke="#f59e0b" 
                strokeWidth={2}
                dot={false}
                name="Integrated DOS"
              />
            )}
          </AreaChart>
        </ResponsiveContainer>
      </div>
      
      <div className="chart-stats">
        {data.fermi_energy_ev && (
          <div className="stat-item">
            <span className="stat-label">Fermi Energy</span>
            <span className="stat-value">{data.fermi_energy_ev.toFixed(4)} eV</span>
          </div>
        )}
        <div className="stat-item">
          <span className="stat-label">Energy Range</span>
          <span className="stat-value">
            [{data.energy_range_ev[0].toFixed(2)}, {data.energy_range_ev[1].toFixed(2)}] eV
          </span>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Band Structure Chart
// =============================================================================

interface BandsChartProps {
  data: BandStructureData | null;
  referenceData?: BandStructureData | null;
  showReference?: boolean;
  isLoading?: boolean;
}

export function BandsChart({ data, referenceData, showReference = true, isLoading }: BandsChartProps) {
  const [shiftFermi, setShiftFermi] = useState(true);
  const [energyRange, setEnergyRange] = useState<[number, number] | null>(null);
  
  // Local input state (strings) for editing - only commits on blur/enter
  const [minInput, setMinInput] = useState<string>('');
  const [maxInput, setMaxInput] = useState<string>('');
  
  // Calculate actual data range when data changes
  const dataRange = useMemo(() => {
    if (!data?.energies_ev) return null;
    
    const fermiShift = shiftFermi && data.fermi_energy_ev ? data.fermi_energy_ev : 0;
    
    // Find min and max across all bands
    let min = Infinity;
    let max = -Infinity;
    
    data.energies_ev.forEach((bandEnergies) => {
      bandEnergies.forEach((energy) => {
        const shifted = energy - fermiShift;
        min = Math.min(min, shifted);
        max = Math.max(max, shifted);
      });
    });
    
    // Add some padding
    const padding = (max - min) * 0.1;
    return [min - padding, max + padding] as [number, number];
  }, [data, shiftFermi]);
  
  // Initialize range from data when data first loads
  useEffect(() => {
    if (dataRange && energyRange === null) {
      setEnergyRange(dataRange);
      setMinInput(dataRange[0].toFixed(2));
      setMaxInput(dataRange[1].toFixed(2));
    }
  }, [dataRange, energyRange]);
  
  // Update range and inputs when shiftFermi changes
  useEffect(() => {
    if (dataRange) {
      setEnergyRange(dataRange);
      setMinInput(dataRange[0].toFixed(2));
      setMaxInput(dataRange[1].toFixed(2));
    }
  }, [shiftFermi, dataRange]);
  
  // Sync input display when range changes externally
  useEffect(() => {
    if (energyRange) {
      setMinInput(energyRange[0].toFixed(2));
      setMaxInput(energyRange[1].toFixed(2));
    }
  }, [energyRange]);
  
  // Validate and commit min value
  const handleMinBlur = () => {
    const val = parseFloat(minInput);
    if (!isNaN(val) && energyRange) {
      if (val < energyRange[1]) {
        setEnergyRange([val, energyRange[1]]);
      } else {
        // Invalid - rollback
        setMinInput(energyRange[0].toFixed(2));
      }
    } else {
      // Invalid - rollback
      if (energyRange) {
        setMinInput(energyRange[0].toFixed(2));
      }
    }
  };
  
  // Validate and commit max value
  const handleMaxBlur = () => {
    const val = parseFloat(maxInput);
    if (!isNaN(val) && energyRange) {
      if (val > energyRange[0]) {
        setEnergyRange([energyRange[0], val]);
      } else {
        // Invalid - rollback
        setMaxInput(energyRange[1].toFixed(2));
      }
    } else {
      // Invalid - rollback
      if (energyRange) {
        setMaxInput(energyRange[1].toFixed(2));
      }
    }
  };
  
  // Handle Enter key
  const handleMinKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.currentTarget.blur();
    }
  };
  
  const handleMaxKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.currentTarget.blur();
    }
  };
  
  const chartData = useMemo(() => {
    if (!data?.k_distances || !data?.energies_ev) return [];
    
    const fermiShift = shiftFermi && data.fermi_energy_ev ? data.fermi_energy_ev : 0;
    
    // Transform to chart-friendly format
    // Each point has k_distance and energy values for each band
    return data.k_distances.map((k, kIdx) => {
      const point: { k: number; [key: string]: number } = { k };
      data.energies_ev.forEach((bandEnergies, bandIdx) => {
        point[`band${bandIdx}`] = bandEnergies[kIdx] - fermiShift;
      });
      return point;
    });
  }, [data, shiftFermi]);
  
  // Generate band lines config
  const bandLines = useMemo(() => {
    if (!data?.energies_ev) return [];
    
    // Color palette for bands
    const colors = [
      '#6366f1', '#8b5cf6', '#a855f7', '#d946ef', '#ec4899',
      '#f43f5e', '#ef4444', '#f97316', '#f59e0b', '#eab308',
      '#84cc16', '#22c55e', '#10b981', '#14b8a6', '#06b6d4',
    ];
    
    return data.energies_ev.map((_, idx) => ({
      dataKey: `band${idx}`,
      stroke: colors[idx % colors.length],
    }));
  }, [data]);
  
  // High symmetry point positions for reference lines
  const highSymLines = useMemo(() => {
    if (!data?.high_symmetry_points) return [];
    return data.high_symmetry_points.filter(pt => pt.k_distance != null);
  }, [data]);
  
  // Reference chart data (for demo comparison)
  const refChartData = useMemo(() => {
    if (!showReference || !referenceData?.k_distances || !referenceData?.energies_ev) return [];
    
    const fermiShift = shiftFermi && referenceData.fermi_energy_ev ? referenceData.fermi_energy_ev : 0;
    
    return referenceData.k_distances.map((k, kIdx) => {
      const point: { k: number; [key: string]: number } = { k };
      referenceData.energies_ev.forEach((bandEnergies, bandIdx) => {
        point[`refBand${bandIdx}`] = bandEnergies[kIdx] - fermiShift;
      });
      return point;
    });
  }, [referenceData, shiftFermi, showReference]);
  
  // Reference band lines config
  const refBandLines = useMemo(() => {
    if (!showReference || !referenceData?.energies_ev) return [];
    
    return referenceData.energies_ev.map((_, idx) => ({
      dataKey: `refBand${idx}`,
      stroke: '#9ca3af',  // Gray for reference
    }));
  }, [referenceData, showReference]);
  
  // Merged chart data: combine current and reference data
  const mergedChartData = useMemo(() => {
    // If we have current data, use it as base
    if (chartData.length > 0) {
      // Merge reference data if available
      if (refChartData.length > 0 && chartData.length === refChartData.length) {
        return chartData.map((point, idx) => ({
          ...point,
          ...refChartData[idx],
        }));
      }
      return chartData;
    }
    // Only reference data available
    return refChartData;
  }, [chartData, refChartData]);
  
  // Determine if we have any data to show
  const hasData = data !== null;
  const hasReferenceOnly = !hasData && referenceData !== null;
  
  if (isLoading) {
    return (
      <div className="chart-container chart-container--loading">
        <div className="loading-spinner" />
        <p>Loading band structure...</p>
      </div>
    );
  }
  
  if (!data && !referenceData) {
    return (
      <div className="chart-container chart-container--empty">
        <div className="chart-placeholder">
          <span className="chart-icon">📈</span>
          <h3>No Band Structure Data</h3>
          <p>Select a workflow with band calculation to view band structure.</p>
        </div>
      </div>
    );
  }
  
  // Use reference data for display when current data is not available
  const displayData = data || referenceData;
  
  return (
    <div className="chart-container" data-testid="qv-analysis-bands-chart">
      <div className="chart-header">
        <h3 className="chart-title">
          Band Structure
          {hasReferenceOnly && <span className="reference-badge"> (Reference)</span>}
        </h3>
        <div className="chart-info">
          <span className="info-item">{displayData?.n_bands} bands</span>
          <span className="info-item">{displayData?.n_kpoints} k-points</span>
          {referenceData && data && (
            <label className="reference-toggle">
              <input
                type="checkbox"
                checked={showReference}
                onChange={() => {/* handled by parent */}}
                disabled
              />
              Show reference
            </label>
          )}
        </div>
      </div>
      
      {hasReferenceOnly && (
        <div className="reference-notice">
          <span className="notice-icon">ℹ️</span>
          Showing reference results from the demo. Run the workflow to generate your own data.
        </div>
      )}
      
      <div className="chart-controls">
        <label className="control-item">
          <input
            type="checkbox"
            checked={shiftFermi}
            onChange={(e) => setShiftFermi(e.target.checked)}
            disabled={!displayData?.fermi_energy_ev}
          />
          Shift to Fermi Level
        </label>
        <label className="control-item control-item--range">
          Energy Range
          <input
            type="text"
            value={minInput}
            onChange={(e) => setMinInput(e.target.value)}
            onBlur={handleMinBlur}
            onKeyDown={handleMinKeyDown}
            className="range-input"
            placeholder="min"
          />
          <span>to</span>
          <input
            type="text"
            value={maxInput}
            onChange={(e) => setMaxInput(e.target.value)}
            onBlur={handleMaxBlur}
            onKeyDown={handleMaxKeyDown}
            className="range-input"
            placeholder="max"
          />
          <span>eV</span>
          {dataRange && (
            <button
              type="button"
              onClick={() => {
                setEnergyRange(dataRange);
                setMinInput(dataRange[0].toFixed(2));
                setMaxInput(dataRange[1].toFixed(2));
              }}
              className="range-reset-btn"
              title="Reset to auto range"
            >
              Reset
            </button>
          )}
        </label>
      </div>
      
      <div className="chart-wrapper">
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={mergedChartData} margin={{ top: 20, right: 30, left: 20, bottom: 30 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
            <XAxis 
              dataKey="k" 
              stroke="#94a3b8"
              tickFormatter={() => ''}
              label={{ value: 'k-path', position: 'insideBottom', offset: -5, fill: '#94a3b8' }}
            />
            <YAxis 
              stroke="#6366f1"
              domain={energyRange ? [energyRange[0], energyRange[1]] : (dataRange ? [dataRange[0], dataRange[1]] : ['auto', 'auto'])}
              allowDataOverflow={false}
              allowDecimals={true}
              type="number"
              label={{ 
                value: shiftFermi ? 'E - E_F (eV)' : 'Energy (eV)', 
                angle: -90, 
                position: 'insideLeft', 
                fill: '#6366f1' 
              }}
            />
            <Tooltip 
              contentStyle={{ 
                background: '#1e293b', 
                border: '1px solid #334155',
                borderRadius: '6px',
              }}
              labelStyle={{ color: '#f1f5f9' }}
              formatter={(value: number) => [value.toFixed(4) + ' eV']}
              labelFormatter={(value: number) => `k = ${value.toFixed(4)}`}
            />
            
            {/* Fermi level reference line */}
            {displayData?.fermi_energy_ev && (
              <ReferenceLine 
                y={0} 
                stroke="#ef4444" 
                strokeDasharray="5 5"
                label={{ value: 'E_F', fill: '#ef4444', position: 'right' }}
              />
            )}
            
            {/* High symmetry point lines */}
            {highSymLines.map((pt, idx) => (
              <ReferenceLine 
                key={idx}
                x={pt.k_distance!} 
                stroke="#475569" 
                strokeDasharray="3 3"
                label={{ 
                  value: pt.label, 
                  fill: '#94a3b8', 
                  position: 'bottom',
                  offset: 10,
                }}
              />
            ))}
            
            {/* Reference band lines (dashed, gray) */}
            {showReference && refBandLines.map((band, idx) => (
              <Line 
                key={`ref-${idx}`}
                type="monotone" 
                dataKey={band.dataKey} 
                stroke={band.stroke}
                strokeWidth={1}
                strokeDasharray="4 2"
                strokeOpacity={0.6}
                dot={false}
                isAnimationActive={false}
              />
            ))}
            
            {/* Current band lines (solid) */}
            {bandLines.map((band, idx) => (
              <Line 
                key={idx}
                type="monotone" 
                dataKey={band.dataKey} 
                stroke={band.stroke}
                strokeWidth={1.5}
                dot={false}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      
      <div className="chart-stats">
        {displayData?.fermi_energy_ev && (
          <div className="stat-item" data-testid="qv-analysis-fermi">
            <span className="stat-label">Fermi Energy</span>
            <span className="stat-value">{displayData.fermi_energy_ev.toFixed(4)} eV</span>
          </div>
        )}
        <div className="stat-item" data-testid="qv-analysis-kpath">
          <span className="stat-label">K-path</span>
          <span className="stat-value kpath-value">
            {displayData?.high_symmetry_points.map(pt => pt.label).join(' → ')}
          </span>
        </div>
      </div>
    </div>
  );
}

// =============================================================================
// Main Analysis Panel
// =============================================================================

export function AnalysisPanel({
  workflows,
  selectedWorkflow,
  projectRoot,
  onSelectWorkflow,
  onLoadScf,
  onLoadDos,
  onLoadBands,
  autoAnalysis = false,
  defaultAnalysis,
}: AnalysisPanelProps & { defaultAnalysis?: string | null }) {
  // Initialize analysis type from defaultAnalysis if provided
  const [analysisType, setAnalysisType] = useState<AnalysisTypeUI>(
    defaultAnalysis === 'bands' ? 'bands' : defaultAnalysis === 'dos' ? 'dos' : 'scf'
  );
  const [scfData, setScfData] = useState<ScfConvergenceData | null>(null);
  const [dosData, setDosData] = useState<DosData | null>(null);
  const [bandsData, setBandsData] = useState<BandStructureData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedStep, setSelectedStep] = useState<string>('scf');
  
  // Reference data for demo projects
  // Note: SCF and DOS reference overlay not yet implemented, using _ prefix
  const [_refScfData, setRefScfData] = useState<ScfConvergenceData | null>(null);
  const [_refDosData, setRefDosData] = useState<DosData | null>(null);
  const [refBandsData, setRefBandsData] = useState<BandStructureData | null>(null);
  const [showReference, _setShowReference] = useState(true);
  
  // Analysis pipeline state
  const [analysisState, setAnalysisState] = useState<AnalysisState>('idle');
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  
  // Track last auto-loaded workflow to prevent infinite loops
  const lastAutoLoadedRef = useRef<string | null>(null);
  
  // Update analysis type when defaultAnalysis changes (e.g., from demo project)
  useEffect(() => {
    if (defaultAnalysis) {
      const newType: AnalysisTypeUI = defaultAnalysis === 'bands' ? 'bands' : defaultAnalysis === 'dos' ? 'dos' : 'scf';
      if (newType !== analysisType) {
        setAnalysisType(newType);
      }
    }
  }, [defaultAnalysis, analysisType]);
  
  // Ensure analysis artifacts exist before loading data
  const ensureAnalysis = useCallback(async (
    workflow: WorkflowInfo, 
    type: AnalysisTypeUI,
    force: boolean = false
  ): Promise<boolean> => {
    if (!window.qv || !projectRoot) return false;
    
    setAnalysisState('analyzing');
    setAnalysisError(null);
    
    try {
      const response = await window.qv.request<AnalysisStatus>('ensure_workflow_analysis', {
        project_root: projectRoot,
        workflow: workflow.slug,
        analysis_type: type,
        force,
      });
      
      if (response.ok && response.data?.ok) {
        setAnalysisState('ready');
        return true;
      } else {
        const errorMsg = response.data?.error || response.error?.message || 'Analysis failed';
        setAnalysisError(errorMsg);
        setAnalysisState('error');
        return false;
      }
    } catch (e) {
      const errorMsg = e instanceof Error ? e.message : 'Analysis failed';
      setAnalysisError(errorMsg);
      setAnalysisState('error');
      return false;
    }
  }, [projectRoot]);
  
  // Auto-detect best analysis type based on workflow's last step
  const detectAnalysisType = useCallback((workflow: WorkflowInfo): AnalysisTypeUI => {
    if (!workflow.steps || workflow.steps.length === 0) return 'scf';
    
    // Check last step type
    const lastStep = workflow.steps[workflow.steps.length - 1];
    const stepType = lastStep.type?.toLowerCase() || '';
    
    if (stepType === 'dos' || stepType.includes('dos')) {
      return 'dos';
    } else if (stepType === 'bands' || stepType === 'bands_pw' || stepType.includes('bands')) {
      return 'bands';
    }
    
    // Also check if workflow has dos or bands steps at all
    const hasDoStep = workflow.steps.some(s => s.type?.toLowerCase() === 'dos');
    const hasBandsStep = workflow.steps.some(s => 
      s.type?.toLowerCase() === 'bands' || s.type?.toLowerCase() === 'bands_pw'
    );
    
    if (hasDoStep) return 'dos';
    if (hasBandsStep) return 'bands';
    
    return 'scf';
  }, []);
  
  // Fetch reference analysis data for demo projects
  const fetchReferenceData = useCallback(async (workflow: WorkflowInfo, type: AnalysisTypeUI) => {
    if (!window.qv || !projectRoot) return null;
    
    try {
      const response = await window.qv.request<{ data: ScfConvergenceData | DosData | BandStructureData | null; has_reference: boolean }>('get_reference_analysis', {
        project_root: projectRoot,
        workflow: workflow.slug,
        analysis_type: type,
      });
      
      if (response.ok && response.data?.has_reference && response.data?.data) {
        return response.data.data;
      }
      return null;
    } catch {
      return null;
    }
  }, [projectRoot]);
  
  const handleLoadAnalysis = useCallback(async (type?: AnalysisTypeUI, force: boolean = false) => {
    if (!selectedWorkflow) return;
    
    const typeToLoad = type || analysisType;
    setIsLoading(true);
    setAnalysisError(null);
    
    try {
      // Fetch reference data (doesn't require workflow to be run)
      const refData = await fetchReferenceData(selectedWorkflow, typeToLoad);
      if (typeToLoad === 'scf') {
        setRefScfData(refData as ScfConvergenceData | null);
      } else if (typeToLoad === 'dos') {
        setRefDosData(refData as DosData | null);
      } else if (typeToLoad === 'bands') {
        setRefBandsData(refData as BandStructureData | null);
      }
      
      // Try to ensure analysis artifacts exist
      const analysisReady = await ensureAnalysis(selectedWorkflow, typeToLoad, force);
      
      if (!analysisReady) {
        // If analysis failed but we have reference data, show reference only
        if (refData) {
          setAnalysisState('ready');
          return;
        }
        // No reference and no analysis - error state
        return;
      }
      
      // Now load the current analysis data
      if (typeToLoad === 'scf') {
        const data = await onLoadScf(selectedWorkflow, selectedStep);
        setScfData(data);
      } else if (typeToLoad === 'dos') {
        const data = await onLoadDos(selectedWorkflow);
        setDosData(data);
      } else if (typeToLoad === 'bands') {
        const data = await onLoadBands(selectedWorkflow);
        setBandsData(data);
      }
      
      setAnalysisState('ready');
    } catch (e) {
      const errorMsg = e instanceof Error ? e.message : 'Failed to load analysis';
      setAnalysisError(errorMsg);
      setAnalysisState('error');
    } finally {
      setIsLoading(false);
    }
  }, [selectedWorkflow, analysisType, selectedStep, onLoadScf, onLoadDos, onLoadBands, ensureAnalysis, fetchReferenceData]);
  
  // Auto-select analysis type and load when workflow changes
  useEffect(() => {
    if (selectedWorkflow && autoAnalysis) {
      // Only auto-load if we haven't already loaded for this workflow
      if (lastAutoLoadedRef.current !== selectedWorkflow.id) {
        const detectedType = detectAnalysisType(selectedWorkflow);
        setAnalysisType(detectedType);
        lastAutoLoadedRef.current = selectedWorkflow.id;
        
        // Reset previous data
        setScfData(null);
        setDosData(null);
        setBandsData(null);
        setAnalysisError(null);
        
        // Load the detected analysis type via the new pipeline
        handleLoadAnalysis(detectedType);
      }
    } else if (!selectedWorkflow) {
      // Reset when no workflow is selected
      lastAutoLoadedRef.current = null;
      setAnalysisState('idle');
      setAnalysisError(null);
    }
  }, [selectedWorkflow, autoAnalysis, detectAnalysisType, handleLoadAnalysis]);
  
  return (
    <div className="analysis-panel" data-testid="qv-analysis-view">
      {/* Sidebar */}
      <div className="analysis-sidebar">
        <div className="sidebar-section">
          <h3 className="sidebar-title">Analysis Type</h3>
          <div className="analysis-type-tabs">
            <button
              className={`type-tab ${analysisType === 'scf' ? 'type-tab--active' : ''}`}
              onClick={() => setAnalysisType('scf')}
            >
              📉 SCF
            </button>
            <button
              className={`type-tab ${analysisType === 'dos' ? 'type-tab--active' : ''}`}
              onClick={() => setAnalysisType('dos')}
            >
              📊 DOS
            </button>
            <button
              className={`type-tab ${analysisType === 'bands' ? 'type-tab--active' : ''}`}
              onClick={() => setAnalysisType('bands')}
            >
              📈 Bands
            </button>
          </div>
        </div>
        
        <div className="sidebar-section">
          <h3 className="sidebar-title">Workflow</h3>
          {workflows && workflows.length > 0 ? (
            <div className="workflow-select">
              {workflows.map((wf) => (
                <button
                  key={wf.id}
                  className={`workflow-option ${selectedWorkflow?.id === wf.id ? 'workflow-option--selected' : ''}`}
                  onClick={() => onSelectWorkflow(wf)}
                >
                  <span className="workflow-name">{wf.name}</span>
                  <span className="workflow-steps">{wf.n_steps} steps</span>
                </button>
              ))}
            </div>
          ) : (
            <p className="no-workflows">No workflows loaded</p>
          )}
        </div>
        
        {selectedWorkflow && analysisType === 'scf' && (
          <div className="sidebar-section">
            <h3 className="sidebar-title">Step</h3>
            <select 
              value={selectedStep}
              onChange={(e) => setSelectedStep(e.target.value)}
              className="step-select"
            >
              {selectedWorkflow.steps.map((step) => (
                <option key={step.id} value={step.id}>
                  {step.id} ({step.type})
                </option>
              ))}
            </select>
          </div>
        )}
        
        <button
          className="load-button"
          onClick={() => handleLoadAnalysis()}
          disabled={!selectedWorkflow || isLoading || analysisState === 'analyzing'}
        >
          {isLoading || analysisState === 'analyzing' ? 'Analyzing...' : `Load ${analysisType.toUpperCase()}`}
        </button>
        
        {/* Re-analyze button (force refresh) */}
        {analysisState === 'ready' && (
          <button
            className="load-button load-button--secondary"
            onClick={() => handleLoadAnalysis(undefined, true)}
            disabled={isLoading}
            title="Force re-parse analysis from QE outputs"
          >
            🔄 Re-analyze
          </button>
        )}
      </div>
      
      {/* Main Chart Area */}
      <div className="analysis-content">
        {/* Error State */}
        {analysisState === 'error' && analysisError && (
          <div className="chart-container chart-container--error">
            <div className="chart-placeholder chart-placeholder--error">
              <span className="chart-icon">⚠️</span>
              <h3>Analysis Error</h3>
              <p className="analysis-error-message">{analysisError}</p>
              <button
                className="btn btn-primary"
                onClick={() => handleLoadAnalysis(undefined, true)}
                disabled={isLoading}
              >
                Retry Analysis
              </button>
            </div>
          </div>
        )}
        
        {/* Analyzing State */}
        {analysisState === 'analyzing' && (
          <div className="chart-container chart-container--loading">
            <div className="loading-spinner" />
            <p>Analyzing workflow outputs...</p>
            <p className="analysis-hint">Parsing QE output files and generating analysis data</p>
          </div>
        )}
        
        {/* Charts */}
        {analysisState !== 'error' && analysisState !== 'analyzing' && (
          <>
            {analysisType === 'scf' && <ScfConvergenceChart data={scfData} isLoading={isLoading} />}
            {analysisType === 'dos' && <DosChart data={dosData} isLoading={isLoading} />}
            {analysisType === 'bands' && (
              <BandsChart 
                data={bandsData} 
                referenceData={refBandsData} 
                showReference={showReference}
                isLoading={isLoading} 
              />
            )}
          </>
        )}
      </div>
    </div>
  );
}

