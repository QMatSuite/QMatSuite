/**
 * CreateCalculationDialog - Dialog for creating a new calculation from template
 */

import { useState, useCallback, useEffect } from 'react';
import { Modal } from './Modal';
import { useQVClient } from '../../hooks/useQVClient';
import type { StructureInfo, CalculationTemplateInfo, WorkflowTemplate, EngineFamilyInfo } from '../../types/qv';

interface CreateCalculationDialogProps {
  isOpen: boolean;
  projectRoot: string;
  structures: StructureInfo[];
  onClose: () => void;
  onSuccess: (calculationId: string) => void;
}

export function CreateCalculationDialog({ 
  isOpen,
  projectRoot,
  structures,
  onClose, 
  onSuccess,
}: CreateCalculationDialogProps) {
  const qv = useQVClient();
  
  const [calculationName, setCalculationName] = useState('');
  const [selectedStructure, setSelectedStructure] = useState('');
  const [selectedTemplate, setSelectedTemplate] = useState('');
  const [selectedWorkflow, setSelectedWorkflow] = useState('');
  const [selectedEngine, setSelectedEngine] = useState('');
  const [engineFamilies, setEngineFamilies] = useState<EngineFamilyInfo[]>([]);
  const [templates, setTemplates] = useState<CalculationTemplateInfo[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowTemplate[]>([]);
  const [localStructures, setLocalStructures] = useState<StructureInfo[]>([]);
  const [isLoadingTemplates, setIsLoadingTemplates] = useState(false);
  const [isLoadingStructures, setIsLoadingStructures] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Use provided structures or fetch if not provided
  const effectiveStructures = structures.length > 0 ? structures : localStructures;
  
  // Load templates, workflows, structures, and engine families when dialog opens
  useEffect(() => {
    if (isOpen) {
      if (templates.length === 0) loadTemplates();
      if (workflows.length === 0) loadWorkflows();
      // Fetch structures if not provided via props
      if (structures.length === 0 && localStructures.length === 0) {
        loadStructures();
      }
      // Fetch engine families
      if (engineFamilies.length === 0) {
        qv.listEngineFamilies().then((res) => {
          if (res.ok && res.data) {
            // Filter to base engines only (postprocessing engines can't be selected as engine_family)
            const baseEngines = res.data.engines.filter(e => e.engine_role === 'base');
            setEngineFamilies(baseEngines);
          }
        });
      }
    }
  }, [isOpen]);
  
  const loadStructures = useCallback(async () => {
    setIsLoadingStructures(true);
    const response = await qv.listStructures(projectRoot);
    setIsLoadingStructures(false);
    
    if (response.ok && response.data) {
      setLocalStructures(response.data.structures);
    }
  }, [qv, projectRoot]);
  
  const loadTemplates = useCallback(async () => {
    setIsLoadingTemplates(true);
    const response = await qv.call('list_calculation_templates', {});
    setIsLoadingTemplates(false);
    
    if (response.ok && response.data) {
      setTemplates(response.data.templates);
    }
  }, [qv]);
  
  const loadWorkflows = useCallback(async () => {
    const response = await qv.call('list_workflow_templates', {});
    if (response.ok && response.data) {
      setWorkflows(response.data.templates);
    }
  }, [qv]);
  
  const handleCreate = useCallback(async () => {
    if (!calculationName.trim()) {
      setError('Please enter a calculation name');
      return;
    }
    
    if (!projectRoot) {
      setError('No project loaded');
      return;
    }
    
    setIsCreating(true);
    setError(null);
    
    // Create the calculation first (without workflow template)
    const response = await qv.call('create_calculation', {
      project_root: projectRoot,
      name: calculationName,
      structure: selectedStructure || undefined,
      template: selectedWorkflow ? undefined : (selectedTemplate || undefined),
      engine_family: selectedEngine || undefined,  // null = UNDECIDED
    });
    
    if (!response.ok || !response.data) {
      setIsCreating(false);
      setError(response.error?.message || 'Failed to create calculation');
      return;
    }
    
    const calculationId = response.data.calculation_id;
    const calculationSlug = response.data.slug;
    
    // If workflow is selected, instantiate it
    if (selectedWorkflow && calculationId) {
      const structureId = selectedStructure ? 
        structures.find(s => s.slug === selectedStructure)?.id || '' : '';
      
      // Construct calculation path from slug (calculations/{slug})
      const calculationPath = `${projectRoot}/calculations/${calculationSlug}`;
      
      const wfResponse = await qv.call('instantiate_workflow', {
        workflow_id: selectedWorkflow,
        calculation_path: calculationPath,
        structure_id: structureId,
        calculation_id: calculationId,
      });
      
      if (!wfResponse.ok) {
        // Workflow instantiation failed but calculation was created
        setIsCreating(false);
        setError(`Calculation created, but workflow instantiation failed: ${wfResponse.error?.message}`);
        onSuccess(calculationId);
        handleClose();
        return;
      }
    }
    
    setIsCreating(false);
    onSuccess(calculationId);
    handleClose();
  }, [qv, projectRoot, calculationName, selectedStructure, selectedTemplate, selectedWorkflow, structures, onSuccess]);
  
  const handleClose = useCallback(() => {
    setCalculationName('');
    setSelectedStructure('');
    setSelectedTemplate('');
    setSelectedWorkflow('');
    setSelectedEngine('');
    setError(null);
    onClose();
  }, [onClose]);
  
  // Auto-generate name when workflow is selected
  const handleWorkflowChange = useCallback((workflowId: string) => {
    setSelectedWorkflow(workflowId);
    // Clear file template when workflow is selected
    if (workflowId) {
      setSelectedTemplate('');
    }
    // Auto-generate name from workflow
    if (workflowId && !calculationName) {
      const wf = workflows.find(w => w.id === workflowId);
      if (wf) {
        setCalculationName(wf.id);
      }
    }
  }, [calculationName, workflows]);
  
  // Auto-generate name when template is selected
  const handleTemplateChange = useCallback((templateName: string) => {
    setSelectedTemplate(templateName);
    if (templateName && !calculationName) {
      setCalculationName(templateName);
    }
  }, [calculationName]);
  
  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Create New Calculation"
      size="medium"
      footer={
        <>
          <button className="btn btn--secondary" onClick={handleClose}>
            Cancel
          </button>
          <button 
            className={`btn btn--primary ${isCreating ? 'btn--loading' : ''}`}
            onClick={handleCreate}
            disabled={isCreating || !calculationName.trim()}
          >
            Create Calculation
          </button>
        </>
      }
    >
      <div className="modal-form">
        <div className="form-group">
          <label className="form-label form-label--required">
            Calculation Name
          </label>
          <input
            type="text"
            className="form-input"
            value={calculationName}
            onChange={(e) => setCalculationName(e.target.value)}
            placeholder="si-dos"
          />
        </div>
        
        <div className="form-group">
          <label className="form-label">
            Structure
          </label>
          <select
            className="form-select"
            value={selectedStructure}
            onChange={(e) => setSelectedStructure(e.target.value)}
          >
            <option value="">— None —</option>
            {isLoadingStructures ? (
              <option disabled>Loading structures...</option>
            ) : (
              effectiveStructures.map((s) => (
                <option key={s.id} value={s.slug}>
                  {s.name} ({s.formula})
                </option>
              ))
            )}
          </select>
          <span className="form-hint">
            Select a structure for this calculation
          </span>
        </div>
        
        <div className="form-group">
          <label htmlFor="engine-family">Engine</label>
          <select
            id="engine-family"
            className="form-select"
            value={selectedEngine}
            onChange={(e) => setSelectedEngine(e.target.value)}
          >
            <option value="">Decide later</option>
            {engineFamilies.map((eng) => (
              <option key={eng.engine_family} value={eng.engine_family}>
                {eng.display_name}
              </option>
            ))}
          </select>
        </div>
        
        <div className="form-group">
          <label className="form-label">
            Workflow
          </label>
          <select
            className="form-select"
            value={selectedWorkflow}
            onChange={(e) => handleWorkflowChange(e.target.value)}
          >
            <option value="">— None (manual steps) —</option>
            {workflows.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name} ({w.step_sequence.join(' → ')})
              </option>
            ))}
          </select>
          <span className="form-hint">
            Select a workflow to auto-create steps.
          </span>
        </div>
        
        {selectedWorkflow && workflows.find(w => w.id === selectedWorkflow) && (
          <div className="template-preview">
            <div className="template-preview__label">Workflow steps:</div>
            <div className="template-preview__steps">
              {workflows.find(w => w.id === selectedWorkflow)?.step_sequence.map((type, idx) => (
                <span key={idx} className="template-preview__step">
                  {idx > 0 && <span className="step-arrow">→</span>}
                  {type}
                </span>
              ))}
            </div>
          </div>
        )}
        
        {!selectedWorkflow && (
          <div className="form-group">
            <label className="form-label">
              File Template (Legacy)
            </label>
            {isLoadingTemplates ? (
              <div className="form-hint">Loading templates...</div>
            ) : (
              <select
                className="form-select"
                value={selectedTemplate}
                onChange={(e) => handleTemplateChange(e.target.value)}
              >
                <option value="">— Empty calculation —</option>
                {templates.map((t) => (
                  <option key={t.name} value={t.name}>
                    {t.name} ({t.step_types.join(' → ')})
                  </option>
                ))}
              </select>
            )}
            <span className="form-hint">
              Or use a legacy file-based template.
            </span>
          </div>
        )}
        
        {selectedTemplate && !selectedWorkflow && templates.find(t => t.name === selectedTemplate) && (
          <div className="template-preview">
            <div className="template-preview__label">Template steps:</div>
            <div className="template-preview__steps">
              {templates.find(t => t.name === selectedTemplate)?.step_types.map((type, idx) => (
                <span key={idx} className="template-preview__step">
                  {idx > 0 && <span className="step-arrow">→</span>}
                  {type}
                </span>
              ))}
            </div>
          </div>
        )}
        
        {error && (
          <div className="form-error">
            ⚠️ {error}
          </div>
        )}
      </div>
    </Modal>
  );
}

