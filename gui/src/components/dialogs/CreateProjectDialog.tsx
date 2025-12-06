/**
 * CreateProjectDialog - Dialog for creating a new QV project
 */

import { useState, useCallback } from 'react';
import { Modal } from './Modal';
import { useQVClient } from '../../hooks/useQVClient';

interface CreateProjectDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (projectRoot: string) => void;
}

export function CreateProjectDialog({ 
  isOpen, 
  onClose, 
  onSuccess,
}: CreateProjectDialogProps) {
  const qv = useQVClient();
  
  const [targetDir, setTargetDir] = useState('');
  const [projectName, setProjectName] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const handleBrowse = useCallback(async () => {
    if (window.qv?.openDirectory) {
      const path = await window.qv.openDirectory();
      if (path) {
        setTargetDir(path);
        // Auto-fill project name from directory name if empty
        if (!projectName) {
          const dirName = path.split('/').pop() || path.split('\\').pop() || '';
          setProjectName(dirName);
        }
      }
    }
  }, [projectName]);
  
  const handleCreate = useCallback(async () => {
    if (!targetDir) {
      setError('Please select a target directory');
      return;
    }
    
    setIsCreating(true);
    setError(null);
    
    const response = await qv.call('create_project', {
      target_dir: targetDir,
      name: projectName || undefined,
    });
    
    setIsCreating(false);
    
    if (response.ok && response.data) {
      onSuccess(response.data.project_root);
      handleClose();
    } else {
      setError(response.error?.message || 'Failed to create project');
    }
  }, [qv, targetDir, projectName, onSuccess]);
  
  const handleClose = useCallback(() => {
    setTargetDir('');
    setProjectName('');
    setError(null);
    onClose();
  }, [onClose]);
  
  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Create New Project"
      size="medium"
      footer={
        <>
          <button className="btn btn--secondary" onClick={handleClose}>
            Cancel
          </button>
          <button 
            className={`btn btn--primary ${isCreating ? 'btn--loading' : ''}`}
            onClick={handleCreate}
            disabled={isCreating || !targetDir}
          >
            Create Project
          </button>
        </>
      }
    >
      <div className="modal-form">
        <div className="form-group">
          <label className="form-label form-label--required">
            Project Directory
          </label>
          <div className="form-input-group">
            <input
              type="text"
              className="form-input form-input--mono"
              value={targetDir}
              onChange={(e) => setTargetDir(e.target.value)}
              placeholder="/path/to/new-project"
            />
            <button className="form-button" onClick={handleBrowse}>
              📂
            </button>
          </div>
          <span className="form-hint">
            Choose an empty directory or a new directory name
          </span>
        </div>
        
        <div className="form-group">
          <label className="form-label">
            Project Name
          </label>
          <input
            type="text"
            className="form-input"
            value={projectName}
            onChange={(e) => setProjectName(e.target.value)}
            placeholder="My QE Project"
          />
          <span className="form-hint">
            Optional. Defaults to the directory name.
          </span>
        </div>
        
        {error && (
          <div className="form-error">
            ⚠️ {error}
          </div>
        )}
      </div>
    </Modal>
  );
}

