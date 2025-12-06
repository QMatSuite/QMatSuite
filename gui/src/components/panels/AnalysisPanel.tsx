/**
 * AnalysisPanel - Combined analysis views for SCF, DOS, and Band structure
 * 
 * Uses Recharts for plotting scientific data.
 */

import { useState, useMemo } from 'react';
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
} from '../../types/qv';
import './AnalysisPanel.css';

// =============================================================================
// Types
// =============================================================================

type AnalysisType = 'scf' | 'dos' | 'bands';

interface AnalysisPanelProps {
  workflows: WorkflowInfo[] | null;
  selectedWorkflow: WorkflowInfo | null;
  onSelectWorkflow: (workflow: WorkflowInfo) => void;
  onLoadScf: (workflow: WorkflowInfo, step: string) => Promise<ScfConvergenceData | null>;
  onLoadDos: (workflow: WorkflowInfo) => Promise<DosData | null>;
  onLoadBands: (workflow: WorkflowInfo) => Promise<BandStructureData | null>;
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
  isLoading?: boolean;
}

export function BandsChart({ data, isLoading }: BandsChartProps) {
  const [shiftFermi, setShiftFermi] = useState(true);
  const [energyRange, setEnergyRange] = useState<[number, number]>([-10, 10]);
  
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
  
  if (isLoading) {
    return (
      <div className="chart-container chart-container--loading">
        <div className="loading-spinner" />
        <p>Loading band structure...</p>
      </div>
    );
  }
  
  if (!data) {
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
  
  return (
    <div className="chart-container">
      <div className="chart-header">
        <h3 className="chart-title">Band Structure</h3>
        <div className="chart-info">
          <span className="info-item">{data.n_bands} bands</span>
          <span className="info-item">{data.n_kpoints} k-points</span>
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
        <label className="control-item control-item--range">
          Energy Range
          <input
            type="number"
            value={energyRange[0]}
            onChange={(e) => setEnergyRange([parseFloat(e.target.value), energyRange[1]])}
            className="range-input"
          />
          <span>to</span>
          <input
            type="number"
            value={energyRange[1]}
            onChange={(e) => setEnergyRange([energyRange[0], parseFloat(e.target.value)])}
            className="range-input"
          />
          <span>eV</span>
        </label>
      </div>
      
      <div className="chart-wrapper">
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 30 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
            <XAxis 
              dataKey="k" 
              stroke="#94a3b8"
              tickFormatter={() => ''}
              label={{ value: 'k-path', position: 'insideBottom', offset: -5, fill: '#94a3b8' }}
            />
            <YAxis 
              stroke="#6366f1"
              domain={energyRange}
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
            {data.fermi_energy_ev && (
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
            
            {/* Band lines */}
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
        {data.fermi_energy_ev && (
          <div className="stat-item">
            <span className="stat-label">Fermi Energy</span>
            <span className="stat-value">{data.fermi_energy_ev.toFixed(4)} eV</span>
          </div>
        )}
        <div className="stat-item">
          <span className="stat-label">K-path</span>
          <span className="stat-value kpath-value">
            {data.high_symmetry_points.map(pt => pt.label).join(' → ')}
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
  onSelectWorkflow,
  onLoadScf,
  onLoadDos,
  onLoadBands,
}: AnalysisPanelProps) {
  const [analysisType, setAnalysisType] = useState<AnalysisType>('scf');
  const [scfData, setScfData] = useState<ScfConvergenceData | null>(null);
  const [dosData, setDosData] = useState<DosData | null>(null);
  const [bandsData, setBandsData] = useState<BandStructureData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedStep, setSelectedStep] = useState<string>('scf');
  
  const handleLoadAnalysis = async () => {
    if (!selectedWorkflow) return;
    
    setIsLoading(true);
    try {
      if (analysisType === 'scf') {
        const data = await onLoadScf(selectedWorkflow, selectedStep);
        setScfData(data);
      } else if (analysisType === 'dos') {
        const data = await onLoadDos(selectedWorkflow);
        setDosData(data);
      } else if (analysisType === 'bands') {
        const data = await onLoadBands(selectedWorkflow);
        setBandsData(data);
      }
    } finally {
      setIsLoading(false);
    }
  };
  
  return (
    <div className="analysis-panel">
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
          onClick={handleLoadAnalysis}
          disabled={!selectedWorkflow || isLoading}
        >
          {isLoading ? 'Loading...' : `Load ${analysisType.toUpperCase()}`}
        </button>
      </div>
      
      {/* Main Chart Area */}
      <div className="analysis-content">
        {analysisType === 'scf' && <ScfConvergenceChart data={scfData} isLoading={isLoading} />}
        {analysisType === 'dos' && <DosChart data={dosData} isLoading={isLoading} />}
        {analysisType === 'bands' && <BandsChart data={bandsData} isLoading={isLoading} />}
      </div>
    </div>
  );
}

