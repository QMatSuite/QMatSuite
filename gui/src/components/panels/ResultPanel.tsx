/**
 * ResultPanel - Displays JSON results from daemon calls
 * 
 * Shows formatted JSON with syntax highlighting and status indicators.
 */

import type { QVResponse } from '../../types/qv';
import './ResultPanel.css';

interface ResultPanelProps {
  result: QVResponse | null;
}

export function ResultPanel({ result }: ResultPanelProps) {
  if (!result) {
    return (
      <div className="result-panel result-panel--empty">
        <div className="result-panel__placeholder">
          <span className="result-panel__icon">📊</span>
          <h2>No Results Yet</h2>
          <p>Click an action in the sidebar to see results here.</p>
        </div>
      </div>
    );
  }
  
  return (
    <div className={`result-panel ${result.ok ? 'result-panel--success' : 'result-panel--error'}`}>
      {/* Header */}
      <div className="result-panel__header">
        <div className="result-panel__status">
          <span className={`result-panel__badge ${result.ok ? 'badge--success' : 'badge--error'}`}>
            {result.ok ? '✓ Success' : '✗ Error'}
          </span>
          <span className="result-panel__id">ID: {result.id}</span>
        </div>
      </div>
      
      {/* Content */}
      <div className="result-panel__content">
        {result.ok ? (
          <JsonView data={result.data} />
        ) : (
          <div className="result-panel__error">
            <h3>Error: {result.error?.code || 'unknown'}</h3>
            <p>{result.error?.message || 'An unknown error occurred'}</p>
          </div>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// JSON Viewer Component
// =============================================================================

interface JsonViewProps {
  data: unknown;
  depth?: number;
}

function JsonView({ data, depth = 0 }: JsonViewProps) {
  if (data === null) {
    return <span className="json-null">null</span>;
  }
  
  if (data === undefined) {
    return <span className="json-undefined">undefined</span>;
  }
  
  if (typeof data === 'boolean') {
    return <span className="json-boolean">{data.toString()}</span>;
  }
  
  if (typeof data === 'number') {
    return <span className="json-number">{data}</span>;
  }
  
  if (typeof data === 'string') {
    return <span className="json-string">"{data}"</span>;
  }
  
  if (Array.isArray(data)) {
    if (data.length === 0) {
      return <span className="json-bracket">[]</span>;
    }
    
    // Check if it's an array of primitives (for compact display)
    const allPrimitive = data.every(item => 
      typeof item === 'string' || typeof item === 'number' || typeof item === 'boolean'
    );
    
    if (allPrimitive && data.length <= 10) {
      return (
        <span className="json-array json-array--inline">
          <span className="json-bracket">[</span>
          {data.map((item, i) => (
            <span key={i}>
              <JsonView data={item} depth={depth + 1} />
              {i < data.length - 1 && <span className="json-comma">, </span>}
            </span>
          ))}
          <span className="json-bracket">]</span>
        </span>
      );
    }
    
    return (
      <div className="json-array">
        <span className="json-bracket">[</span>
        <div className="json-indent">
          {data.map((item, i) => (
            <div key={i} className="json-item">
              <JsonView data={item} depth={depth + 1} />
              {i < data.length - 1 && <span className="json-comma">,</span>}
            </div>
          ))}
        </div>
        <span className="json-bracket">]</span>
      </div>
    );
  }
  
  if (typeof data === 'object') {
    const entries = Object.entries(data as Record<string, unknown>);
    
    if (entries.length === 0) {
      return <span className="json-bracket">{'{}'}</span>;
    }
    
    return (
      <div className="json-object">
        <span className="json-bracket">{'{'}</span>
        <div className="json-indent">
          {entries.map(([key, value], i) => (
            <div key={key} className="json-property">
              <span className="json-key">"{key}"</span>
              <span className="json-colon">: </span>
              <JsonView data={value} depth={depth + 1} />
              {i < entries.length - 1 && <span className="json-comma">,</span>}
            </div>
          ))}
        </div>
        <span className="json-bracket">{'}'}</span>
      </div>
    );
  }
  
  return <span>{String(data)}</span>;
}

