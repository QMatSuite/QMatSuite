/**
 * CalculationAnalysisPanel - Step-driven analysis view for a specific calculation
 * 
 * Shows one entry per calculation step with:
 * - Text view: Step output file content (StepOutputTextViewer)
 * - Plot view: Analysis plots for supported step types (scf/dos/bands)
 */

import { useState, useCallback, useEffect } from 'react';
import { useQVClient } from '../../hooks/useQVClient';
import { ScfConvergenceChart, DosChart, BandsChart } from './AnalysisPanel';
import { StepOutputTextViewer } from './StepOutputTextViewer';
import type { 
  CalculationInfo, 
  CalculationDetailResult,
  ScfConvergenceData,
  DosData,
  BandStructureData,
} from '../../types/qv';
import { normalizeProjectRoot } from '../../utils/pathUtils';
import './CalculationAnalysisPanel.css';

interface CalculationAnalysisPanelProps {
  projectRoot: string;
  calculation: CalculationInfo | CalculationDetailResult | null;
}

// Analysis provider registry: maps step types to plot components
type StepViewMode = 'text' | 'plot';

// Helper: Get step type label for display
function getStepTypeLabel(stepType: string): string {
  const upper = stepType.toUpperCase();
  // Map common step types to readable labels
  const labels: Record<string, string> = {
    'SCF': 'SCF',
    'NSCF': 'NSCF',
    'BANDS_PW': 'BANDS',
    'BANDS': 'BANDS',
    'DOS': 'DOS',
  };
  return labels[upper] || upper;
}

// Helper: Check if a step type supports plotting
function stepTypeSupportsPlot(stepType: string): boolean {
  const typeLower = stepType.toLowerCase();
  return typeLower === 'scf' || typeLower === 'dos' || typeLower === 'bands' || typeLower === 'bands_pw';
}

