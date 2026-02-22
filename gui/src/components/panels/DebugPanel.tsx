/**
 * DebugPanel - Shows daemon log output and debug tools
 * Features a resizable panel similar to VS Code's terminal panel.
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { useQMSLogs, useQMSClient } from '../../hooks/useQMSClient';
import type { QMSResponse } from '../../types/qms';
import { getVisibleLogLines, getVisibleLogText } from '../../utils/logFilter';
import './DebugPanel.css';

interface DebugPanelProps {
  isVisible?: boolean;
}

// Min/max heights for the resizable panel
const MIN_HEIGHT = 80;
const MAX_HEIGHT = 500;
const DEFAULT_HEIGHT = 180;

/**
 * Compact log footer panel with resizable height
 */
export function DebugPanel({ isVisible = true }: DebugPanelProps) {
  const allLogs = useQMSLogs(200);
  const scrollRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState(DEFAULT_HEIGHT);
  const [isResizing, setIsResizing] = useState(false);
  const [showPollingLogs, setShowPollingLogs] = useState(false);
  const [copyButtonLabel, setCopyButtonLabel] = useState('Copy');
  
  // Filter logs using shared utility (single source of truth)
  const logs = getVisibleLogLines(allLogs, showPollingLogs);
  
  // Copy handler
  const handleCopyLogs = useCallback(async () => {
    const textToCopy = getVisibleLogText(allLogs, showPollingLogs);
    
    if (!textToCopy) {
      return;
    }
    
    try {
      // Try modern clipboard API first
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(textToCopy);
      } else {
        // Fallback for older browsers/contexts
        const textarea = document.createElement('textarea');
        textarea.value = textToCopy;
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        textarea.style.left = '-999999px';
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
      }
      
      // Show feedback
      setCopyButtonLabel('Copied!');
      setTimeout(() => {
        setCopyButtonLabel('Copy');
      }, 2000);
    } catch (e) {
      console.error('Failed to copy logs:', e);
    }
  }, [allLogs, showPollingLogs]);
  
  // Auto-scroll to bottom on new logs
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);
  
  // Handle resize drag
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
    
    const startY = e.clientY;
    const startHeight = height;
    
    const handleMouseMove = (moveEvent: MouseEvent) => {
      // Dragging up (negative deltaY) should increase height
      const deltaY = startY - moveEvent.clientY;
      const newHeight = Math.max(MIN_HEIGHT, Math.min(MAX_HEIGHT, startHeight + deltaY));
      setHeight(newHeight);
    };
    
    const handleMouseUp = () => {
      setIsResizing(false);
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    
    document.body.style.cursor = 'row-resize';
    document.body.style.userSelect = 'none';
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  }, [height]);
  
  // Use CSS to hide instead of unmounting to preserve log state
  return (
    <div 
      className={`debug-panel ${isResizing ? 'debug-panel--resizing' : ''} ${!isVisible ? 'debug-panel--hidden' : ''}`}
      ref={panelRef}
      style={{ height: isVisible ? `${height}px` : '0px' }}
    >
      {/* Resize Handle */}
      <div 
        className="debug-panel__resize-handle"
        onMouseDown={handleMouseDown}
        title="Drag to resize"
      >
        <div className="debug-panel__resize-grip" />
      </div>
      
      <div className="debug-panel__header">
        <span className="debug-panel__title">🔧 Daemon Logs</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginLeft: 'auto' }}>
          <button
            className="debug-panel__copy-btn"
            onClick={handleCopyLogs}
            disabled={logs.length === 0}
            title="Copy visible logs to clipboard"
            data-testid="qms-dock-daemon-logs-copy"
          >
            {copyButtonLabel}
          </button>
          <label className="debug-panel__filter-toggle" title="Show polling RPC logs (job_counts, list_jobs)">
            <input
              type="checkbox"
              checked={showPollingLogs}
              onChange={(e) => setShowPollingLogs(e.target.checked)}
            />
            <span>Show polling logs</span>
          </label>
          <span className="debug-panel__count">{logs.length} lines</span>
        </div>
      </div>
      <div className="debug-panel__content" ref={scrollRef}>
        {logs.length === 0 ? (
          <div className="debug-panel__empty">
            Waiting for daemon output...
          </div>
        ) : (
          logs.map((log, i) => (
            <div key={i} className="debug-panel__line">
              {log}
            </div>
          ))
        )}
      </div>
    </div>
  );
}

