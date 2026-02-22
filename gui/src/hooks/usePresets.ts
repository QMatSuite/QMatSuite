/**
 * React hook for preset detection and application.
 * 
 * Per Constitution Chapter 10:
 * - §10.4.1: Detector B is the sole legitimate state source
 * - §10.3.3: Apply overwrites, not merges
 * - Presets are runtime-only interpretations
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import { useQMSClient } from './useQMSClient';
import type {
  WorkflowType,
  PresetDetectionResult,
  WorkflowDetectionResult,
  StepPresetFootprint,
  ApplyPresetsToCalcResult,
  StepApplyResult,
} from '../types/qms';
import { normalizeProjectRoot } from '../utils/pathUtils';

export interface PresetState {
  [dimension: string]: string | 'Custom';
}

/** Result of applying presets - for toast/modal feedback */
export interface ApplyResult {
  success: boolean;
  stepsUpdated: number;
  stepsSkipped: number;
  stepResults: StepApplyResult[];
  dimension: string;
  value: string;
  error?: string;
}

export interface PresetsHookState {
  presets: PresetState | null;
  workflow: WorkflowType | null;
  footprints: Record<string, StepPresetFootprint> | null;
  isLoading: boolean;
  isApplying: boolean;
  error: string | null;
  /** Last apply result for toast/modal feedback */
  lastApplyResult: ApplyResult | null;
}

export interface PresetsHook extends PresetsHookState {
  /** Refresh preset detection from backend */
  refresh: () => Promise<void>;
  
  /** Apply preset to all steps in calculation (BROADCAST), returns detailed result */
  applyPreset: (dimension: string, value: string) => Promise<ApplyResult>;
  
  /** Apply multiple presets at once */
  applyPresets: (presets: Partial<PresetState>) => Promise<ApplyResult>;
  
  /** Clear the last apply result (after toast dismissed) */
  clearApplyResult: () => void;
}

/**
 * Hook for preset detection and application.
 * 
 * @example
 * function CalculationPresets({ projectRoot, calculationSlug }) {
 *   const { presets, workflow, isLoading, applyPreset } = usePresets(projectRoot, calculationSlug);
 *   
 *   if (isLoading) return <div>Loading...</div>;
 *   if (!presets) return null;
 *   
 *   return (
 *     <div>
 *       <div>Workflow: {workflow}</div>
 *       <div>Magnetism: {presets.magnetism}</div>
 *       <select onChange={(e) => applyPreset('magnetism', e.target.value)}>
 *         Options come from preset catalog
 *       </select>
 *     </div>
 *   );
 * }
 */
