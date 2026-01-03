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

import { useCallback, useMemo } from 'react';
import type { StepDetail } from '../../types/qv';
import type { QEParameterMeta, QEModuleMeta } from '../../hooks/useQEParameterMetadata';
import { ParameterValueEditor } from './ParameterValueEditor';
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
}: ActiveParametersPanelProps) {
  
  // Group active parameters by namelist
  // Handles both:
  // 1. QE-style nested: { SYSTEM: { ecutwfc: 40 }, CONTROL: { ... } }
  // 2. W90-style flat: { seedname: "diamond", num_wann: 4 }
  const parametersByNamelist = useMemo(() => {
    const grouped: Record<string, ParameterWithMetadata[]> = {};
    
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
        
        namelistParams.push({
          namelist,
          name: paramName,
          value,
          metadata: paramMeta || null,
        });
      }
      
      if (namelistParams.length > 0) {
        // Sort by parameter name
        namelistParams.sort((a, b) => a.name.localeCompare(b.name));
        grouped[namelist] = namelistParams;
      }
    }
    
    return grouped;
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
  
  if (!hasActiveParameters) {
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
              <div key={`${namelist}:${param.name}`} className="active-parameters-panel__parameter-row">
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
                  {isEditing ? (
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
                    />
                  ) : (
                    <code className="active-parameters-panel__parameter-value-display">
                      {param.value === null || param.value === undefined ? '—' : String(param.value)}
                    </code>
                  )}
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
    </div>
  );
}

