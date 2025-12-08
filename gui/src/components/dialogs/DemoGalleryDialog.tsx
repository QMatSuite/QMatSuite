/**
 * DemoGalleryDialog - Modal dialog for browsing and creating demo projects
 * 
 * Shows available demo project snapshots and allows user to select one
 * and create a project from it.
 */

import { useCallback, useEffect, useState } from 'react';
import { useQVClient } from '../../hooks/useQVClient';
import type { DemoProjectInfo } from '../../types/qv';
import { Modal } from './Modal';
import './DemoGalleryDialog.css';

interface DemoGalleryDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (projectRoot: string) => void;
  defaultParentDir?: string;
}

export function DemoGalleryDialog({
  isOpen,
  onClose,
  onSuccess,
  defaultParentDir = '',
}: DemoGalleryDialogProps) {
  const qv = useQVClient();
  const [demos, setDemos] = useState<DemoProjectInfo[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedDemo, setSelectedDemo] = useState<DemoProjectInfo | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [parentDir, setParentDir] = useState(defaultParentDir);
  
  const loadDemos = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    setDemos([]);
    
    try {
      const response = await qv.call('list_demo_projects', {});
      
      // Always set loading to false, even on error
      setIsLoading(false);
      
      if (response.ok && response.data) {
        // Daemon returns {demos: [...], count: N}
        const demosList = response.data.demos || [];
        setDemos(demosList);
        if (demosList.length === 0) {
          setError('No demo projects found. Please check that resources/demo_projects/ contains snapshot files.');
        }
      } else {
        // RPC returned error
        setError(response.error?.message || 'Failed to load demo projects');
        setDemos([]);
      }
    } catch (e) {
      // Network/JSON parsing error - ensure loading is false
      setIsLoading(false);
      setError(e instanceof Error ? e.message : 'Failed to load demo projects');
      setDemos([]);
    }
  }, [qv]);
  
  // Load demo projects when dialog opens
  useEffect(() => {
    if (isOpen) {
      loadDemos();
      setParentDir(defaultParentDir);
      setError(null);
      setSelectedDemo(null);
    }
  }, [isOpen, defaultParentDir, loadDemos]);
  
  const handleBrowseParent = useCallback(async () => {
    if (window.qv?.openDirectory) {
      const path = await window.qv.openDirectory();
      if (path) {
        setParentDir(path);
      }
    }
  }, []);
  
  const handleSelectDemo = useCallback((demo: DemoProjectInfo) => {
    setSelectedDemo(demo);
    setError(null);
  }, []);
  
  const handleCreate = useCallback(async () => {
    if (!selectedDemo) {
      setError('Please select a demo project');
      return;
    }
    if (!parentDir) {
      setError('Please select a workspace folder');
      return;
    }
    
    setIsCreating(true);
    setError(null);
    
    try {
      // Generate project name from demo name
      const projectName = selectedDemo.name.toLowerCase()
        .replace(/\s+/g, '-')
        .replace(/[^a-z0-9-]/g, '');
      
      const response = await qv.call('create_demo_project', {
        target_dir: parentDir,
        name: projectName,
        demo_id: selectedDemo.id,
      });
      
      if (response.ok && response.data) {
        const result = response.data;
        onSuccess(result.project_root);
        onClose();
      } else {
        // Show error but keep dialog open
        setError(response.error?.message || 'Failed to create demo project');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create demo project');
    } finally {
      setIsCreating(false);
    }
  }, [selectedDemo, parentDir, qv, onSuccess, onClose]);
  
  const handleClose = useCallback(() => {
    setSelectedDemo(null);
    setParentDir('');
    setError(null);
    onClose();
  }, [onClose]);
  
  return (
    <Modal
      isOpen={isOpen}
      onClose={handleClose}
      title="Demo Gallery"
      size="large"
    >
      <div className="demo-gallery-dialog__content">
        {isLoading ? (
          <div className="demo-gallery-dialog__loading" data-testid="qv-demo-gallery-loading">
            <div className="loading-spinner" />
            <p>Loading demo projects...</p>
          </div>
        ) : error ? (
          <div className="demo-gallery-dialog__error" data-testid="qv-demo-gallery-error-state">
            <p>{error}</p>
            <button onClick={loadDemos} data-testid="qv-demo-gallery-retry-btn">Retry</button>
          </div>
        ) : demos.length === 0 ? (
          <div className="demo-gallery-dialog__error" data-testid="qv-demo-gallery-empty-state">
            <p>No demo projects available.</p>
            <button onClick={loadDemos} data-testid="qv-demo-gallery-retry-btn">Retry</button>
          </div>
        ) : (
          <>
            <div className="demo-gallery-dialog__description">
              <p>Choose a demo project to get started. Each demo includes a complete workflow with example calculations.</p>
            </div>
            
            <div className="demo-gallery-dialog__demos" data-testid="qv-demo-gallery-cards">
              {demos.map((demo) => (
                <div
                  key={demo.id}
                  className={`demo-card ${selectedDemo?.id === demo.id ? 'demo-card--selected' : ''}`}
                  data-testid={`qv-demo-card-${demo.id}`}
                  onClick={() => handleSelectDemo(demo)}
                >
                  <div className="demo-card__header">
                    <h3 className="demo-card__name">{demo.name}</h3>
                    <div className="demo-card__tags">
                      <span className="demo-tag">{demo.recommended_use}</span>
                      <span className="demo-tag">Silicon</span>
                      <span className="demo-tag">Beginner</span>
                    </div>
                  </div>
                  <p className="demo-card__description">{demo.description}</p>
                  {selectedDemo?.id === demo.id && (
                    <div className="demo-card__selected-indicator">✓ Selected</div>
                  )}
                </div>
              ))}
            </div>
            
            <div className="demo-gallery-dialog__workspace">
              <label className="demo-gallery-dialog__label">
                Workspace Folder
              </label>
              <div className="demo-gallery-dialog__workspace-input">
                <input
                  type="text"
                  value={parentDir}
                  onChange={(e) => setParentDir(e.target.value)}
                  placeholder="Select a folder to create the project in"
                  data-testid="qv-demo-gallery-workspace-input"
                />
                <button
                  onClick={handleBrowseParent}
                  data-testid="qv-demo-gallery-browse-btn"
                >
                  Browse...
                </button>
              </div>
            </div>
            
            {error && (
              <div className="demo-gallery-dialog__error" data-testid="qv-demo-gallery-error">
                <p>{error}</p>
              </div>
            )}
            
            <div className="demo-gallery-dialog__actions">
              <button
                className="demo-gallery-dialog__button demo-gallery-dialog__button--secondary"
                onClick={handleClose}
                disabled={isCreating}
              >
                Cancel
              </button>
              <button
                className="demo-gallery-dialog__button demo-gallery-dialog__button--primary"
                onClick={handleCreate}
                disabled={!selectedDemo || !parentDir || isCreating}
                data-testid="qv-demo-gallery-create-btn"
              >
                {isCreating ? 'Creating...' : 'Create Project'}
              </button>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
}

