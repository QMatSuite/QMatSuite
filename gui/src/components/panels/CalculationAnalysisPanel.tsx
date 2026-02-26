import { useCallback, useEffect, useRef, useState } from 'react';

import { useQMSClient } from '../../hooks/useQMSClient';
import type {
  CalculationDetailResult,
  CalculationInfo,
  PrimitiveBundleData,
} from '../../types/qms';
import { normalizeProjectRoot } from '../../utils/pathUtils';
import { AnalysisVizPanel } from './AnalysisVizPanel';
import { FatbandsVizPanel } from './FatbandsVizPanel';
import { Field3DVizPanel } from './Field3DVizPanel';
import { RawFileViewer } from './RawFileViewer';
import { StepDigestPanel } from './StepDigestPanel';
import { TrajectoryVizPanel } from './TrajectoryVizPanel';
import './CalculationAnalysisPanel.css';

interface CalculationAnalysisPanelProps {
  projectRoot: string;
  calculation: CalculationInfo | CalculationDetailResult | null;
}

type StepViewMode = 'raw' | 'analysis';

type AnalysisResponse = {
  run_ulid: string;
  object_type: string;
  canonical_sha: string;
  bundle: PrimitiveBundleData;
};

const ANALYSIS_OBJECT_TYPES = ['bands', 'dos', 'convergence', 'trajectory', 'neb_trajectory', 'field3d'];