/**
 * Full debug view for the main content area
 */
interface DebugViewProps {
  lastResult: QMSResponse | null;
}

export function DebugView({ lastResult }: DebugViewProps) {
  const qms = useQMSClient();
  const logs = useQMSLogs(500);
  const scrollRef = useRef<HTMLDivElement>(null);
  const [pingResult, setPingResult] = useState<string | null>(null);
  const [isPinging, setIsPinging] = useState(false);
  
  // Auto-scroll logs
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);
  
  const handlePing = useCallback(async () => {
    setIsPinging(true);
    setPingResult(null);
    
    const response = await qms.ping();
    
    if (response.ok && response.data) {
      setPingResult(`✓ Daemon v${response.data.version} (connected)`);
    } else {
      setPingResult(`✗ ${response.error?.message || 'Connection failed'}`);
    }
    setIsPinging(false);
  }, [qms]);
  
  return (
    <div className="debug-view">
      {/* Debug Tools */}
      <div className="debug-view__tools">
        <div className="debug-tools__section">
          <h3 className="debug-tools__title">Connection Test</h3>
          <div className="debug-tools__row">
            <button
              className="debug-tools__button"
              onClick={handlePing}
              disabled={isPinging}
            >
              {isPinging ? '⏳ Pinging...' : '🏓 Ping Daemon'}
            </button>
            {pingResult && (
              <span className={`debug-tools__result ${pingResult.startsWith('✓') ? 'success' : 'error'}`}>
                {pingResult}
              </span>
            )}
          </div>
        </div>
        
        <div className="debug-tools__section">
          <h3 className="debug-tools__title">Daemon Status</h3>
          <div className="debug-tools__info">
            <div className="debug-tools__info-item">
              <span className="info-label">Connected:</span>
              <span className={`info-value ${qms.state.isConnected ? 'success' : 'error'}`}>
                {qms.state.isConnected ? 'Yes' : 'No'}
              </span>
            </div>
            {qms.state.daemonStatus?.pythonPath && (
              <div className="debug-tools__info-item">
                <span className="info-label">Python:</span>
                <code className="info-value">{qms.state.daemonStatus.pythonPath}</code>
              </div>
            )}
            {qms.state.daemonStatus?.projectRoot && (
              <div className="debug-tools__info-item">
                <span className="info-label">CWD:</span>
                <code className="info-value">{qms.state.daemonStatus.projectRoot}</code>
              </div>
            )}
          </div>
        </div>
      </div>
      
      {/* Last Result */}
      {lastResult && (
        <div className="debug-view__result">
          <h3 className="debug-view__section-title">Last RPC Result</h3>
          <div className={`debug-view__json ${lastResult.ok ? 'success' : 'error'}`}>
            <pre>{JSON.stringify(lastResult, null, 2)}</pre>
          </div>
        </div>
      )}
      
      {/* Full Logs */}
      <div className="debug-view__logs">
        <div className="debug-view__logs-header">
          <h3 className="debug-view__section-title">Daemon Logs</h3>
          <span className="debug-view__logs-count">{logs.length} lines</span>
        </div>
        <div className="debug-view__logs-content" ref={scrollRef}>
          {logs.length === 0 ? (
            <div className="debug-view__logs-empty">
              No daemon output yet...
            </div>
          ) : (
            logs.map((log, i) => (
              <div key={i} className="debug-view__log-line">
                <span className="log-number">{i + 1}</span>
                <span className="log-text">{log}</span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
