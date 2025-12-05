/**
 * ProjectSummaryPanel - Displays project overview in a structured format
 */

import type { ProjectSummary } from '../../types/qv';
import './ProjectSummaryPanel.css';

interface ProjectSummaryPanelProps {
  summary: ProjectSummary | null;
  isLoading?: boolean;
}

export function ProjectSummaryPanel({ summary, isLoading }: ProjectSummaryPanelProps) {
  if (isLoading) {
    return (
      <div className="project-summary-panel project-summary-panel--loading">
        <div className="loading-spinner" />
        <p>Loading project...</p>
      </div>
    );
  }
  
  if (!summary) {
    return (
      <div className="project-summary-panel project-summary-panel--empty">
        <div className="panel-placeholder">
          <span className="panel-icon">📁</span>
          <h3>No Project Loaded</h3>
          <p>Enter a project path and click "Load Project" to get started.</p>
        </div>
      </div>
    );
  }
  
  return (
    <div className="project-summary-panel">
      <div className="panel-header">
        <h2 className="panel-title">
          <span className="panel-icon">📁</span>
          {summary.name}
        </h2>
        <span className="panel-badge">{summary.slug}</span>
      </div>
      
      <div className="panel-content">
        <div className="summary-grid">
          <div className="summary-card">
            <div className="summary-card__value">{summary.n_structures}</div>
            <div className="summary-card__label">Structures</div>
            <div className="summary-card__list">
              {summary.structure_names.slice(0, 5).map(name => (
                <span key={name} className="summary-tag">{name}</span>
              ))}
              {summary.structure_names.length > 5 && (
                <span className="summary-tag summary-tag--more">
                  +{summary.structure_names.length - 5} more
                </span>
              )}
            </div>
          </div>
          
          <div className="summary-card">
            <div className="summary-card__value">{summary.n_workflows}</div>
            <div className="summary-card__label">Workflows</div>
            <div className="summary-card__list">
              {summary.workflow_names.slice(0, 5).map(name => (
                <span key={name} className="summary-tag">{name}</span>
              ))}
              {summary.workflow_names.length > 5 && (
                <span className="summary-tag summary-tag--more">
                  +{summary.workflow_names.length - 5} more
                </span>
              )}
            </div>
          </div>
        </div>
        
        <div className="summary-details">
          <div className="detail-row">
            <span className="detail-label">Project ID</span>
            <code className="detail-value">{summary.id}</code>
          </div>
          <div className="detail-row">
            <span className="detail-label">Path</span>
            <code className="detail-value detail-value--path">{summary.path}</code>
          </div>
        </div>
      </div>
    </div>
  );
}

