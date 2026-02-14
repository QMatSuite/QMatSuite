/**
 * ActiveParametersPanel - Shows active parameters grouped by namelist/card
 * 
 * Displays only parameters that are currently set in the step, grouped by:
 * - Namelists: &CONTROL, &SYSTEM, &ELECTRONS, etc.
 * - Cards: K_POINTS, ATOMIC_SPECIES, etc.
 * 
 * Each parameter row shows:
 * - Parameter name
 * - Value editor (type-aware)
 * - Actions: Unset (remove user value) and Remove (delete from step)
 * - Info tooltip: description + type + default + enum/range + module/section
 */

import { useCallback, useMemo, useState } from 'react';
import type { StepDetail } from '../../types/qv';
import type { QEParameterMeta, QEModuleMeta } from '../../hooks/useEngineParameterMetadata';
import { ParameterValueEditor } from './ParameterValueEditor';
import { ParameterModeSelector } from './ParameterModeSelector';
import { ScanValuesEditor } from './ScanValuesEditor';
import { isScanRef, getScanId, isLeafValue } from '../../utils/scanUtils';
import './ActiveParametersPanel.css';

interface ActiveParametersPanelProps {
  stepDetail: StepDetail;
  module: string | null;
  metadata: {
    parameters: Map<string, QEParameterMeta>; // key: "module::section::name"
    modules: QEModuleMeta[];
  };
  isEditing: boolean;
  onParameterChange: (namelist: string, paramName: string, value: unknown) => void;
  onParameterReset: (namelist: string, paramName: string) => void;
  onParameterRemove: (namelist: string, paramName: string) => void;
  onScanToggle?: (namelist: string, paramName: string, enabled: boolean) => void;
  onScanValuesChange?: (scanId: string, values: unknown[]) => void;
  editedParameterScan?: Record<string, { values: unknown[] }>; // Current edited parameter_scan state
}

interface ParameterWithMetadata {
  namelist: string;
  name: string;
  value: unknown;
  metadata: QEParameterMeta | null;
}

