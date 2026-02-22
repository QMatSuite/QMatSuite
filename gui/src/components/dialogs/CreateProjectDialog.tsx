/**
 * CreateProjectDialog - Dialog for creating a new QMS project
 * 
 * Uses parent directory + project name approach:
 * - User picks a parent directory (default: from settings)
 * - User enters project name
 * - Final project will be created as <parent>/<project-slug>
 * 
 * Also handles "Create Demo Project" flow when isDemoProject is true.
 */

import { useState, useCallback, useEffect, useMemo } from 'react';
import { Modal } from './Modal';
import { useQMSClient } from '../../hooks/useQMSClient';
import type { DemoProjectResult } from '../../types/qms';
import './CreateProjectDialog.css';

interface CreateProjectDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (projectRoot: string) => void;
  /** If true, creates a demo Si project instead of empty project */
  isDemoProject?: boolean;
  /** Default parent directory from app settings */
  defaultParentDir?: string;
}

// Simple slug generator
function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^\w\s-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-+|-+$/g, '');
}

export function CreateProjectDialog({ 
  isOpen, 
  onClose, 
  onSuccess,
  isDemoProject = false,
  defaultParentDir = '',
}: CreateProjectDialogProps) {
  const qms = useQMSClient();
  
  const [parentDir, setParentDir] = useState(defaultParentDir);
  const [projectName, setProjectName] = useState(isDemoProject ? 'demo-si-project' : 'my-project');
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  // Reset form when dialog opens
  useEffect(() => {
    if (isOpen) {
      setParentDir(defaultParentDir);
      setProjectName(isDemoProject ? 'demo-si-project' : 'my-project');
      setError(null);
    }
  }, [isOpen, isDemoProject, defaultParentDir]);
  
  // Compute the final project path preview
  const projectSlug = useMemo(() => slugify(projectName), [projectName]);
  const previewPath = useMemo(() => {
    if (!parentDir || !projectSlug) return '';
    // Handle both Unix and Windows path separators
    const separator = parentDir.includes('\\') ? '\\' : '/';
    return `${parentDir}${separator}${projectSlug}`;
  }, [parentDir, projectSlug]);
  
  const handleBrowseParent = useCallback(async () => {
    if (window.qms?.openDirectory) {
      const path = await window.qms.openDirectory();
      if (path) {
        setParentDir(path);
      }
    }
  }, []);
  
  const handleCreate = useCallback(async () => {
    if (!parentDir) {
      setError('Please select a parent directory');
      return;
    }
    if (!projectName.trim()) {
      setError('Please enter a project name');
      return;
    }
    
    setIsCreating(true);
    setError(null);
    
    // The final target directory is parent/slug
    const finalTargetDir = previewPath;
    
    if (isDemoProject) {
      // Create demo project
      const response = await qms.call('create_demo_project', {
        target_dir: parentDir,
        name: projectSlug,
      });
      
      setIsCreating(false);
      
      if (response.ok && response.data) {
        const result = response.data as DemoProjectResult;
        onSuccess(result.project_root);
        handleClose();
      } else {
        setError(response.error?.message || 'Failed to create demo project');
      }
    } else {
      // Create empty project
      const response = await qms.call('create_project', {
        target_dir: finalTargetDir,
        name: projectName.trim(),
      });
      
      setIsCreating(false);
      
      if (response.ok && response.data) {
        onSuccess(response.data.project_root);
        handleClose();
      } else {
        // Show error but keep dialog open (for validation errors like "inside existing project")
        const errorMsg = response.error?.message || 'Failed to create project';
        setError(errorMsg);
        // Don't close dialog - let user fix the folder choice
      }
    }
  }, [qms, parentDir, projectName, projectSlug, previewPath, isDemoProject, onSuccess]);
  
  const handleClose = useCallback(() => {
    setParentDir('');
    setProjectName('');
    setError(null);
    onClose();
  }, [onClose]);
  
  const title = isDemoProject ? 'Create Demo Project' : 'Create New Project';
  const description = isDemoProject 
    ? 'Create a demo Silicon project with a ready-to-run SCF/DOS calculation.'
    : 'Create a new QMatSuite project in the specified location.';
  
  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title={title}
      size="medium"
      footer={
        <>
          <button className="btn btn--secondary" onClick={handleClose} data-testid="qms-btn-cancel-create">
            Cancel
          </button>
          <button 
            className={`btn btn--primary ${isCreating ? 'btn--loading' : ''}`}
            onClick={handleCreate}
            disabled={isCreating || !parentDir || !projectName.trim()}
            data-testid="qms-btn-confirm-create"
          >
            {isDemoProject ? 'Create Demo' : 'Create Project'}
          </button>
        </>
      }
    >
      <div className="modal-form" data-testid="qms-create-project-dialog">
        <p className="form-description">{description}</p>
        
        <div className="form-group">
          <label className="form-label form-label--required">
            Parent Directory
          </label>
          <div className="form-input-group">
            <input
              type="text"
              className="form-input form-input--mono"
              value={parentDir}
              onChange={(e) => setParentDir(e.target.value)}
              placeholder="/path/to/projects"
              data-testid="qms-input-parent-dir"
            />
            <button className="form-button" onClick={handleBrowseParent}>
              📂
            </button>
          </div>
          <span className="form-hint">
            Select the folder where your project will be created
          </span>
        </div>
        
        <div className="form-group">
          <label className="form-label form-label--required">
            Project Name
          </label>
          <input
            type="text"
            className="form-input"
            value={projectName}
            onChange={(e) => setProjectName(e.target.value)}
            placeholder="my-project"
            data-testid="qms-input-project-name"
          />
          <span className="form-hint">
            A folder with this name will be created in the parent directory
          </span>
        </div>
        
        {/* Preview Path */}
        {previewPath && (
          <div className="form-preview" data-testid="qms-project-preview-path">
            <span className="form-preview__label">Project will be created at:</span>
            <code className="form-preview__path">{previewPath}</code>
          </div>
        )}
        
        {error && (
          <div className="form-error" data-testid="qms-create-project-error">
            ⚠️ {error}
          </div>
        )}
      </div>
    </Modal>
  );
}
