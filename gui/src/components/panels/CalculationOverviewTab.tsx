/**
 * CalculationOverviewTab - Overview & Steps tab content
 * 
 * Shows calculation overview and steps list in left pane,
 * StepDetailPanel in right pane (when step is selected).
 * 
 * Supports two modes:
 * - Overview mode: Full calculation overview with step list
 * - Step Focus mode: Compact step list on left, StepDetailPanel as main workspace on right
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { CalculationDetailPanel } from './CalculationListPanel';
import { StepDetailPanel } from './StepDetailPanel';
import { ResizablePane, type ResizablePaneRef } from '../layout/ResizablePane';
import { normalizeProjectRoot } from '../../utils/pathUtils';
import type { CalculationInfo, CalculationDetailResult, StructureInfo } from '../../types/qv';
import './CalculationOverviewTab.css';

interface CalculationOverviewTabProps {
  calculationSummary: CalculationInfo | null;
  calculationDetail: CalculationDetailResult | null;
  projectRoot: string;
  structures?: StructureInfo[];
  selectedStepId: string | null;
  onSelectStep: (stepId: string) => void;
  onRunCalculation: (calculation: CalculationInfo, runMode?: 'incremental' | 'full') => void;
  onDeleteStep: (stepId: string) => void;
  onGoToJobs?: () => void;
  onCalculationUpdated?: () => void;
  onCalculationDetailUpdated?: (detail: CalculationDetailResult) => void;
}

export function CalculationOverviewTab({
  calculationSummary,
  calculationDetail,
  projectRoot,
  structures,
  selectedStepId,
  onSelectStep,
  onRunCalculation,
  onDeleteStep,
  onGoToJobs,
  onCalculationUpdated,
  onCalculationDetailUpdated,
}: CalculationOverviewTabProps) {
  // Note: Auto-switch to Run & Logs tab is handled in App.tsx's handleRunCalculation

  // Step Focus mode state
  // When a step is selected, enter focus mode (compact step list + expanded StepDetailPanel)
  const [stepFocused, setStepFocused] = useState(false);
  
  // Ref for ResizablePane to control width
  const stepListPaneRef = useRef<ResizablePaneRef>(null);
  
  // Store overview width separately from focus width
  const overviewWidthRef = useRef<number | null>(null);
  const hasAutoShrunkRef = useRef(false);

  // Compute step index and count for breadcrumb
  const steps = calculationDetail?.steps ?? [];
  const selectedStep = selectedStepId ? steps.find(step => step.ulid === selectedStepId) : null;
  const stepIndex = selectedStep ? steps.findIndex(step => step.ulid === selectedStepId) : -1;
  const stepCount = steps.length;
  const calculationName = calculationDetail?.name || calculationSummary?.name || null;

  // Handle step selection - enter focus mode when step is clicked
  const handleSelectStep = useCallback((stepId: string) => {
    if (stepId === selectedStepId && stepFocused) {
      // Toggle: if clicking the already selected step in focus mode, exit focus mode
      setStepFocused(false);
      onSelectStep('');
    } else if (stepId) {
      // Enter focus mode when selecting a step
      onSelectStep(stepId);
      setStepFocused(true);
    } else {
      // Clear selection and exit focus mode
      setStepFocused(false);
      onSelectStep('');
    }
  }, [selectedStepId, stepFocused, onSelectStep]);

  // Handle exiting focus mode
  const handleExitFocus = useCallback(() => {
    setStepFocused(false);
    onSelectStep('');
  }, [onSelectStep]);

  // Update focus mode when selectedStepId changes externally (e.g., cleared from parent)
  useEffect(() => {
    if (!selectedStepId && stepFocused) {
      setStepFocused(false);
    } else if (selectedStepId && !stepFocused) {
      // If step is selected but we're not in focus mode, enter focus mode
      setStepFocused(true);
    }
  }, [selectedStepId, stepFocused]);
  
  // Auto-shrink step list panel when entering step detail view
  useEffect(() => {
    if (stepFocused && stepListPaneRef.current && !hasAutoShrunkRef.current) {
      // Save current width before shrinking (if we have it)
      const currentWidth = stepListPaneRef.current.getWidth();
      if (currentWidth > 240) {
        overviewWidthRef.current = currentWidth;
      }
      // Auto-shrink to compact width (240px)
      stepListPaneRef.current.setWidth(240);
      hasAutoShrunkRef.current = true;
    } else if (!stepFocused && stepListPaneRef.current && hasAutoShrunkRef.current) {
      // Restore previous width when leaving step detail view
      if (overviewWidthRef.current !== null && overviewWidthRef.current > 240) {
        stepListPaneRef.current.setWidth(overviewWidthRef.current);
      }
      hasAutoShrunkRef.current = false;
      overviewWidthRef.current = null;
    }
  }, [stepFocused]);

  // Compute step YAML absolute path for reveal button
  const calculationAbsolutePath = calculationDetail?.absolute_path || calculationSummary?.absolute_path || null;
  let stepYamlAbsolutePath: string | null = null;
  if (selectedStep && calculationAbsolutePath && selectedStep.step_file) {
    try {
      // Use Node.js path module (available in Electron)
      const path = (window as any).require?.('path');
      if (path) {
        const stepYamlFullPath = path.join(calculationAbsolutePath, selectedStep.step_file);
        stepYamlAbsolutePath = path.dirname(stepYamlFullPath);
      }
    } catch (e) {
      console.warn('[CalculationOverviewTab] Failed to compute step YAML path:', e);
      // Fallback to calculation directory
      stepYamlAbsolutePath = calculationAbsolutePath;
    }
  }

  // Handle background click to exit focus mode
  const handleBackgroundClick = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!stepFocused) return;
    // Only exit if clicking directly on the background container, not on child elements
    if (e.target === e.currentTarget) {
      handleExitFocus();
    }
  }, [stepFocused, handleExitFocus]);

  // Overview mode: show full calculation overview (no StepDetailPanel)
  if (!stepFocused || !selectedStepId) {
    return (
      <div className="calculation-overview-tab calculation-overview-tab--overview" data-testid="qv-calc-overview-tab">
        <div className="calculation-overview-tab__overview-full calculation-overview-tab__scroll-container" data-testid="qv-calc-overview-panel">
          <CalculationDetailPanel
            calculationSummary={calculationSummary}
            calculationDetail={calculationDetail}
            projectRoot={projectRoot}
            structures={structures}
            onClose={undefined} // No close button in tab view
            onRunCalculation={onRunCalculation}
            onSelectStep={handleSelectStep}
            onDeleteStep={onDeleteStep}
            onGoToJobs={onGoToJobs}
            onCalculationUpdated={onCalculationUpdated}
            onCalculationDetailUpdated={onCalculationDetailUpdated}
            isFocusMode={false}
          />
        </div>
      </div>
    );
  }

  // Step Focus mode: compact step list on left, StepDetailPanel on right
  const calculation = calculationDetail || calculationSummary;
  
  return (
    <div 
      className="calculation-overview-tab calculation-overview-tab--focus"
      onClick={handleBackgroundClick}
      data-testid="qv-calc-overview-tab-focus"
    >
      {/* Two-column layout: step list + step detail */}
      <div className="calculation-overview-tab__focus-content">
        {/* Left Column: Compact Step List */}
        <div onClick={(e) => e.stopPropagation()}>
          <ResizablePane
            ref={stepListPaneRef}
            defaultWidth={240}
            minWidth={200}
            maxWidth={400}
            storageKey="qv-step-focus-list-width"
            className="calculation-overview-tab__focus-list"
            collapsedWidth={240}
          >
            <CompactStepList
            calculation={calculation}
            steps={steps}
            selectedStepId={selectedStepId}
            stepIndex={stepIndex}
            stepCount={stepCount}
            structures={structures}
            projectRoot={projectRoot}
            onSelectStep={handleSelectStep}
            onExitFocus={handleExitFocus}
            onRunCalculation={calculation && onRunCalculation ? () => onRunCalculation(calculation, 'incremental') : undefined}
            onAddStep={onCalculationUpdated}
            onImportStep={onCalculationUpdated}
            onReorder={onCalculationUpdated}
          />
          </ResizablePane>
        </div>
        
        {/* Right Column: StepDetailPanel as main workspace */}
        <div 
          className="calculation-overview-tab__focus-detail calculation-overview-tab__scroll-container"
          onClick={(e) => e.stopPropagation()} // Prevent background click when clicking on StepDetailPanel
        >
            <StepDetailPanel
              projectRoot={projectRoot}
              selectedCalculation={calculationDetail}
              selectedStepId={selectedStepId}
              calculationName={calculationName}
              stepIndex={stepIndex >= 0 ? stepIndex : undefined}
              stepCount={stepCount > 0 ? stepCount : undefined}
              isFocusMode={true}
              calculationAbsolutePath={calculationAbsolutePath}
              stepYamlAbsolutePath={stepYamlAbsolutePath}
              onClose={handleExitFocus}
              onRunStep={(result) => {
                console.log('[CalculationOverviewTab] Step run submitted', result);
              }}
              onStepDeleted={(stepId) => {
                onDeleteStep(stepId);
                // Exit focus mode if the deleted step was the selected one
                if (stepId === selectedStepId) {
                  handleExitFocus();
                }
              }}
            />
        </div>
      </div>
    </div>
  );
}

