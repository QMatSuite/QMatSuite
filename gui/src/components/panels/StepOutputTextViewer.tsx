/**
 * StepOutputTextViewer - Displays step output file content
 * 
 * Shows text output from step artifact files with support for:
 * - Multiple artifact file selection
 * - File truncation for large files
 * - Monospaced text display
 */

import { useState, useEffect, useCallback } from 'react';
import { useQVClient } from '../../hooks/useQVClient';
import { normalizeProjectRoot } from '../../utils/pathUtils';
import './StepOutputTextViewer.css';

interface StepOutputTextViewerProps {
  projectRoot: string;
  calculation: string; // Calculation selector (slug or ULID)
  stepId: string; // Step ULID
}

interface Artifact {
  path_relative_to_raw: string;
  kind: string;
  size_bytes: number;
  mtime: number;
  is_default_candidate: boolean;
}

export function StepOutputTextViewer({ 
  projectRoot, 
  calculation, 
  stepId 
}: StepOutputTextViewerProps) {
  const qv = useQVClient();
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [selectedArtifact, setSelectedArtifact] = useState<string | null>(null);
  const [content, setContent] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [truncated, setTruncated] = useState(false);
  const [totalBytes, setTotalBytes] = useState<number | null>(null);

  // Load artifacts list
  const loadArtifacts = useCallback(async () => {
    if (!qv || !projectRoot || !calculation || !stepId) return;
    
    setIsLoading(true);
    setError(null);
    
    try {
      const normalizedRoot = normalizeProjectRoot(projectRoot);
      if (!normalizedRoot) return;
      
      const response = await qv.call('list_step_artifacts', {
        project_root: normalizedRoot,
        calculation,
        step: stepId,
      });
      
      if (response.ok && response.data) {
        const artifactsList = response.data.artifacts || [];
        setArtifacts(artifactsList);
        
        // Select default candidate if available
        const defaultArtifact = artifactsList.find((a: Artifact) => a.is_default_candidate);
        if (defaultArtifact) {
          setSelectedArtifact(defaultArtifact.path_relative_to_raw);
        } else if (artifactsList.length > 0) {
          // Fallback to first artifact
          setSelectedArtifact(artifactsList[0].path_relative_to_raw);
        } else {
          setSelectedArtifact(null);
        }
      } else {
        setArtifacts([]);
        setSelectedArtifact(null);
        setError(response.error?.message || 'Failed to load artifacts');
      }
    } catch (e) {
      console.error('Failed to load artifacts', e);
      setArtifacts([]);
      setSelectedArtifact(null);
      setError(e instanceof Error ? e.message : 'Failed to load artifacts');
    } finally {
      setIsLoading(false);
    }
  }, [qv, projectRoot, calculation, stepId]);

  // Load artifact content
  const loadContent = useCallback(async (artifactPath: string) => {
    if (!qv || !projectRoot || !calculation || !stepId) return;
    
    setIsLoading(true);
    setError(null);
    
    try {
      const normalizedRoot = normalizeProjectRoot(projectRoot);
      if (!normalizedRoot) return;
      
      // For large files, show first 1000 lines and last 100 lines
      const response = await qv.call('read_step_artifact_text', {
        project_root: normalizedRoot,
        calculation,
        step: stepId,
        artifact_path: artifactPath,
        head_lines: 1000,
        tail_lines: 100,
      });
      
      if (response.ok && response.data) {
        setContent(response.data.content || '');
        setTruncated(response.data.truncated || false);
        setTotalBytes(response.data.total_bytes || null);
      } else {
        setContent('');
        setError(response.error?.message || 'Failed to read artifact');
      }
    } catch (e) {
      console.error('Failed to load artifact content', e);
      setContent('');
      setError(e instanceof Error ? e.message : 'Failed to read artifact');
    } finally {
      setIsLoading(false);
    }
  }, [qv, projectRoot, calculation, stepId]);

  // Load artifacts on mount and when props change
  useEffect(() => {
    loadArtifacts();
  }, [loadArtifacts]);

  // Load content when selected artifact changes
  useEffect(() => {
    if (selectedArtifact) {
      loadContent(selectedArtifact);
    } else {
      setContent('');
      setTruncated(false);
      setTotalBytes(null);
    }
  }, [selectedArtifact, loadContent]);

  if (isLoading && artifacts.length === 0) {
    return (
      <div className="step-output-viewer step-output-viewer--loading">
        <div className="loading-spinner" />
        <p>Loading artifacts...</p>
      </div>
    );
  }

  if (artifacts.length === 0) {
    return (
      <div className="step-output-viewer step-output-viewer--empty">
        <div className="step-output-placeholder">
          <span className="step-output-icon">📄</span>
          <h3>No Output Files</h3>
          <p>No output files found for this step yet.</p>
          <p className="step-output-hint">The calculation may not have been run yet.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="step-output-viewer" data-testid="qv-step-output-viewer">
      {/* Artifact selector */}
      <div className="step-output-header">
        <div className="step-output-selector">
          <label htmlFor="artifact-select">Output File:</label>
          <select
            id="artifact-select"
            value={selectedArtifact || ''}
            onChange={(e) => setSelectedArtifact(e.target.value)}
            className="artifact-select"
          >
            {artifacts.map((artifact) => (
              <option key={artifact.path_relative_to_raw} value={artifact.path_relative_to_raw}>
                {artifact.path_relative_to_raw}
                {artifact.is_default_candidate ? ' (default)' : ''}
                {artifact.size_bytes > 0 ? ` (${formatFileSize(artifact.size_bytes)})` : ''}
              </option>
            ))}
          </select>
        </div>
        {totalBytes !== null && (
          <div className="step-output-info">
            <span className="file-size">{formatFileSize(totalBytes)}</span>
            {truncated && (
              <span className="truncation-hint" title="File content was truncated">
                (truncated)
              </span>
            )}
          </div>
        )}
      </div>

      {/* Content area */}
      <div className="step-output-content">
        {error ? (
          <div className="step-output-error">
            <span className="error-icon">⚠️</span>
            <p>{error}</p>
          </div>
        ) : isLoading ? (
          <div className="step-output-loading">
            <div className="loading-spinner" />
            <p>Loading file content...</p>
          </div>
        ) : (
          <pre className="step-output-text">{content || '(empty file)'}</pre>
        )}
      </div>
    </div>
  );
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`;
  } else if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  } else {
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }
}

