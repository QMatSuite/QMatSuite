/**
 * DemoGalleryPanel - Inline panel for browsing and creating demo projects
 * 
 * Shows available demo project snapshots and allows user to select one
 * and create a project from it. Rendered as part of the Home view, not a modal.
 */

import { useCallback, useEffect, useState } from 'react';
import { useQMSClient } from '../../hooks/useQMSClient';
import type { DemoProjectInfo } from '../../types/qms';
import './DemoGalleryPanel.css';

interface DemoGalleryPanelProps {
  defaultParentDir?: string;
  onBack: () => void;
  onCreateProject: (projectRoot: string, recommendedAnalysis?: string | null) => void;
}

export function DemoGalleryPanel({
  onBack,
  onCreateProject,
}: DemoGalleryPanelProps) {
  const qms = useQMSClient();
  const [demos, setDemos] = useState<DemoProjectInfo[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [creatingDemoId, setCreatingDemoId] = useState<string | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  
  const loadDemos = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    setDemos([]);
    
    try {
      const response = await qms.call('list_demo_projects', {});
      
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
  }, [qms.call]); // Use qms.call instead of qms to avoid infinite loop (call is stable)
  
  // Load demo projects on mount (only once)
  useEffect(() => {
    loadDemos();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Only run on mount, loadDemos is stable
  
  const handleCreateProject = useCallback(async (demo: DemoProjectInfo) => {
    if (!window.qms?.openDirectory) {
      setCreateError('File picker not available');
      return;
    }
    
    // Ask user to select parent directory
    const parentDir = await window.qms.openDirectory();
    
    if (!parentDir) {
      return; // User cancelled
    }
    
    setCreatingDemoId(demo.ulid);
    setCreateError(null);
    
    try {
      // Generate project name from demo title or id
      const projectName = (demo.title || demo.ulid).toLowerCase()
        .replace(/\s+/g, '-')
        .replace(/[^a-z0-9-]/g, '');
      
      const response = await qms.call('create_demo_project', {
        target_dir: parentDir,
        name: projectName,
        demo_id: demo.ulid,
      });
      
      if (response.ok && response.data) {
        const result = response.data;
        onCreateProject(result.project_root, demo.recommended_analysis);
      } else {
        // Show error but keep gallery open - user can try again with different folder
        const errorMsg = response.error?.message || 'Failed to create demo project';
        setCreateError(errorMsg);
      }
    } catch (e) {
      setCreateError(e instanceof Error ? e.message : 'Failed to create demo project');
    } finally {
      setCreatingDemoId(null);
    }
  }, [qms.call, onCreateProject]); // Use qms.call instead of qms to avoid infinite loop
  
  return (
    <div className="demo-gallery-panel" data-testid="qms-demo-gallery-view">
      <div className="demo-gallery-panel__header">
        <button 
          className="demo-gallery-panel__back-btn"
          onClick={onBack}
          data-testid="qms-demo-gallery-back-btn"
        >
          ← Back to Home
        </button>
        <h2 className="demo-gallery-panel__title">Demo Gallery</h2>
      </div>
      
      <div className="demo-gallery-panel__content">
        {isLoading ? (
          <div className="demo-gallery-panel__loading" data-testid="qms-demo-gallery-loading">
            <div className="loading-spinner" />
            <p>Loading demo projects...</p>
          </div>
        ) : error ? (
          <div className="demo-gallery-panel__error" data-testid="qms-demo-gallery-error">
            <div className="error-card">
              <span className="error-icon">⚠️</span>
              <h3>Failed to load demo projects</h3>
              <p className="error-message">{error}</p>
              <button 
                onClick={loadDemos} 
                className="action-button"
                data-testid="qms-demo-gallery-error-retry-btn"
              >
                Retry
              </button>
            </div>
          </div>
        ) : demos.length === 0 ? (
          <div className="demo-gallery-panel__error" data-testid="qms-demo-gallery-empty-state">
            <div className="error-card">
              <span className="error-icon">ℹ️</span>
              <h3>No demo projects available</h3>
              <p className="error-message">No demo projects found. Please check that resources/demo_projects/ contains snapshot files.</p>
              <button 
                onClick={loadDemos} 
                className="action-button"
                data-testid="qms-demo-gallery-empty-retry-btn"
              >
                Retry
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className="demo-gallery-panel__description">
              <p>Choose a demo project to get started. Each demo includes a complete calculation with example calculations.</p>
            </div>
            
            {createError && (
              <div className="demo-gallery-panel__create-error" data-testid="qms-demo-gallery-create-error">
                <span className="error-icon">⚠️</span>
                <span>{createError}</span>
                <button onClick={() => setCreateError(null)}>×</button>
              </div>
            )}
            
            <div className="demo-gallery-panel__demos" data-testid="qms-demo-gallery-cards">
              {demos.map((demo) => (
                <div
                  key={demo.ulid}
                  className="demo-card"
                  data-testid={`qms-demo-card-${demo.ulid.replace(/_/g, '-')}`}
                >
                  <div className="demo-card__header">
                    <div className="demo-card__title-section">
                      <h3 className="demo-card__name">{demo.title || demo.name}</h3>
                      {demo.subtitle && (
                        <p className="demo-card__subtitle">{demo.subtitle}</p>
                      )}
                    </div>
                    <div className="demo-card__tags">
                      {demo.tags && demo.tags.length > 0 ? (
                        demo.tags.map((tag, idx) => (
                          <span key={idx} className="demo-tag" data-testid={`qms-demo-tag-${demo.ulid.replace(/_/g, '-')}-${tag}`}>
                            {tag}
                          </span>
                        ))
                      ) : (
                        <>
                          <span className="demo-tag">{demo.recommended_use}</span>
                          <span className="demo-tag">Silicon</span>
                        </>
                      )}
                      {demo.difficulty && (
                        <span className="demo-tag demo-tag--difficulty" data-testid={`qms-demo-difficulty-${demo.ulid.replace(/_/g, '-')}`}>
                          {demo.difficulty}
                        </span>
                      )}
                    </div>
                  </div>
                  <p className="demo-card__description">{demo.description}</p>
                  <button
                    className="demo-card__create-btn"
                    onClick={() => handleCreateProject(demo)}
                    disabled={creatingDemoId !== null}
                    data-testid={`qms-demo-card-btn-create-${demo.ulid.replace(/_/g, '-')}`}
                  >
                    {creatingDemoId === demo.ulid ? 'Creating...' : 'Create Project'}
                  </button>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