export function CalculationAnalysisPanel({ projectRoot, calculation }: CalculationAnalysisPanelProps) {
  const qv = useQVClient();
  
  // Get steps from calculation
  const steps = calculation 
    ? ((calculation as CalculationDetailResult).steps || (calculation as CalculationInfo).steps || [])
    : [];
  
  // Step selection state
  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<StepViewMode>('text');
  
  // Plot data state (keyed by step ID)
  const [scfDataMap, setScfDataMap] = useState<Record<string, ScfConvergenceData | null>>({});
  const [dosDataMap, setDosDataMap] = useState<Record<string, DosData | null>>({});
  const [bandsDataMap, setBandsDataMap] = useState<Record<string, BandStructureData | null>>({});
  
  // Loading state (keyed by step ID)
  const [isLoadingMap, setIsLoadingMap] = useState<Record<string, boolean>>({});
  
  // Auto-select first step when calculation changes
  useEffect(() => {
    if (steps.length > 0 && !selectedStepId) {
      setSelectedStepId(steps[0].id);
    } else if (steps.length === 0) {
      setSelectedStepId(null);
    } else if (selectedStepId && !steps.find(s => s.id === selectedStepId)) {
      // Selected step no longer exists, select first step
      setSelectedStepId(steps[0].id);
    }
  }, [steps, selectedStepId]);
  
  // Get selected step
  const selectedStep = steps.find(s => s.id === selectedStepId) || null;
  const selectedStepType = selectedStep?.type?.toLowerCase() || '';
  const supportsPlot = selectedStep ? stepTypeSupportsPlot(selectedStep.type) : false;
  
  // Load plot data for a step
  const loadPlotData = useCallback(async (stepId: string, stepType: string) => {
    if (!calculation || !qv) return;
    
    setIsLoadingMap(prev => ({ ...prev, [stepId]: true }));
    
    try {
      const normalizedRoot = normalizeProjectRoot(projectRoot);
      if (!normalizedRoot) return;
      
      const calcSelector = calculation.slug || calculation.name;
      const stepTypeLower = stepType.toLowerCase();
      
      if (stepTypeLower === 'scf') {
        const response = await qv.call('get_scf_convergence', {
          project_root: normalizedRoot,
          calculation: calcSelector,
          step: stepId,
        });
        if (response.ok && response.data) {
          setScfDataMap(prev => ({ ...prev, [stepId]: response.data as ScfConvergenceData }));
        } else {
          setScfDataMap(prev => ({ ...prev, [stepId]: null }));
        }
      } else if (stepTypeLower === 'dos') {
        const response = await qv.call('get_dos_data', {
          project_root: normalizedRoot,
          calculation: calcSelector,
          step: stepId,
        });
        if (response.ok && response.data) {
          setDosDataMap(prev => ({ ...prev, [stepId]: response.data as DosData }));
        } else {
          setDosDataMap(prev => ({ ...prev, [stepId]: null }));
        }
      } else if (stepTypeLower === 'bands' || stepTypeLower === 'bands_pw') {
        const response = await qv.call('get_band_structure_data', {
          project_root: normalizedRoot,
          calculation: calcSelector,
          step: stepId,
        });
        if (response.ok && response.data) {
          setBandsDataMap(prev => ({ ...prev, [stepId]: response.data as BandStructureData }));
        } else {
          setBandsDataMap(prev => ({ ...prev, [stepId]: null }));
        }
      }
    } catch (e) {
      console.error(`Failed to load plot data for step ${stepId}`, e);
      // Set data to null on error
      if (selectedStepType === 'scf') {
        setScfDataMap(prev => ({ ...prev, [stepId]: null }));
      } else if (selectedStepType === 'dos') {
        setDosDataMap(prev => ({ ...prev, [stepId]: null }));
      } else if (selectedStepType === 'bands' || selectedStepType === 'bands_pw') {
        setBandsDataMap(prev => ({ ...prev, [stepId]: null }));
      }
    } finally {
      setIsLoadingMap(prev => ({ ...prev, [stepId]: false }));
    }
  }, [calculation, qv, projectRoot, selectedStepType]);
  
  // Load plot data when switching to plot view
  useEffect(() => {
    if (selectedStepId && viewMode === 'plot' && supportsPlot && selectedStep) {
      const stepId = selectedStepId;
      const stepType = selectedStep.type;
      
      // Check if we already have data for this step
      const hasData = 
        (stepType.toLowerCase() === 'scf' && scfDataMap[stepId] !== undefined) ||
        (stepType.toLowerCase() === 'dos' && dosDataMap[stepId] !== undefined) ||
        ((stepType.toLowerCase() === 'bands' || stepType.toLowerCase() === 'bands_pw') && bandsDataMap[stepId] !== undefined);
      
      if (!hasData && !isLoadingMap[stepId]) {
        loadPlotData(stepId, stepType);
      }
    }
  }, [selectedStepId, viewMode, supportsPlot, selectedStep, scfDataMap, dosDataMap, bandsDataMap, isLoadingMap, loadPlotData]);
  
  if (!calculation) {
    return (
      <div className="calculation-analysis-panel calculation-analysis-panel--empty">
        <p>No calculation selected</p>
      </div>
    );
  }
  
  if (steps.length === 0) {
    return (
      <div className="calculation-analysis-panel calculation-analysis-panel--empty">
        <p>No steps in this calculation</p>
      </div>
    );
  }
  
  const calcSelector = calculation.slug || calculation.name;
  const isLoading = selectedStepId ? (isLoadingMap[selectedStepId] || false) : false;
  
  // Get plot data for selected step
  let plotData: ScfConvergenceData | DosData | BandStructureData | null = null;
  if (selectedStepId && supportsPlot) {
    if (selectedStepType === 'scf') {
      plotData = scfDataMap[selectedStepId] || null;
    } else if (selectedStepType === 'dos') {
      plotData = dosDataMap[selectedStepId] || null;
    } else if (selectedStepType === 'bands' || selectedStepType === 'bands_pw') {
      plotData = bandsDataMap[selectedStepId] || null;
    }
  }
  
  return (
    <div className="calculation-analysis-panel" data-testid="qv-calc-analysis-panel">
      <div className="calculation-analysis-panel__header">
        <h3>Analysis: {calculation.name}</h3>
      </div>
      
      {/* Step selector (pills) */}
      <div className="calculation-analysis-panel__step-tabs">
        {steps.map((step) => {
          const stepTypeLabel = getStepTypeLabel(step.type);
          const isSelected = step.id === selectedStepId;
          return (
            <button
              key={step.id}
              className={`calculation-analysis-panel__step-tab ${isSelected ? 'calculation-analysis-panel__step-tab--active' : ''}`}
              onClick={() => {
                setSelectedStepId(step.id);
                // Reset to text view when switching steps
                setViewMode('text');
              }}
              title={`${stepTypeLabel} (${step.id.slice(0, 8)}...)`}
            >
              {stepTypeLabel}
            </button>
          );
        })}
      </div>
      
      {/* View mode tabs (Text / Plot) */}
      {selectedStep && (
        <div className="calculation-analysis-panel__view-mode-tabs">
          <button
            className={`calculation-analysis-panel__view-mode-tab ${viewMode === 'text' ? 'calculation-analysis-panel__view-mode-tab--active' : ''}`}
            onClick={() => setViewMode('text')}
          >
            Text
          </button>
          {supportsPlot && (
            <button
              className={`calculation-analysis-panel__view-mode-tab ${viewMode === 'plot' ? 'calculation-analysis-panel__view-mode-tab--active' : ''}`}
              onClick={() => setViewMode('plot')}
            >
              Plot
            </button>
          )}
        </div>
      )}
      
      {/* Content area */}
      <div className="calculation-analysis-panel__content">
        {selectedStep && selectedStepId && (
          <>
            {viewMode === 'text' && (
              <StepOutputTextViewer
                projectRoot={projectRoot}
                calculation={calcSelector}
                stepId={selectedStepId}
              />
            )}
            {viewMode === 'plot' && supportsPlot && (
              <div className="calculation-analysis-panel__plot-container">
                {selectedStepType === 'scf' && (
                  <ScfConvergenceChart data={plotData as ScfConvergenceData | null} isLoading={isLoading} />
                )}
                {selectedStepType === 'dos' && (
                  <DosChart data={plotData as DosData | null} isLoading={isLoading} />
                )}
                {(selectedStepType === 'bands' || selectedStepType === 'bands_pw') && (
                  <BandsChart data={plotData as BandStructureData | null} isLoading={isLoading} />
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
