/**
 * DebugPanel - Shows daemon log output and debug tools
 * Features a resizable panel similar to VS Code's terminal panel.
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { useQVLogs, useQVClient } from '../../hooks/useQVClient';
import type { QVResponse } from '../../types/qv';
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
  const logs = useQVLogs(200);
  const scrollRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const [height, setHeight] = useState(DEFAULT_HEIGHT);
  const [isResizing, setIsResizing] = useState(false);
  
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
  
  if (!isVisible) return null;
  
  return (
    <div 
      className={`debug-panel ${isResizing ? 'debug-panel--resizing' : ''}`}
      ref={panelRef}
      style={{ height: `${height}px` }}
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
        <span className="debug-panel__count">{logs.length} lines</span>
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
  lastResult: QVResponse | null;
}

export function DebugView({ lastResult }: DebugViewProps) {
  const qv = useQVClient();
  const logs = useQVLogs(500);
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
    
    const response = await qv.ping();
    
    if (response.ok && response.data) {
      setPingResult(`✓ Daemon v${response.data.version} (connected)`);
    } else {
      setPingResult(`✗ ${response.error?.message || 'Connection failed'}`);
    }
    setIsPinging(false);
  }, [qv]);
  
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
              <span className={`info-value ${qv.state.isConnected ? 'success' : 'error'}`}>
                {qv.state.isConnected ? 'Yes' : 'No'}
              </span>
            </div>
            {qv.state.daemonStatus?.pythonPath && (
              <div className="debug-tools__info-item">
                <span className="info-label">Python:</span>
                <code className="info-value">{qv.state.daemonStatus.pythonPath}</code>
              </div>
            )}
            {qv.state.daemonStatus?.projectRoot && (
              <div className="debug-tools__info-item">
                <span className="info-label">CWD:</span>
                <code className="info-value">{qv.state.daemonStatus.projectRoot}</code>
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
