/**
 * DebugPanel - Shows daemon log output for debugging
 */

import { useEffect, useRef } from 'react';
import { useQVLogs } from '../../hooks/useQVClient';
import './DebugPanel.css';

interface DebugPanelProps {
  isVisible?: boolean;
}

export function DebugPanel({ isVisible = true }: DebugPanelProps) {
  const logs = useQVLogs(200);
  const scrollRef = useRef<HTMLDivElement>(null);
  
  // Auto-scroll to bottom on new logs
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs]);
  
  if (!isVisible) return null;
  
  return (
    <div className="debug-panel">
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