export function CalculationAnalysisPanel({
  projectRoot,
  calculation,
}: CalculationAnalysisPanelProps) {
  const qms = useQMSClient();
  const steps = calculation
    ? ((calculation as CalculationDetailResult).steps ??
      (calculation as CalculationInfo).steps ??
      [])
    : [];
  const calcSelector = calculation ? calculation.slug || calculation.name : null;

  const [selectedStepId, setSelectedStepId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<StepViewMode>('raw');

  const [runInfo, setRunInfo] = useState<{ run_ulid: string | null; can_pin: boolean; reason: string | null } | null>(null);
  const [runInfoError, setRunInfoError] = useState<string | null>(null);

  const [digestLoading, setDigestLoading] = useState(false);
  const [digestError, setDigestError] = useState<string | null>(null);
  const [digestPayload, setDigestPayload] = useState<Record<string, unknown> | null>(null);
  const [digestSha, setDigestSha] = useState<string | null>(null);
  const [digestEngine, setDigestEngine] = useState<string | null>(null);

  const [availableObjectTypes, setAvailableObjectTypes] = useState<string[]>([]);
  const [selectedObjectType, setSelectedObjectType] = useState<string | null>(null);
  const [shiftToFermi, setShiftToFermi] = useState(false);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [analysisResponse, setAnalysisResponse] = useState<AnalysisResponse | null>(null);
  const analysisCacheRef = useRef<Record<string, AnalysisResponse>>({});

  const [pinning, setPinning] = useState(false);
  const [pinMessage, setPinMessage] = useState<string | null>(null);

  // Reference data from demo ref packs
  const [referenceData, setReferenceData] = useState<AnalysisResponse | null>(null);
  const [showReference, setShowReference] = useState(false);
  const [referenceOnlyMode, setReferenceOnlyMode] = useState(false);

  useEffect(() => {
    if (!steps.length) {
      setSelectedStepId(null);
      return;
    }
    if (!selectedStepId || !steps.some((step) => step.ulid === selectedStepId)) {
      setSelectedStepId(steps[0].ulid);
    }
  }, [selectedStepId, steps]);

  useEffect(() => {
    if (!selectedStepId || !calcSelector) {
      setRunInfo(null);
      setRunInfoError(null);
      return;
    }
    const normalizedRoot = normalizeProjectRoot(projectRoot);
    if (!normalizedRoot) {
      setRunInfo(null);
      setRunInfoError('Invalid project path');
      return;
    }

    let cancelled = false;
    setRunInfoError(null);
    qms.call('get_latest_run_for_step', {
      project_root: normalizedRoot,
      step_ulid: selectedStepId,
    })
      .then((response) => {
        if (cancelled) {
          return;
        }
        if (!response.ok || !response.data) {
          setRunInfo(null);
          setRunInfoError(response.error?.message ?? 'Failed to resolve run for step');
          return;
        }
        setRunInfo(response.data);
      })
      .catch((err) => {
        if (!cancelled) {
          setRunInfo(null);
          setRunInfoError(err instanceof Error ? err.message : 'Failed to resolve run for step');
        }
      });
    return () => {
      cancelled = true;
    };
  }, [calcSelector, projectRoot, qms, selectedStepId]);

  useEffect(() => {
    if (!runInfo?.run_ulid || !selectedStepId) {
      setDigestPayload(null);
      setDigestSha(null);
      setDigestEngine(null);
      setDigestLoading(false);
      setDigestError(null);
      return;
    }

    const normalizedRoot = normalizeProjectRoot(projectRoot);
    if (!normalizedRoot) {
      setDigestError('Invalid project path');
      return;
    }

    let cancelled = false;
    setDigestLoading(true);
    setDigestError(null);
    qms.call('get_step_digest', {
      project_root: normalizedRoot,
      run_ulid: runInfo.run_ulid,
      step_ulid: selectedStepId,
    })
      .then((response) => {
        if (cancelled) {
          return;
        }
        if (!response.ok || !response.data) {
          setDigestPayload(null);
          setDigestSha(null);
          setDigestEngine(null);
          setDigestError(response.error?.message ?? 'Failed to load step digest');
          return;
        }
        setDigestPayload(response.data.available ? response.data.digest : null);
        setDigestSha(response.data.digest_sha);
        setDigestEngine(response.data.engine ?? null);
      })
      .catch((err) => {
        if (!cancelled) {
          setDigestPayload(null);
          setDigestSha(null);
          setDigestEngine(null);
          setDigestError(err instanceof Error ? err.message : 'Failed to load step digest');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setDigestLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [projectRoot, qms, runInfo?.run_ulid, selectedStepId]);

  useEffect(() => {
    const runUlid = runInfo?.run_ulid;
    if (!selectedStepId || !runUlid) {
      // Don't clear available types if reference-only mode is active
      if (!referenceOnlyMode) {
        setAvailableObjectTypes([]);
        setSelectedObjectType(null);
      }
      setAnalysisResponse(null);
      setAnalysisError(null);
      return;
    }

    // If we have a real run, exit reference-only mode
    if (referenceOnlyMode) {
      setReferenceOnlyMode(false);
    }

    const normalizedRoot = normalizeProjectRoot(projectRoot);
    if (!normalizedRoot) {
      setAvailableObjectTypes([]);
      setSelectedObjectType(null);
      return;
    }

    let cancelled = false;
    const detect = async () => {
      const matched: string[] = [];
      for (const objectType of ANALYSIS_OBJECT_TYPES) {
        const cacheKey = `${runUlid}:${objectType}:canonical`;
        let payload = analysisCacheRef.current[cacheKey];
        if (!payload) {
          const response = await qms.call('get_analysis', {
            project_root: normalizedRoot,
            run_ulid: runUlid,
            object_type: objectType,
          });
          if (!response.ok || !response.data) {
            continue;
          }
          payload = response.data;
          analysisCacheRef.current[cacheKey] = payload;
        }

        if (payload.bundle.provenance_meta.step_ulids.includes(selectedStepId)) {
          matched.push(objectType);
        }
      }

      if (cancelled) {
        return;
      }
      setAvailableObjectTypes(matched);
      setShiftToFermi(false);
      if (!matched.length) {
        setSelectedObjectType(null);
        setViewMode('raw');
        return;
      }
      setViewMode('analysis');
      setSelectedObjectType((previous) => (previous && matched.includes(previous) ? previous : matched[0]));
    };

    void detect();
    return () => {
      cancelled = true;
    };
  }, [projectRoot, qms, referenceOnlyMode, runInfo?.run_ulid, selectedStepId]);

  useEffect(() => {
    const runUlid = runInfo?.run_ulid;
    if (!runUlid || !selectedObjectType) {
      setAnalysisLoading(false);
      setAnalysisError(null);
      setAnalysisResponse(null);
      return;
    }

    const normalizedRoot = normalizeProjectRoot(projectRoot);
    if (!normalizedRoot) {
      setAnalysisError('Invalid project path');
      setAnalysisResponse(null);
      return;
    }

    const transforms = shiftToFermi ? ['FermiShift'] : [];
    const transformKey = transforms.length ? transforms.join(',') : 'canonical';
    const cacheKey = `${runUlid}:${selectedObjectType}:${transformKey}`;
    const cached = analysisCacheRef.current[cacheKey];
    if (cached) {
      setAnalysisResponse(cached);
      setAnalysisError(null);
      setAnalysisLoading(false);
      return;
    }

    let cancelled = false;
    setAnalysisLoading(true);
    setAnalysisError(null);
    qms.call('get_analysis', {
      project_root: normalizedRoot,
      run_ulid: runUlid,
      object_type: selectedObjectType,
      transforms,
    })
      .then((response) => {
        if (cancelled) {
          return;
        }
        if (!response.ok || !response.data) {
          setAnalysisResponse(null);
          setAnalysisError(response.error?.message ?? 'Failed to derive analysis bundle');
          return;
        }
        analysisCacheRef.current[cacheKey] = response.data;
        setAnalysisResponse(response.data);
      })
      .catch((err) => {
        if (!cancelled) {
          setAnalysisResponse(null);
          setAnalysisError(err instanceof Error ? err.message : 'Failed to derive analysis bundle');
        }
      })
      .finally(() => {
        if (!cancelled) {
          setAnalysisLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [projectRoot, qms, runInfo?.run_ulid, selectedObjectType, shiftToFermi]);

  // Reference-only mode: when no run available, probe for reference types
  useEffect(() => {
    if (!calcSelector || !selectedStepId) {
      setReferenceOnlyMode(false);
      setReferenceData(null);
      return;
    }

    // If there's a real run, don't activate reference-only mode
    if (runInfo?.run_ulid) {
      setReferenceOnlyMode(false);
      return;
    }

    // Wait for run resolution: runInfo is null while loading.
    // runInfo = { run_ulid: null } means "no run exists" (resolved).
    // runInfoError being set also means resolution complete.
    const resolved = (runInfo !== null && !runInfo.run_ulid) || runInfoError !== null;
    if (!resolved) {
      return;
    }

    const normalizedRoot = normalizeProjectRoot(projectRoot);
    if (!normalizedRoot) {
      return;
    }

    // Filter probe types to only those relevant for the selected step's type_gen
    const stepTypeGen = (steps.find(s => s.ulid === selectedStepId)?.step_type_gen ?? '').toLowerCase();
    const probeTypes = stepTypeGen.includes('band')
      ? ['bands', 'convergence']
      : stepTypeGen.includes('dos') || stepTypeGen === 'nscf'
        ? ['dos', 'convergence']
        : ['convergence'];

    let cancelled = false;
    const probeReferenceTypes = async () => {
      const matched: string[] = [];
      const refCache: Record<string, AnalysisResponse> = {};

      for (const objType of probeTypes) {
        const response = await qms.call('get_reference_analysis', {
          project_root: normalizedRoot,
          calculation: calcSelector,
          analysis_type: objType,
        });
        if (cancelled) return;
        if (response.ok && response.data) {
          matched.push(objType);
          refCache[objType] = response.data as AnalysisResponse;
        }
      }

      if (cancelled) return;

      if (matched.length > 0) {
        setReferenceOnlyMode(true);
        setShowReference(true);
        setAvailableObjectTypes(matched);
        setViewMode('analysis');
        setSelectedObjectType(prev => prev && matched.includes(prev) ? prev : matched[0]);
        // Set initial reference data for the first type
        const firstType = matched[0];
        setReferenceData(refCache[firstType] ?? null);
        // Store full cache in ref for later use
        referenceCacheRef.current = refCache;
      } else {
        setReferenceOnlyMode(false);
        setReferenceData(null);
      }
    };

    void probeReferenceTypes();
    return () => { cancelled = true; };
  }, [calcSelector, projectRoot, qms, runInfo, runInfoError, selectedStepId, steps]);

  // Fetch reference data when selectedObjectType changes (for reference-only mode or overlay)
  const referenceCacheRef = useRef<Record<string, AnalysisResponse>>({});

  useEffect(() => {
    if (!calcSelector || !selectedObjectType) {
      setReferenceData(null);
      return;
    }

    // Check cache first
    const cached = referenceCacheRef.current[selectedObjectType];
    if (cached) {
      setReferenceData(cached);
      return;
    }

    const normalizedRoot = normalizeProjectRoot(projectRoot);
    if (!normalizedRoot) {
      return;
    }

    let cancelled = false;
    qms.call('get_reference_analysis', {
      project_root: normalizedRoot,
      calculation: calcSelector,
      analysis_type: selectedObjectType,
    })
      .then((response) => {
        if (cancelled) return;
        if (response.ok && response.data) {
          const refResp = response.data as AnalysisResponse;
          referenceCacheRef.current[selectedObjectType] = refResp;
          setReferenceData(refResp);
        } else {
          setReferenceData(null);
        }
      })
      .catch(() => {
        if (!cancelled) setReferenceData(null);
      });
    return () => { cancelled = true; };
  }, [calcSelector, projectRoot, qms, selectedObjectType]);

  useEffect(() => {
    if (!pinMessage) {
      return;
    }
    const timer = setTimeout(() => setPinMessage(null), 3500);
    return () => clearTimeout(timer);
  }, [pinMessage]);

  const handlePin = useCallback(async () => {
    if (!selectedStepId || !analysisResponse) {
      return;
    }
    const normalizedRoot = normalizeProjectRoot(projectRoot);
    if (!normalizedRoot) {
      setPinMessage('Invalid project path');
      return;
    }

    setPinning(true);
    setPinMessage(null);
    try {
      const response = await qms.call('pin_analysis_to_history', {
        project_root: normalizedRoot,
        step_ulid: selectedStepId,
        analysis_kind: analysisResponse.object_type,
        json_payload: analysisResponse,
      });
      if (!response.ok || !response.data?.success) {
        setPinMessage(response.error?.message ?? response.data?.error ?? 'Pin failed');
        return;
      }
      const source = response.data.run_ulid_source ?? 'unknown';
      setPinMessage(`Pinned (${source})`);
    } catch (err) {
      setPinMessage(err instanceof Error ? err.message : 'Pin failed');
    } finally {
      setPinning(false);
    }
  }, [analysisResponse, projectRoot, qms, selectedStepId]);

  if (!calculation) {
    return (
      <div className="calculation-analysis-panel calculation-analysis-panel--empty">
        No calculation selected.
      </div>
    );
  }

  if (!steps.length || !selectedStepId || !calcSelector) {
    return (
      <div className="calculation-analysis-panel calculation-analysis-panel--empty">
        No calculation steps are available.
      </div>
    );
  }

  return (
    <div className="calculation-analysis-panel" data-testid="qms-calc-analysis-panel">
      <div className="calculation-analysis-panel__header">
        <h3>Analysis: {calculation.name}</h3>
        {(referenceData || referenceOnlyMode) && (
          <label className="calculation-analysis-panel__ref-toggle">
            <input
              checked={showReference}
              onChange={(e) => setShowReference(e.target.checked)}
              data-testid="qms-analysis-reference-toggle"
              type="checkbox"
            />
            Reference
          </label>
        )}
      </div>

      <div className="calculation-analysis-panel__step-tabs">
        {steps.map((step) => (
          <button
            key={step.ulid}
            className={`calculation-analysis-panel__step-tab${
              step.ulid === selectedStepId ? ' calculation-analysis-panel__step-tab--active' : ''
            }`}
            data-testid={`qms-analysis-step-tab-${step.step_type_gen}`}
            data-step-type-gen={step.step_type_gen}
            onClick={() => setSelectedStepId(step.ulid)}
            type="button"
          >
            {step.step_type_gen.toUpperCase()}
          </button>
        ))}
      </div>

      <div className="calculation-analysis-panel__surface-tabs">
        <button
          className={`calculation-analysis-panel__view-mode-tab calculation-analysis-panel__surface-tab${
            viewMode === 'raw' ? ' calculation-analysis-panel__surface-tab--active' : ''
          }`}
          onClick={() => setViewMode('raw')}
          type="button"
        >
          Raw
        </button>
        <button
          className={`calculation-analysis-panel__view-mode-tab calculation-analysis-panel__surface-tab${
            viewMode === 'analysis' ? ' calculation-analysis-panel__surface-tab--active' : ''
          }`}
          onClick={() => setViewMode('analysis')}
          type="button"
        >
          Plot
        </button>
      </div>

      <div className="calculation-analysis-panel__content">
        {!referenceOnlyMode && (
          <StepDigestPanel
            digest={digestPayload}
            digestSha={digestSha}
            engine={digestEngine}
            error={digestError ?? runInfoError}
            loading={digestLoading}
          />
        )}

        {referenceOnlyMode && showReference && referenceData && (
          <div
            className="calculation-analysis-panel__reference-banner"
            data-testid="qms-analysis-reference-banner"
          >
            Reference data (pre-computed, no engine run required)
          </div>
        )}

        {(() => {
          // In reference-only mode, use reference bundle; otherwise use analysis response
          const activeBundle: PrimitiveBundleData | null =
            referenceOnlyMode && showReference && referenceData
              ? referenceData.bundle
              : analysisResponse?.bundle ?? null;
          const activeLoading = referenceOnlyMode ? false : analysisLoading;
          const activeError = referenceOnlyMode ? null : analysisError;

          return viewMode === 'raw' ? (
            <RawFileViewer
              calculation={calcSelector}
              projectRoot={projectRoot}
              stepId={selectedStepId}
            />
          ) : selectedObjectType === 'field3d' ? (
            <Field3DVizPanel
              availableObjectTypes={availableObjectTypes}
              bundle={activeBundle}
              canPin={!referenceOnlyMode && Boolean(analysisResponse)}
              error={activeError}
              loading={activeLoading}
              onPin={handlePin}
              onSelectObjectType={setSelectedObjectType}
              pinMessage={pinMessage}
              pinning={pinning}
              pinReason={runInfo?.reason ?? null}
              projectRoot={projectRoot}
              runUlid={runInfo?.run_ulid ?? null}
              selectedObjectType={selectedObjectType}
            />
          ) : selectedObjectType === 'trajectory' || selectedObjectType === 'neb_trajectory' ? (
            <TrajectoryVizPanel
              availableObjectTypes={availableObjectTypes}
              bundle={activeBundle}
              canPin={!referenceOnlyMode && Boolean(analysisResponse)}
              error={activeError}
              loading={activeLoading}
              onPin={handlePin}
              onSelectObjectType={setSelectedObjectType}
              pinMessage={pinMessage}
              pinning={pinning}
              pinReason={runInfo?.reason ?? null}
              selectedObjectType={selectedObjectType}
            />
          ) : selectedObjectType === 'bands' && activeBundle?.render_meta?.extra?.has_projections ? (
            <FatbandsVizPanel
              availableObjectTypes={availableObjectTypes}
              bundle={activeBundle}
              canPin={!referenceOnlyMode && Boolean(analysisResponse)}
              error={activeError}
              loading={activeLoading}
              onPin={handlePin}
              onSelectObjectType={setSelectedObjectType}
              onShiftToFermiChange={setShiftToFermi}
              pinMessage={pinMessage}
              pinning={pinning}
              pinReason={runInfo?.reason ?? null}
              selectedObjectType={selectedObjectType}
              shiftToFermi={shiftToFermi}
            />
          ) : (
            <AnalysisVizPanel
              availableObjectTypes={availableObjectTypes}
              bundle={activeBundle}
              canPin={!referenceOnlyMode && Boolean(analysisResponse)}
              error={activeError}
              loading={activeLoading}
              onPin={handlePin}
              onSelectObjectType={setSelectedObjectType}
              onShiftToFermiChange={setShiftToFermi}
              pinMessage={pinMessage}
              pinning={pinning}
              pinReason={runInfo?.reason ?? null}
              selectedObjectType={selectedObjectType}
              shiftToFermi={shiftToFermi}
            />
          );
        })()}
      </div>
    </div>
  );
}