// Compact Step List Component for Focus Mode
interface CompactStepListProps {
  calculation: CalculationInfo | CalculationDetailResult | null;
  steps: Array<{ ulid: string; slug: string; step_type_gen: string; step_type_spec: string; step_file: string }>;
  selectedStepId: string | null;
  stepIndex: number;
  stepCount: number;
  structures?: StructureInfo[];
  projectRoot: string;
  onSelectStep: (stepId: string) => void;
  onExitFocus: () => void;
  onRunCalculation?: (calculation: CalculationInfo, runMode?: 'incremental' | 'full') => void;
  onAddStep?: () => void;
  onImportStep?: () => void;
  onReorder?: () => void;
}

function CompactStepList({
  calculation,
  steps,
  selectedStepId,
  stepIndex,
  stepCount,
  structures: _structures,
  projectRoot,
  onSelectStep,
  onExitFocus,
  onRunCalculation,
  onAddStep,
  onImportStep,
  onReorder: _onReorder,
}: CompactStepListProps) {
  const [showAddStep, setShowAddStep] = useState(false);
  const [newStepType, setNewStepType] = useState('');
  const [newStepName, setNewStepName] = useState('');
  const [isAddingStep, setIsAddingStep] = useState(false);
  const [isImportingStep, setIsImportingStep] = useState(false);

  const handleAddStep = useCallback(async () => {
    if (!window.qv || !calculation || !newStepType) return;
    
    setIsAddingStep(true);
    try {
      const normalizedProjectRoot = projectRoot ? normalizeProjectRoot(projectRoot) : null;
      if (!normalizedProjectRoot) {
        throw new Error('Project root is required');
      }

      const response = await window.qv.request('add_step', {
        project_root: normalizedProjectRoot,
        calculation: calculation.slug,
        step_type_gen: newStepType,
        step_name: newStepName || undefined,
      });

      if (response.ok) {
        setShowAddStep(false);
        setNewStepType('');
        setNewStepName('');
        onAddStep?.();
      } else {
        alert(`Failed to add step: ${response.error?.message || 'Unknown error'}`);
      }
    } catch (e) {
      alert(`Error: ${e instanceof Error ? e.message : 'Unknown error'}`);
    } finally {
      setIsAddingStep(false);
    }
  }, [calculation, projectRoot, newStepType, newStepName, onAddStep]);

  const handleImportStep = useCallback(async () => {
    if (!window.qv || !calculation || isImportingStep) return;
    
    setIsImportingStep(true);
    try {
      const inputFile = await window.qv.openFile({
        title: 'Import QE Input File',
        filters: [
          { name: 'QE Input Files', extensions: ['in'] },
          { name: 'All Files', extensions: ['*'] },
        ],
      });

      if (!inputFile) {
        setIsImportingStep(false);
        return;
      }

      const normalizedProjectRoot = projectRoot ? normalizeProjectRoot(projectRoot) : null;
      if (!normalizedProjectRoot) {
        throw new Error('Project root is required');
      }

      const response = await window.qv.request('import_step', {
        project_root: normalizedProjectRoot,
        calculation: calculation.slug,
        input_file: inputFile,
      });

      if (response.ok) {
        onImportStep?.();
      } else {
        alert(`Failed to import step: ${response.error?.message || 'Unknown error'}`);
      }
    } catch (e) {
      alert(`Error: ${e instanceof Error ? e.message : 'Unknown error'}`);
    } finally {
      setIsImportingStep(false);
    }
  }, [calculation, projectRoot, isImportingStep, onImportStep]);


  if (!calculation) {
    return (
      <div className="compact-step-list">
        <div className="compact-step-list__empty">No calculation selected</div>
      </div>
    );
  }

  return (
    <div className="compact-step-list" data-testid="qv-compact-step-list">
      {/* Back to overview button */}
      <div className="compact-step-list__back">
        <button
          className="compact-step-list__back-btn"
          onClick={(e) => {
            e.stopPropagation(); // Prevent background click handler from firing
            onExitFocus();
          }}
          title="Back to overview"
          data-testid="qv-btn-back-to-overview"
        >
          ← Back to overview
        </button>
      </div>

      {/* Run Calculation button */}
      {onRunCalculation && calculation && (
        <div className="compact-step-list__run-calculation">
          <button
            className="compact-step-list__run-calculation-btn"
            onClick={(e) => {
              e.stopPropagation(); // Prevent background click handler from firing
              onRunCalculation(calculation, 'incremental');
            }}
            title="Run all steps in this calculation"
            data-testid="qv-btn-run-calculation-focus"
          >
            Run Calculation
          </button>
        </div>
      )}

      {/* Header with label and icon buttons */}
      <div className="compact-step-list__header">
        <div className="compact-step-list__header-left">
          <span className="compact-step-list__label">Steps</span>
          {selectedStepId && stepIndex >= 0 && stepCount > 0 && (
            <span className="compact-step-list__count">
              Step {stepIndex + 1} of {stepCount}
            </span>
          )}
        </div>
        <div className="compact-step-list__header-actions">
          <button
            className="compact-step-list__icon-btn"
            onClick={(e) => {
              e.stopPropagation(); // Prevent background click handler from firing
              setShowAddStep(!showAddStep);
            }}
            title="Add step"
          >
            ➕
          </button>
          <button
            className="compact-step-list__icon-btn"
            onClick={(e) => {
              e.stopPropagation(); // Prevent background click handler from firing
              // Reorder functionality not yet implemented in compact step list
            }}
            disabled={steps.length < 2}
            title="Reorder steps"
          >
            ↕️
          </button>
          <button
            className="compact-step-list__icon-btn"
            onClick={(e) => {
              e.stopPropagation(); // Prevent background click handler from firing
              handleImportStep();
            }}
            disabled={isImportingStep}
            title="Import QE input"
          >
            {isImportingStep ? '⟳' : '📥'}
          </button>
        </div>
      </div>

      {/* Add Step Form */}
      {showAddStep && (
        <div className="compact-step-list__add-form">
          <select
            value={newStepType}
            onChange={(e) => setNewStepType(e.target.value)}
            className="compact-step-list__type-select"
          >
            <option value="">Select step type...</option>
            <option value="scf">SCF</option>
            <option value="nscf">NSCF</option>
            <option value="relax">Relax</option>
            <option value="vc-relax">VC-Relax</option>
            <option value="bands_pw">Bands (PW)</option>
            <option value="bands">Bands</option>
            <option value="dos">DOS</option>
          </select>
          <input
            type="text"
            value={newStepName}
            onChange={(e) => setNewStepName(e.target.value)}
            placeholder="Step name (optional)"
            className="compact-step-list__name-input"
          />
          <div className="compact-step-list__add-actions">
            <button
              onClick={handleAddStep}
              disabled={!newStepType || isAddingStep}
              className="compact-step-list__add-btn"
            >
              {isAddingStep ? 'Adding...' : 'Add'}
            </button>
            <button
              onClick={() => {
                setShowAddStep(false);
                setNewStepType('');
                setNewStepName('');
              }}
              className="compact-step-list__cancel-btn"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Compact step list */}
      <div className="compact-step-list__steps">
        {steps.map((step, idx) => (
          <button
            key={step.ulid}
            className={`compact-step-list__step-item ${
              selectedStepId === step.ulid ? 'compact-step-list__step-item--selected' : ''
            }`}
            onClick={(e) => {
              e.stopPropagation(); // Prevent background click handler from firing
              onSelectStep(step.ulid);
            }}
            title={step.step_file ? `${step.step_type_gen} - ${step.step_file}` : `${step.step_type_gen} - ${step.ulid.substring(0, 8)}`}
            aria-label={step.step_file ? `Step ${idx + 1}: ${step.step_type_gen} (${step.step_file})` : `Step ${idx + 1}: ${step.step_type_gen}`}
          >
            <span className="compact-step-list__step-number">{idx + 1}</span>
            <span className="compact-step-list__step-type">{step.step_type_gen}</span>
          </button>
        ))}
      </div>

      {/* Footer: Structure selector or reveal button */}
      <div className="compact-step-list__footer">
        {calculation.absolute_path && (
          <button
            className="compact-step-list__reveal-btn"
            onClick={() => window.qv?.revealPath?.(calculation.absolute_path!)}
            title="Reveal calculation folder in Finder/Explorer"
          >
            📂
          </button>
        )}
      </div>
    </div>
  );
}