export function ActiveParametersPanel({
  stepDetail,
  module,
  metadata,
  isEditing,
  onParameterChange,
  onParameterReset,
  onParameterRemove,
  onScanToggle,
  onScanValuesChange,
  editedParameterScan,
}: ActiveParametersPanelProps) {
  
  // Group active parameters by namelist, separating managed from editable
  // Handles both:
  // 1. QE-style nested: { SYSTEM: { ecutwfc: 40 }, CONTROL: { ... } }
  // 2. W90-style flat: { seedname: "diamond", num_wann: 4 }
  const { parametersByNamelist, managedParameters } = useMemo(() => {
    const grouped: Record<string, ParameterWithMetadata[]> = {};
    const managed: ParameterWithMetadata[] = [];
    
    // Detect if parameters are flat (non-namelist) or nested (namelist-wrapped)
    // Flat parameters have primitive values at the top level
    const isFlat = Object.values(stepDetail.parameters).some(
      val => typeof val !== 'object' || val === null || Array.isArray(val)
    );
    
    if (isFlat) {
      // W90-style flat parameters: treat top-level keys as parameter names
      // Group under a synthetic "PARAMETERS" section
      const flatParams: ParameterWithMetadata[] = [];
      
      for (const [paramName, value] of Object.entries(stepDetail.parameters)) {
        // Skip if value is an object (it's a namelist, not a flat param)
        if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
          continue;
        }
        
        flatParams.push({
          namelist: 'PARAMETERS',
          name: paramName,
          value,
          metadata: null, // No QE metadata for W90 params
        });
      }
      
      if (flatParams.length > 0) {
        flatParams.sort((a, b) => a.name.localeCompare(b.name));
        grouped['PARAMETERS'] = flatParams;
      }
    }
    
    // Process namelist parameters (nested objects)
    for (const [namelist, params] of Object.entries(stepDetail.parameters)) {
      // Skip if params is not an object (handled above as flat param)
      if (typeof params !== 'object' || params === null || Array.isArray(params)) {
        continue;
      }
      
      if (Object.keys(params).length === 0) continue;
      
      const namelistParams: ParameterWithMetadata[] = [];
      
      for (const [paramName, value] of Object.entries(params)) {
        // Look up metadata
        const sectionKey = namelist.startsWith('&') ? namelist : `&${namelist}`;
        const metadataKey = module ? `${module}::${sectionKey}::${paramName}` : null;
        const paramMeta = metadataKey ? metadata.parameters.get(metadataKey) : null;
        
        const param: ParameterWithMetadata = {
          namelist,
          name: paramName,
          value,
          metadata: paramMeta || null,
        };
        
        // Check if parameter is managed
        const isManaged = paramMeta && (paramMeta as any).is_managed === true;
        if (isManaged) {
          managed.push(param);
        } else {
          namelistParams.push(param);
        }
      }
      
      if (namelistParams.length > 0) {
        // Sort by parameter name
        namelistParams.sort((a, b) => a.name.localeCompare(b.name));
        grouped[namelist] = namelistParams;
      }
    }
    
    // Sort managed parameters
    managed.sort((a, b) => {
      const namelistCompare = a.namelist.localeCompare(b.namelist);
      if (namelistCompare !== 0) return namelistCompare;
      return a.name.localeCompare(b.name);
    });
    
    return { parametersByNamelist: grouped, managedParameters: managed };
  }, [stepDetail.parameters, module, metadata]);
  
  // Process cards (if any)
  const cards = useMemo(() => {
    const cardList: Array<{ name: string; data: Record<string, unknown> }> = [];
    
    for (const [cardName, cardData] of Object.entries(stepDetail.cards)) {
      if (cardData && Object.keys(cardData).length > 0) {
        cardList.push({ name: cardName, data: cardData });
      }
    }
    
    return cardList.sort((a, b) => a.name.localeCompare(b.name));
  }, [stepDetail.cards]);
  
  const hasActiveParameters = Object.keys(parametersByNamelist).length > 0 || cards.length > 0;
  
  // Extract prefix/outdir injection metadata
  const injectionInfo = stepDetail.prefix_outdir_injection;
  const hasInjectionInfo = injectionInfo && (
    injectionInfo.effective_prefix || 
    injectionInfo.effective_outdir || 
    injectionInfo.ignored_step_prefix || 
    injectionInfo.ignored_step_outdir
  );
  
  if (!hasActiveParameters && !hasInjectionInfo) {
    return (
      <div className="active-parameters-panel">
        <div className="active-parameters-panel__empty">
          <p>No parameters set. Use "Add Parameter" to add QE parameters.</p>
        </div>
      </div>
    );
  }
  
  // Generate tooltip text for a parameter
  const getParameterTooltip = useCallback((param: ParameterWithMetadata): string => {
    if (!param.metadata) {
      return `${param.name}: ${param.value}`;
    }
    
    const parts: string[] = [];
    if (param.metadata.description) {
      parts.push(param.metadata.description);
    }
    parts.push(`Type: ${param.metadata.type || 'UNKNOWN'}`);
    if (param.metadata.default !== null && param.metadata.default !== undefined) {
      parts.push(`Default: ${param.metadata.default}`);
    }
    if (param.metadata.enum && param.metadata.enum.length > 0) {
      parts.push(`Enum: ${param.metadata.enum.join(', ')}`);
    }
    if (param.metadata.module) {
      parts.push(`Module: ${param.metadata.module}`);
    }
    if (param.metadata.section) {
      parts.push(`Section: ${param.metadata.section}`);
    }
    
    return parts.join(' • ');
  }, []);
  
  return (
    <div className="active-parameters-panel">
      {/* Prefix/Outdir Injection Info */}
      {hasInjectionInfo && (
        <div className="active-parameters-panel__injection-info">
          <div className="active-parameters-panel__injection-header">
            <span className="active-parameters-panel__injection-title">Calculation-Level Settings</span>
            <span className="active-parameters-panel__injection-subtitle">These values are injected from the calculation and override step-level settings</span>
          </div>
          
          <div className="active-parameters-panel__injection-fields">
            {injectionInfo.effective_prefix && (
              <div className="active-parameters-panel__injection-field">
                <span className="active-parameters-panel__injection-label">Effective prefix:</span>
                <code className="active-parameters-panel__injection-value">{injectionInfo.effective_prefix}</code>
                <span className="active-parameters-panel__injection-note">(from calculation)</span>
              </div>
            )}
            
            {injectionInfo.effective_outdir && (
              <div className="active-parameters-panel__injection-field">
                <span className="active-parameters-panel__injection-label">Effective outdir:</span>
                <code className="active-parameters-panel__injection-value">{injectionInfo.effective_outdir}</code>
                <span className="active-parameters-panel__injection-note">(from calculation)</span>
              </div>
            )}
            
            {(injectionInfo.ignored_step_prefix || injectionInfo.ignored_step_outdir) && (
              <div className="active-parameters-panel__injection-warning">
                <span className="active-parameters-panel__injection-warning-icon">⚠️</span>
                <div className="active-parameters-panel__injection-warning-content">
                  <span className="active-parameters-panel__injection-warning-title">Ignored step-level overrides:</span>
                  {injectionInfo.ignored_step_prefix && (
                    <div className="active-parameters-panel__injection-warning-item">
                      <span>prefix:</span>
                      <code>{injectionInfo.ignored_step_prefix}</code>
                      <span>(calculation value used instead)</span>
                    </div>
                  )}
                  {injectionInfo.ignored_step_outdir && (
                    <div className="active-parameters-panel__injection-warning-item">
                      <span>outdir:</span>
                      <code>{injectionInfo.ignored_step_outdir}</code>
                      <span>(calculation value used instead)</span>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
      
      {/* Namelist parameters */}
      {Object.entries(parametersByNamelist).map(([namelist, params]) => (
        <div key={namelist} className="active-parameters-panel__namelist-group">
          <div className="active-parameters-panel__namelist-header">
            <span className="active-parameters-panel__namelist-name">
              {namelist.startsWith('&') ? namelist : `&${namelist}`}
            </span>
            <span className="active-parameters-panel__namelist-count">
              {params.length} parameter{params.length !== 1 ? 's' : ''}
            </span>
          </div>
          
          <div className="active-parameters-panel__parameters">
            {params.map((param) => (
              <div key={`${namelist}:${param.name}`} className="active-parameters-panel__parameter-row" data-testid={`qv-param-row-${namelist.toLowerCase()}-${param.name.toLowerCase()}`}>
                <div className="active-parameters-panel__parameter-info">
                  <span className="active-parameters-panel__parameter-name" title={getParameterTooltip(param)}>
                    {param.name}
                  </span>
                  {param.metadata && (
                    <span className="active-parameters-panel__parameter-type">
                      {param.metadata.type || 'UNKNOWN'}
                    </span>
                  )}
                </div>
                
                <div className="active-parameters-panel__parameter-value">
                  {(() => {
                    const isScanned = isScanRef(param.value);
                    const scanId = isScanned ? getScanId(param.value) : null;
                    const canScan = isLeafValue(param.value) || isScanned;
                    const currentMode: 'value' | 'scan' = isScanned ? 'scan' : 'value';
                    
                    // Check for unsupported object values
                    if (typeof param.value === 'object' && param.value !== null && !Array.isArray(param.value) && !isScanRef(param.value)) {
                      return (
                        <div className="active-parameters-panel__unsupported-value">
                          <code className="active-parameters-panel__parameter-value-display">
                            Unsupported object value
                          </code>
                          <span className="active-parameters-panel__unsupported-warning">
                            ⚠️ Complex objects cannot be scanned
                          </span>
                        </div>
                      );
                    }
                    
                    // Check if parameter is managed (skip scan toggle for managed params)
                    const isManaged = param.metadata && (param.metadata as any).is_managed === true;
                    
                    // Show mode selector + editor (skip if managed)
                    if (isEditing && canScan && onScanToggle && !isManaged) {
                      return (
                        <div className="active-parameters-panel__value-editor-container">
                          {/* Mode selector: Value/Scan */}
                          <ParameterModeSelector
                            mode={currentMode}
                            onChange={(mode) => {
                              if (mode === 'scan' && !isScanned) {
                                onScanToggle(namelist, param.name, true);
                              } else if (mode === 'value' && isScanned) {
                                onScanToggle(namelist, param.name, false);
                              }
                            }}
                            disabled={false}
                            showScanBadge={isScanned}
                          />
                          
                          {/* Editor based on mode */}
                          {currentMode === 'scan' && scanId && onScanValuesChange ? (
                            <div className="active-parameters-panel__scan-editor-inline">
                              {(() => {
                                // Use editedParameterScan if editing and it has scan definitions, otherwise fall back to stepDetail.parameter_scan
                                // Empty object {} is truthy, so we must check for actual keys
                                const editedHasScan = editedParameterScan && Object.keys(editedParameterScan).length > 0;
                                const effectiveParameterScan =
                                  isEditing
                                    ? (editedHasScan ? editedParameterScan : (stepDetail.parameter_scan || {}))
                                    : (stepDetail.parameter_scan || {});
                                const scanDef = effectiveParameterScan?.[scanId];
                                const scanValues = scanDef?.values || [];
                                const hasEmptyValues = scanValues.length === 0;
                                
                                return (
                                  <>
                                    <ScanValuesEditor
                                      values={scanValues}
                                      onChange={(values) => onScanValuesChange(scanId, values)}
                                      disabled={false}
                                    />
                                    {hasEmptyValues && (
                                      <div className="active-parameters-panel__scan-warning">
                                        ⚠️ Empty scan values
                                      </div>
                                    )}
                                    {!scanDef && (
                                      <div className="active-parameters-panel__scan-warning">
                                        ⚠️ Dangling scan_ref: scan_id '{scanId}' not found
                                      </div>
                                    )}
                                  </>
                                );
                              })()}
                            </div>
                          ) : (
                            <div className="active-parameters-panel__value-editor-wrapper">
                    <ParameterValueEditor
                      parameter={param.metadata || {
                        name: param.name,
                        type: null,
                        default: null,
                        enum: null,
                        description: null,
                        section: namelist,
                        module: module || '',
                      }}
                      value={param.value}
                      onChange={(value) => onParameterChange(namelist, param.name, value)}
                      disabled={false}
                      testIdSuffix={`${namelist.toLowerCase()}-${param.name.toLowerCase()}`}
                    />
                            </div>
                          )}
                        </div>
                      );
                    }
                    
                    // Non-editing mode: show value display
                    if (!isEditing) {
                      return (
                    <code className="active-parameters-panel__parameter-value-display">
                          {(() => {
                            if (isScanned) {
                              const scanDef = stepDetail.parameter_scan?.[scanId || ''];
                              const count = scanDef?.values?.length || 0;
                              return `@scan:${scanId} (${count} values)`;
                            }
                            return param.value === null || param.value === undefined ? '—' : String(param.value);
                          })()}
                    </code>
                      );
                    }
                    
                    // Fallback: value editor only (no scan support)
                    return (
                      <ParameterValueEditor
                        parameter={param.metadata || {
                          name: param.name,
                          type: null,
                          default: null,
                          enum: null,
                          description: null,
                          section: namelist,
                          module: module || '',
                        }}
                        value={param.value}
                        onChange={(value) => onParameterChange(namelist, param.name, value)}
                        disabled={false}
                        testIdSuffix={`${namelist.toLowerCase()}-${param.name.toLowerCase()}`}
                      />
                    );
                  })()}
                </div>
                
                {isEditing && (
                  <div className="active-parameters-panel__parameter-actions">
                    <button
                      className="active-parameters-panel__action-btn"
                      onClick={() => onParameterReset(namelist, param.name)}
                      title="Unset parameter (remove user value)"
                    >
                      ↺ Unset
                    </button>
                    <button
                      className="active-parameters-panel__action-btn active-parameters-panel__action-btn--danger"
                      onClick={() => onParameterRemove(namelist, param.name)}
                      title="Remove parameter from step"
                    >
                      ✕ Remove
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
      
      {/* Cards */}
      {cards.length > 0 && (
        <div className="active-parameters-panel__cards-group">
          <div className="active-parameters-panel__cards-header">
            <span className="active-parameters-panel__cards-title">Cards</span>
          </div>
          
          {cards.map((card) => (
            <div key={card.name} className="active-parameters-panel__card-item">
              <span className="active-parameters-panel__card-name">{card.name}</span>
              <code className="active-parameters-panel__card-data">
                {JSON.stringify(card.data, null, 2)}
              </code>
            </div>
          ))}
        </div>
      )}
      
      {/* Managed / Injected Parameters (read-only) */}
      {managedParameters.length > 0 && (
        <ManagedParametersSection
          managedParameters={managedParameters}
          stepDetail={stepDetail}
        />
      )}
    </div>
  );
}

// Managed Parameters Section Component
interface ManagedParametersSectionProps {
  managedParameters: ParameterWithMetadata[];
  stepDetail: StepDetail;
}

function ManagedParametersSection({
  managedParameters,
  stepDetail,
}: ManagedParametersSectionProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  
  const getManagedReasonText = (param: ParameterWithMetadata): string => {
    const meta = param.metadata as any;
    const reason = meta?.managed_reason;
    if (reason === 'runtime_overridden') {
      return 'Overridden at run time';
    } else if (reason === 'step_type_owned') {
      return 'Owned by step type';
    }
    return 'Managed parameter';
  };
  
  return (
    <div className="active-parameters-panel__managed-section">
      <button
        className="active-parameters-panel__managed-header"
        onClick={() => setIsExpanded(!isExpanded)}
        type="button"
      >
        <span className="active-parameters-panel__managed-title">
          Managed / Injected Parameters (read-only)
        </span>
        <span className="active-parameters-panel__managed-count">
          {managedParameters.length}
        </span>
        <span className="active-parameters-panel__managed-toggle">
          {isExpanded ? '▼' : '▶'}
        </span>
      </button>
      
      {isExpanded && (
        <div className="active-parameters-panel__managed-content">
          {managedParameters.map((param) => {
            const reasonText = getManagedReasonText(param);
            // Get effective value from injection info if available
            const injectionInfo = stepDetail.prefix_outdir_injection;
            let effectiveValue = param.value;
            if (param.name === 'prefix' && injectionInfo?.effective_prefix) {
              effectiveValue = injectionInfo.effective_prefix;
            } else if (param.name === 'outdir' && injectionInfo?.effective_outdir) {
              effectiveValue = injectionInfo.effective_outdir;
            }
            
            return (
              <div key={`${param.namelist}:${param.name}`} className="active-parameters-panel__managed-param">
                <div className="active-parameters-panel__managed-param-info">
                  <span className="active-parameters-panel__managed-param-name">
                    {param.namelist}.{param.name}
                  </span>
                  <span className="active-parameters-panel__managed-param-reason">
                    {reasonText}
                  </span>
                </div>
                <div className="active-parameters-panel__managed-param-value">
                  <code className="active-parameters-panel__parameter-value-display">
                    {effectiveValue === null || effectiveValue === undefined 
                      ? '(not set)' 
                      : String(effectiveValue)}
                  </code>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

