/**
 * CreateWorkflowDialog - Dialog for creating a new workflow from template
 */

import { useState, useCallback, useEffect } from 'react';
import { Modal } from './Modal';
import { useQVClient } from '../../hooks/useQVClient';
import type { StructureInfo, WorkflowTemplateInfo } from '../../types/qv';

interface CreateWorkflowDialogProps {
  isOpen: boolean;
  projectRoot: string;
  structures: StructureInfo[];
  onClose: () => void;
  onSuccess: (workflowId: string) => void;
}

export function CreateWorkflowDialog({ 
  isOpen,
  projectRoot,
  structures,
  onClose, 
  onSuccess,
}: CreateWorkflowDialogProps) {
  const qv = useQVClient();
  
  const [workflowName, setWorkflowName] = useState('');
  const [selectedStructure, setSelectedStructure] = useState('');
  const [selectedTemplate, setSelectedTemplate] = useState('');
  const [templates, setTemplates] = useState<WorkflowTemplateInfo[]>([]);
  const [isLoadingTemplates, setIsLoadingTemplates] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Load templates when dialog opens
  useEffect(() => {
    if (isOpen && templates.length === 0) {
      loadTemplates();
    }
  }, [isOpen]);
  
  const loadTemplates = useCallback(async () => {
    setIsLoadingTemplates(true);
    const response = await qv.call('list_workflow_templates', {});
    setIsLoadingTemplates(false);
    
    if (response.ok && response.data) {
      setTemplates(response.data.templates);
    }
  }, [qv]);
  
  const handleCreate = useCallback(async () => {
    if (!workflowName.trim()) {
      setError('Please enter a workflow name');
      return;
    }
    
    if (!projectRoot) {
      setError('No project loaded');
      return;
    }
    
    setIsCreating(true);
    setError(null);
    
    const response = await qv.call('create_workflow', {
      project_root: projectRoot,
      name: workflowName,
      structure: selectedStructure || undefined,
      template: selectedTemplate || undefined,
    });
    
    setIsCreating(false);
    
    if (response.ok && response.data) {
      onSuccess(response.data.workflow_id);
      handleClose();
    } else {
      setError(response.error?.message || 'Failed to create workflow');
    }
  }, [qv, projectRoot, workflowName, selectedStructure, selectedTemplate, onSuccess]);
  
  const handleClose = useCallback(() => {
    setWorkflowName('');
    setSelectedStructure('');
    setSelectedTemplate('');
    setError(null);
    onClose();
  }, [onClose]);
  
  // Auto-generate name when template is selected
  const handleTemplateChange = useCallback((templateName: string) => {
    setSelectedTemplate(templateName);
    if (templateName && !workflowName) {
      setWorkflowName(templateName);
    }
  }, [workflowName]);
  
  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Create New Workflow"
      size="medium"
      footer={
        <>
          <button className="btn btn--secondary" onClick={handleClose}>
            Cancel
          </button>
          <button 
            className={`btn btn--primary ${isCreating ? 'btn--loading' : ''}`}
            onClick={handleCreate}
            disabled={isCreating || !workflowName.trim()}
          >
            Create Workflow
          </button>
        </>
      }
    >
      <div className="modal-form">
        <div className="form-group">
          <label className="form-label form-label--required">
            Workflow Name
          </label>
          <input
            type="text"
            className="form-input"
            value={workflowName}
            onChange={(e) => setWorkflowName(e.target.value)}
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
            {structures.map((s) => (
              <option key={s.id} value={s.slug}>
                {s.name} ({s.formula})
              </option>
            ))}
          </select>
          <span className="form-hint">
            Select a structure for this workflow
          </span>
        </div>
        
        <div className="form-group">
          <label className="form-label">
            Template
          </label>
          {isLoadingTemplates ? (
            <div className="form-hint">Loading templates...</div>
          ) : (
            <select
              className="form-select"
              value={selectedTemplate}
              onChange={(e) => handleTemplateChange(e.target.value)}
            >
              <option value="">— Empty workflow —</option>
              {templates.map((t) => (
                <option key={t.name} value={t.name}>
                  {t.name} ({t.step_types.join(' → ')})
                </option>
              ))}
            </select>
          )}
          <span className="form-hint">
            Optional. Use a template to pre-configure steps.
          </span>
        </div>
        
        {selectedTemplate && templates.find(t => t.name === selectedTemplate) && (
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

