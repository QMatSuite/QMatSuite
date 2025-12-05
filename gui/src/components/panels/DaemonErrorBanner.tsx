/**
 * DaemonErrorBanner - Shows daemon startup errors prominently
 */

import type { DaemonStatus } from '../../types/qv';
import './DaemonErrorBanner.css';

interface DaemonErrorBannerProps {
  status: DaemonStatus | null;
  onDismiss?: () => void;
}

export function DaemonErrorBanner({ status, onDismiss }: DaemonErrorBannerProps) {
  // Don't show if no status or no error
  if (!status || !status.startupError) {
    return null;
  }
  
  return (
    <div className="daemon-error-banner">
      <div className="banner-icon">⚠️</div>
      <div className="banner-content">
        <h4>Daemon Error</h4>
        <p>{status.startupError}</p>
        {status.pythonPath && (
          <div className="banner-detail">
            Python: <code>{status.pythonPath}</code>
          </div>
        )}
        {status.projectRoot && (
          <div className="banner-detail">
            Project: <code>{status.projectRoot}</code>
          </div>
        )}
      </div>
      {onDismiss && (
        <button className="banner-dismiss" onClick={onDismiss}>×</button>
      )}
    </div>
  );
}

