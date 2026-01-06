/**
 * CalculationAnalysisPanel - Step-driven analysis view for a specific calculation
 * 
 * Shows one entry per calculation step with:
 * - Text view: Step output file content (StepOutputTextViewer)
 * - Plot view: Analysis plots for supported step types (scf/dos/bands)
 * - Pin to History: Save analysis plots to project history (bands/dos)
 */

import { useState, useCallback, useEffect, useRef } from 'react';
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
// Show actual step types (no collapsing) to avoid duplicates
function getStepTypeLabel(stepType: string): string {
  const upper = stepType.toUpperCase();
  // Keep labels readable but preserve distinction between bands_pw and bands
  return upper;
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
  
  // Auto-select first step if none selected and steps are available
  useEffect(() => {
    if (!selectedStepId && steps.length > 0) {
      setSelectedStepId(steps[0].id);
    }
  }, [steps, selectedStepId]);
  
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
  
  // Check if plot is supported (based on step type and artifacts)
  const [supportsPlot, setSupportsPlot] = useState(false);
  const [artifactsCache, setArtifactsCache] = useState<Record<string, any[]>>({});
  
  useEffect(() => {
    if (!selectedStep || !qv || !calculation) {
      setSupportsPlot(false);
      return;
    }
    
    const typeLower = selectedStep.type.toLowerCase();
    const calcSelector = calculation.slug || calculation.name;
    
    // Fast path for scf/dos (always support plot if step type matches)
    if (typeLower === 'scf' || typeLower === 'dos') {
      setSupportsPlot(true);
      return;
    }
    
    // For bands: only 'bands' step (post-processing) supports plot, not 'bands_pw'
    if (typeLower === 'bands') {
      // Check artifacts to see if this step has bands data files
      const cachedArtifacts = artifactsCache[selectedStep.id];
      if (cachedArtifacts) {
        const hasBandsData = cachedArtifacts.some((a: any) => 
          a.path_relative_to_raw.endsWith('.gnu') || 
          a.path_relative_to_raw.includes('.dat.gnu')
        );
        setSupportsPlot(hasBandsData);
        return;
      }
      
      // Load artifacts if not cached
      const normalizedRoot = normalizeProjectRoot(projectRoot);
      if (!normalizedRoot) {
        setSupportsPlot(false);
        return;
      }
      
      qv.call('list_step_artifacts', {
        project_root: normalizedRoot,
        calculation: calcSelector,
        step: selectedStep.id,
      }).then((response: any) => {
        if (response.ok && response.data) {
          const artifacts = response.data.artifacts || [];
          setArtifactsCache(prev => ({ ...prev, [selectedStep.id]: artifacts }));
          const hasBandsData = artifacts.some((a: any) => 
            a.path_relative_to_raw.endsWith('.gnu') || 
            a.path_relative_to_raw.includes('.dat.gnu')
          );
          setSupportsPlot(hasBandsData);
        } else {
          setSupportsPlot(false);
        }
      }).catch(() => setSupportsPlot(false));
    } else {
      setSupportsPlot(false);
    }
  }, [selectedStep, qv, calculation, projectRoot, artifactsCache]);
  
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
          setFailedLoads(prev => {
            const next = new Set(prev);
            next.delete(stepId);
            return next;
          });
        } else {
          setScfDataMap(prev => ({ ...prev, [stepId]: null }));
          setFailedLoads(prev => new Set(prev).add(stepId));
        }
      } else if (stepTypeLower === 'dos') {
        const response = await qv.call('get_dos_data', {
          project_root: normalizedRoot,
          calculation: calcSelector,
          step: stepId,
        });
        if (response.ok && response.data) {
          setDosDataMap(prev => ({ ...prev, [stepId]: response.data as DosData }));
          setFailedLoads(prev => {
            const next = new Set(prev);
            next.delete(stepId);
            return next;
          });
        } else {
          setDosDataMap(prev => ({ ...prev, [stepId]: null }));
          setFailedLoads(prev => new Set(prev).add(stepId));
        }
      } else if (stepTypeLower === 'bands') {
        // Only load bands plot data for 'bands' step (post-processing), not 'bands_pw'
        if (process.env.NODE_ENV === 'development') {
          console.debug(`[Analysis] Calling get_band_structure_data for step=${stepId}, calculation=${calcSelector}`);
        }
        const response = await qv.call('get_band_structure_data', {
          project_root: normalizedRoot,
          calculation: calcSelector,
          step: stepId,  // Use stepId (ULID) as step selector
        });
        if (response.ok && response.data) {
          if (process.env.NODE_ENV === 'development') {
            console.debug(`[Analysis] Received bands data: n_bands=${response.data.n_bands}, n_kpoints=${response.data.n_kpoints}, n_labels=${response.data.high_symmetry_points?.length || 0}`);
          }
          setBandsDataMap(prev => ({ ...prev, [stepId]: response.data as BandStructureData }));
          // Clear failure flag on success
          setFailedLoads(prev => {
            const next = new Set(prev);
            next.delete(stepId);
            return next;
          });
        } else {
          if (process.env.NODE_ENV === 'development') {
            console.debug(`[Analysis] Failed to load bands data:`, response.error || 'Unknown error');
          }
          setBandsDataMap(prev => ({ ...prev, [stepId]: null }));
          // Mark as failed to prevent infinite retries
          setFailedLoads(prev => new Set(prev).add(stepId));
        }
      }
    } catch (e) {
      console.error(`Failed to load plot data for step ${stepId}`, e);
      // Set data to null on error and mark as failed
      if (selectedStepType === 'scf') {
        setScfDataMap(prev => ({ ...prev, [stepId]: null }));
      } else if (selectedStepType === 'dos') {
        setDosDataMap(prev => ({ ...prev, [stepId]: null }));
      } else if (selectedStepType === 'bands') {
        setBandsDataMap(prev => ({ ...prev, [stepId]: null }));
      }
      setFailedLoads(prev => new Set(prev).add(stepId));
    } finally {
      setIsLoadingMap(prev => ({ ...prev, [stepId]: false }));
    }
  }, [calculation, qv, projectRoot, selectedStepType]);
  
  // Track failed loads to prevent infinite retries
  const [failedLoads, setFailedLoads] = useState<Set<string>>(new Set());
  
  // Pin to History state
  const [pinInfo, setPinInfo] = useState<{ run_id: string | null; can_pin: boolean; reason: string | null } | null>(null);
  const [isPinning, setIsPinning] = useState(false);
  const [pinSuccess, setPinSuccess] = useState<string | null>(null);
  const plotContainerRef = useRef<HTMLDivElement>(null);
  
  // Load plot data when switching to plot view
  useEffect(() => {
    // Only proceed if we're in plot mode and have a selected step
    if (!selectedStepId || viewMode !== 'plot' || !selectedStep) {
      return;
    }
    
    const stepId = selectedStepId;
    const stepType = selectedStep.type;
    const stepTypeLower = stepType.toLowerCase();
    
    // For bands, we need to wait for supportsPlot to be determined
    // For scf/dos, supportsPlot is true immediately if step type matches
    if (stepTypeLower === 'bands' && !supportsPlot) {
      // Wait for supportsPlot to be determined (async artifacts check)
      return;
    }
    
    // If plot is not supported, don't try to load
    if (!supportsPlot) {
      return;
    }
    
    // Don't retry if this step has already failed to load
    if (failedLoads.has(stepId)) {
      return;
    }
    
    // Check if we already have valid data for this step
    // Distinguish between: undefined (not loaded), null (error/empty), or actual data
    let hasData = false;
    if (stepTypeLower === 'scf') {
      hasData = scfDataMap[stepId] !== undefined && scfDataMap[stepId] !== null;
    } else if (stepTypeLower === 'dos') {
      hasData = dosDataMap[stepId] !== undefined && dosDataMap[stepId] !== null;
    } else if (stepTypeLower === 'bands') {
      hasData = bandsDataMap[stepId] !== undefined && bandsDataMap[stepId] !== null;
    }
    
    // Load data if we don't have it and we're not already loading
    if (!hasData && !isLoadingMap[stepId]) {
      if (process.env.NODE_ENV === 'development') {
        console.debug(`[Analysis] Loading ${stepTypeLower} plot data for step=${stepId}`);
      }
      loadPlotData(stepId, stepType);
    }
  }, [selectedStepId, viewMode, supportsPlot, selectedStep, scfDataMap, dosDataMap, bandsDataMap, isLoadingMap, loadPlotData, failedLoads]);
  
  // Fetch pin info for selected step when in plot mode (bands/dos only)
  useEffect(() => {
    if (!selectedStepId || viewMode !== 'plot' || !qv) {
      setPinInfo(null);
      return;
    }
    
    const stepTypeLower = selectedStepType.toLowerCase();
    // Only bands and dos support pinning
    if (stepTypeLower !== 'bands' && stepTypeLower !== 'dos') {
      setPinInfo(null);
      return;
    }
    
    const normalizedRoot = normalizeProjectRoot(projectRoot);
    if (!normalizedRoot) {
      setPinInfo(null);
      return;
    }
    
    // Check if this step can be pinned
    qv.call('get_latest_run_for_step', {
      project_root: normalizedRoot,
      step_id: selectedStepId,
    }).then((response: any) => {
      if (response.ok && response.data) {
        setPinInfo({
          run_id: response.data.run_id,
          can_pin: response.data.can_pin,
          reason: response.data.reason,
        });
      } else {
        setPinInfo({ run_id: null, can_pin: false, reason: 'Failed to check pin status' });
      }
    }).catch(() => {
      setPinInfo({ run_id: null, can_pin: false, reason: 'Error checking pin status' });
    });
  }, [selectedStepId, viewMode, selectedStepType, qv, projectRoot]);
  
  // Clear pin success message after 3 seconds
  useEffect(() => {
    if (pinSuccess) {
      const timer = setTimeout(() => setPinSuccess(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [pinSuccess]);
  
  // Handle Pin to History click
  const handlePinToHistory = useCallback(async () => {
    if (!selectedStepId || !pinInfo?.run_id || !pinInfo?.can_pin || !qv) return;
    
    setIsPinning(true);
    setPinSuccess(null);
    
    try {
      const normalizedRoot = normalizeProjectRoot(projectRoot);
      if (!normalizedRoot) {
        throw new Error('Invalid project root');
      }
      
      const stepTypeLower = selectedStepType.toLowerCase();
      
      // Get PNG data from the plot canvas
      let pngDataBase64: string | undefined;
      if (plotContainerRef.current) {
        const canvas = plotContainerRef.current.querySelector('canvas');
        if (canvas) {
          const dataUrl = canvas.toDataURL('image/png');
          // Remove "data:image/png;base64," prefix
          pngDataBase64 = dataUrl.replace(/^data:image\/png;base64,/, '');
        }
      }
      
      // Get JSON payload (the raw plot data)
      let jsonPayload: Record<string, unknown> | undefined;
      if (stepTypeLower === 'dos') {
        jsonPayload = dosDataMap[selectedStepId] as unknown as Record<string, unknown>;
      } else if (stepTypeLower === 'bands') {
        jsonPayload = bandsDataMap[selectedStepId] as unknown as Record<string, unknown>;
      }
      
      const response = await qv.call('pin_analysis_to_history', {
        project_root: normalizedRoot,
        run_id: pinInfo.run_id,
        step_id: selectedStepId,
        analysis_kind: stepTypeLower,
        png_data_base64: pngDataBase64,
        json_payload: jsonPayload,
      });
      
      if (response.ok && response.data?.success) {
        setPinSuccess(`Pinned ${stepTypeLower.toUpperCase()} analysis to history`);
        // Update pinInfo to reflect that we've already pinned
        setPinInfo(prev => prev ? { ...prev, can_pin: false, reason: 'Already pinned' } : null);
      } else {
        const errorMsg = response.data?.error || response.error?.message || 'Failed to pin';
        console.error('[Analysis] Pin failed:', errorMsg);
        // Show error briefly but don't throw
        setPinSuccess(`⚠️ ${errorMsg}`);
      }
    } catch (e) {
      console.error('[Analysis] Pin error:', e);
      setPinSuccess(`⚠️ ${e instanceof Error ? e.message : 'Failed to pin'}`);
    } finally {
      setIsPinning(false);
    }
  }, [selectedStepId, selectedStepType, pinInfo, qv, projectRoot, dosDataMap, bandsDataMap]);
  
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
      } else if (selectedStepType === 'bands') {
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
          // Use step.id for unique testid to avoid duplicates
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
              data-testid={`qv-analysis-step-tab-${step.type.toLowerCase()}`}
              data-step-id={step.id}
              data-step-type={step.type}
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
              <div className="calculation-analysis-panel__plot-container" ref={plotContainerRef}>
                {selectedStepType === 'scf' && (
                  <ScfConvergenceChart data={plotData as ScfConvergenceData | null} isLoading={isLoading} />
                )}
                {selectedStepType === 'dos' && (
                  <DosChart data={plotData as DosData | null} isLoading={isLoading} />
                )}
                {selectedStepType === 'bands' && (
                  <BandsChart data={plotData as BandStructureData | null} isLoading={isLoading} />
                )}
                
                {/* Pin to History button - only for bands/dos */}
                {(selectedStepType === 'bands' || selectedStepType === 'dos') && pinInfo && (
                  <div className="calculation-analysis-panel__pin-bar">
                    <button
                      className={`calculation-analysis-panel__pin-button ${!pinInfo.can_pin ? 'calculation-analysis-panel__pin-button--disabled' : ''}`}
                      onClick={handlePinToHistory}
                      disabled={!pinInfo.can_pin || isPinning || !plotData}
                      title={pinInfo.can_pin ? 'Save this plot to project history' : pinInfo.reason || 'Cannot pin'}
                    >
                      {isPinning ? '📌 Pinning...' : '📌 Pin to History'}
                    </button>
                    {!pinInfo.can_pin && pinInfo.reason && (
                      <span className="calculation-analysis-panel__pin-reason" title={pinInfo.reason}>
                        {pinInfo.reason}
                      </span>
                    )}
                    {pinSuccess && (
                      <span className={`calculation-analysis-panel__pin-success ${pinSuccess.startsWith('⚠️') ? 'calculation-analysis-panel__pin-success--error' : ''}`}>
                        {pinSuccess}
                      </span>
                    )}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
