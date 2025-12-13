/**
 * CalculationAnalysisPanel - Shows analysis (SCF/DOS/Bands) for a specific calculation
 * 
 * Reuses chart components from AnalysisPanel but is fixed to a single calculation.
 */

import { useState, useCallback, useEffect } from 'react';
import { useQVClient } from '../../hooks/useQVClient';
import { ScfConvergenceChart, DosChart, BandsChart } from './AnalysisPanel';
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

type AnalysisType = 'scf' | 'dos' | 'bands';

export function CalculationAnalysisPanel({ projectRoot, calculation }: CalculationAnalysisPanelProps) {
  const qv = useQVClient();
  const [analysisType, setAnalysisType] = useState<AnalysisType>('scf');
  const [scfData, setScfData] = useState<ScfConvergenceData | null>(null);
  const [dosData, setDosData] = useState<DosData | null>(null);
  const [bandsData, setBandsData] = useState<BandStructureData | null>(null);
  const [isLoadingScf, setIsLoadingScf] = useState(false);
  const [isLoadingDos, setIsLoadingDos] = useState(false);
  const [isLoadingBands, setIsLoadingBands] = useState(false);
  const [scfStep, setScfStep] = useState<string | null>(null);
  
  // Auto-detect analysis type based on calculation's last step
  useEffect(() => {
    if (!calculation) return;
    
    const steps = (calculation as CalculationDetailResult).steps || (calculation as CalculationInfo).steps || [];
    if (steps.length === 0) return;
    
    const lastStep = steps[steps.length - 1];
    const lastStepType = lastStep.type?.toLowerCase() || '';
    
    if (lastStepType === 'dos') {
      setAnalysisType('dos');
    } else if (lastStepType === 'bands' || lastStepType === 'bands_pw') {
      setAnalysisType('bands');
    } else {
      setAnalysisType('scf');
      // Find first SCF step for SCF analysis
      const scfStepEntry = steps.find((s: any) => s.type?.toLowerCase() === 'scf');
      if (scfStepEntry) {
        setScfStep(scfStepEntry.id);
      }
    }
  }, [calculation]);
  
  // Load SCF data
  const loadScf = useCallback(async () => {
    if (!calculation || !scfStep) return;
    
    setIsLoadingScf(true);
    try {
      const normalizedRoot = normalizeProjectRoot(projectRoot);
      if (!normalizedRoot) return;
      
      const response = await qv.call('get_scf_convergence', {
        project_root: normalizedRoot,
        calculation: calculation.slug || calculation.name,
        step: scfStep,
      });
      
      if (response.ok && response.data) {
        setScfData(response.data as ScfConvergenceData);
      } else {
        setScfData(null);
      }
    } catch (e) {
      console.error('Failed to load SCF data', e);
      setScfData(null);
    } finally {
      setIsLoadingScf(false);
    }
  }, [qv, projectRoot, calculation, scfStep]);
  
  // Load DOS data
  const loadDos = useCallback(async () => {
    if (!calculation) return;
    
    setIsLoadingDos(true);
    try {
      const normalizedRoot = normalizeProjectRoot(projectRoot);
      if (!normalizedRoot) return;
      
      const response = await qv.call('get_dos_data', {
        project_root: normalizedRoot,
        calculation: calculation.slug || calculation.name,
      });
      
      if (response.ok && response.data) {
        setDosData(response.data as DosData);
      } else {
        setDosData(null);
      }
    } catch (e) {
      console.error('Failed to load DOS data', e);
      setDosData(null);
    } finally {
      setIsLoadingDos(false);
    }
  }, [qv, projectRoot, calculation]);
  
  // Load Bands data
  const loadBands = useCallback(async () => {
    if (!calculation) return;
    
    setIsLoadingBands(true);
    try {
      const normalizedRoot = normalizeProjectRoot(projectRoot);
      if (!normalizedRoot) return;
      
      const response = await qv.call('get_band_structure_data', {
        project_root: normalizedRoot,
        calculation: calculation.slug || calculation.name,
      });
      
      if (response.ok && response.data) {
        setBandsData(response.data as BandStructureData);
      } else {
        setBandsData(null);
      }
    } catch (e) {
      console.error('Failed to load bands data', e);
      setBandsData(null);
    } finally {
      setIsLoadingBands(false);
    }
  }, [qv, projectRoot, calculation]);
  
  // Auto-load data when analysis type changes
  useEffect(() => {
    if (!calculation) return;
    
    if (analysisType === 'scf' && scfStep) {
      loadScf();
    } else if (analysisType === 'dos') {
      loadDos();
    } else if (analysisType === 'bands') {
      loadBands();
    }
  }, [analysisType, calculation, scfStep, loadScf, loadDos, loadBands]);
  
  if (!calculation) {
    return (
      <div className="calculation-analysis-panel calculation-analysis-panel--empty">
        <p>No calculation selected</p>
      </div>
    );
  }
  
  // Get available steps for SCF step selection
  const steps = (calculation as CalculationDetailResult).steps || (calculation as CalculationInfo).steps || [];
  const scfSteps = steps.filter((s: any) => s.type?.toLowerCase() === 'scf');
  
  return (
    <div className="calculation-analysis-panel" data-testid="qv-calc-analysis-panel">
      <div className="calculation-analysis-panel__header">
        <h3>Analysis: {calculation.name}</h3>
        <div className="calculation-analysis-panel__type-selector">
          <button
            className={`calculation-analysis-panel__type-btn ${analysisType === 'scf' ? 'calculation-analysis-panel__type-btn--active' : ''}`}
            onClick={() => setAnalysisType('scf')}
            disabled={scfSteps.length === 0}
          >
            SCF
          </button>
          <button
            className={`calculation-analysis-panel__type-btn ${analysisType === 'dos' ? 'calculation-analysis-panel__type-btn--active' : ''}`}
            onClick={() => setAnalysisType('dos')}
          >
            DOS
          </button>
          <button
            className={`calculation-analysis-panel__type-btn ${analysisType === 'bands' ? 'calculation-analysis-panel__type-btn--active' : ''}`}
            onClick={() => setAnalysisType('bands')}
          >
            Bands
          </button>
        </div>
      </div>
      
      {/* SCF Step Selector */}
      {analysisType === 'scf' && scfSteps.length > 1 && (
        <div className="calculation-analysis-panel__step-selector">
          <label>SCF Step:</label>
          <select
            value={scfStep || ''}
            onChange={(e) => setScfStep(e.target.value)}
          >
            {scfSteps.map((step: any) => (
              <option key={step.id || step.step_id} value={step.id || step.step_id}>
                {step.name || step.type} ({step.id?.slice(0, 8) || step.step_id?.slice(0, 8)})
              </option>
            ))}
          </select>
        </div>
      )}
      
      <div className="calculation-analysis-panel__content">
        {analysisType === 'scf' && (
          <ScfConvergenceChart data={scfData} isLoading={isLoadingScf} />
        )}
        {analysisType === 'dos' && (
          <DosChart data={dosData} isLoading={isLoadingDos} />
        )}
        {analysisType === 'bands' && (
          <BandsChart data={bandsData} isLoading={isLoadingBands} />
        )}
      </div>
    </div>
  );
}