export function usePresets(
  projectRoot: string | null,
  calculationSlug: string | null,
): PresetsHook {
  const qms = useQMSClient();
  
  const [state, setState] = useState<PresetsHookState>({
    presets: null,
    workflow: null,
    footprints: null,
    isLoading: false,
    isApplying: false,
    error: null,
    lastApplyResult: null,
  });
  
  // Track mounted state
  const mountedRef = useRef(true);
  
  // Request sequence counter for stale response detection (Phase 8D)
  const requestSeqRef = useRef(0);
  
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);
  
  // Clear apply result (for dismissing toast)
  const clearApplyResult = useCallback(() => {
    setState(prev => ({ ...prev, lastApplyResult: null }));
  }, []);
  
  // Fetch presets, workflow, and footprints
  const refresh = useCallback(async () => {
    if (!projectRoot || !calculationSlug) {
      setState(prev => ({
        ...prev,
        presets: null,
        workflow: null,
        footprints: null,
        isLoading: false,
        error: null,
      }));
      return;
    }
    
    const normalizedRoot = normalizeProjectRoot(projectRoot);
    if (!normalizedRoot) {
      setState(prev => ({
        ...prev,
        error: 'Invalid project root',
        isLoading: false,
      }));
      return;
    }
    
    // Increment request sequence for stale response detection (Phase 8D)
    const currentSeq = ++requestSeqRef.current;
    
    if (mountedRef.current) {
      setState(prev => ({ ...prev, isLoading: true, error: null }));
    }
    
    try {
      // Fetch presets, workflow, and footprints in parallel
      const [presetsResponse, workflowResponse, footprintsResponse] = await Promise.all([
        qms.call('detect_presets', {
          project_root: normalizedRoot,
          calculation: calculationSlug,
        }),
        qms.call('detect_workflow', {
          project_root: normalizedRoot,
          calculation: calculationSlug,
        }),
        qms.call('get_step_preset_footprints', {
          project_root: normalizedRoot,
          calculation: calculationSlug,
        }),
      ]);
      
      // Check if this response is stale (newer request was issued)
      if (!mountedRef.current || currentSeq !== requestSeqRef.current) {
        return; // Ignore stale response
      }
      
      if (presetsResponse.ok && presetsResponse.data) {
        const presetData = presetsResponse.data as PresetDetectionResult;
        const workflowData = workflowResponse.ok && workflowResponse.data
          ? workflowResponse.data as WorkflowDetectionResult
          : null;
        const footprintsData = footprintsResponse.ok && footprintsResponse.data
          ? footprintsResponse.data.footprints
          : null;
        
        setState(prev => ({
          ...prev,
          presets: presetData.dimension_states,
          workflow: workflowData?.workflow || null,
          footprints: footprintsData,
          isLoading: false,
          error: null,
        }));
      } else {
        // Don't expose raw error messages to UI (e2e will catch them)
        const errorMsg = presetsResponse.error?.message || 'Failed to detect presets';
        // Log to console for debugging
        console.error('Preset detection failed:', errorMsg);
        setState(prev => ({
          ...prev,
          presets: null,
          workflow: null,
          footprints: null,
          isLoading: false,
          error: 'Presets unavailable', // User-friendly message
        }));
      }
    } catch (e) {
      // Check if stale before updating error state
      if (mountedRef.current && currentSeq === requestSeqRef.current) {
        const errorMsg = e instanceof Error ? e.message : 'Unknown error';
        // Log to console for debugging
        console.error('Preset detection error:', errorMsg);
        setState(prev => ({
          ...prev,
          isLoading: false,
          error: 'Presets unavailable', // User-friendly message
        }));
      }
    }
  }, [projectRoot, calculationSlug, qms]);
  
  // Auto-fetch on mount and when calculation changes
  useEffect(() => {
    refresh();
  }, [refresh]);
  
  // Apply single preset dimension (BROADCAST to all steps)
  const applyPreset = useCallback(async (
    dimension: string,
    value: string,
  ): Promise<ApplyResult> => {
    const errorResult: ApplyResult = {
      success: false,
      stepsUpdated: 0,
      stepsSkipped: 0,
      stepResults: [],
      dimension,
      value,
    };
    
    if (!projectRoot || !calculationSlug) {
      errorResult.error = 'No project or calculation selected';
      return errorResult;
    }
    
    const normalizedRoot = normalizeProjectRoot(projectRoot);
    if (!normalizedRoot) {
      errorResult.error = 'Invalid project root';
      return errorResult;
    }
    
    if (mountedRef.current) {
      setState(prev => ({ ...prev, isApplying: true, error: null }));
    }
    
    try {
      const presets: Record<string, string> = { [dimension]: value };
      
      const response = await qms.call('apply_presets_to_calculation', {
        project_root: normalizedRoot,
        calculation: calculationSlug,
        presets,
        validate_physics: true,
      });
      
      if (!mountedRef.current) return errorResult;
      
      if (response.ok && response.data) {
        const data = response.data as ApplyPresetsToCalcResult;
        const result: ApplyResult = {
          success: true,
          stepsUpdated: data.steps_updated,
          stepsSkipped: data.steps_skipped,
          stepResults: data.step_results,
          dimension,
          value,
        };
        
        // Update local state with new dimension states from response
        setState(prev => ({
          ...prev,
          presets: data.dimension_states,
          isApplying: false,
          error: null,
          lastApplyResult: result,
        }));
        
        // Refresh footprints after apply
        refresh();
        
        return result;
      } else {
        const errorMsg = response.error?.message || 'Failed to apply preset';
        errorResult.error = errorMsg;
        setState(prev => ({
          ...prev,
          isApplying: false,
          error: errorMsg,
          lastApplyResult: errorResult,
        }));
        return errorResult;
      }
    } catch (e) {
      const errorMsg = e instanceof Error ? e.message : 'Unknown error';
      errorResult.error = errorMsg;
      if (mountedRef.current) {
        setState(prev => ({
          ...prev,
          isApplying: false,
          error: errorMsg,
          lastApplyResult: errorResult,
        }));
      }
      return errorResult;
    }
  }, [projectRoot, calculationSlug, qms, refresh]);
  
  // Apply multiple presets at once
  const applyPresets = useCallback(async (
    presetsToApply: Partial<PresetState>,
  ): Promise<ApplyResult> => {
    const dimensions = Object.keys(presetsToApply).join(', ');
    const values = Object.values(presetsToApply).join(', ');
    const errorResult: ApplyResult = {
      success: false,
      stepsUpdated: 0,
      stepsSkipped: 0,
      stepResults: [],
      dimension: dimensions,
      value: values,
    };
    
    if (!projectRoot || !calculationSlug) {
      errorResult.error = 'No project or calculation selected';
      return errorResult;
    }
    
    const normalizedRoot = normalizeProjectRoot(projectRoot);
    if (!normalizedRoot) {
      errorResult.error = 'Invalid project root';
      return errorResult;
    }
    
    if (mountedRef.current) {
      setState(prev => ({ ...prev, isApplying: true, error: null }));
    }
    
    try {
      const response = await qms.call('apply_presets_to_calculation', {
        project_root: normalizedRoot,
        calculation: calculationSlug,
        presets: presetsToApply as Record<string, string>,
        validate_physics: true,
      });
      
      if (!mountedRef.current) return errorResult;
      
      if (response.ok && response.data) {
        const data = response.data as ApplyPresetsToCalcResult;
        const result: ApplyResult = {
          success: true,
          stepsUpdated: data.steps_updated,
          stepsSkipped: data.steps_skipped,
          stepResults: data.step_results,
          dimension: dimensions,
          value: values,
        };
        
        setState(prev => ({
          ...prev,
          presets: data.dimension_states,
          isApplying: false,
          error: null,
          lastApplyResult: result,
        }));
        
        // Refresh footprints after apply
        refresh();
        
        return result;
      } else {
        const errorMsg = response.error?.message || 'Failed to apply presets';
        errorResult.error = errorMsg;
        setState(prev => ({
          ...prev,
          isApplying: false,
          error: errorMsg,
          lastApplyResult: errorResult,
        }));
        return errorResult;
      }
    } catch (e) {
      const errorMsg = e instanceof Error ? e.message : 'Unknown error';
      errorResult.error = errorMsg;
      if (mountedRef.current) {
        setState(prev => ({
          ...prev,
          isApplying: false,
          error: errorMsg,
          lastApplyResult: errorResult,
        }));
      }
      return errorResult;
    }
  }, [projectRoot, calculationSlug, qms, refresh]);
  
  return {
    ...state,
    refresh,
    applyPreset,
    applyPresets,
    clearApplyResult,
  };
}

