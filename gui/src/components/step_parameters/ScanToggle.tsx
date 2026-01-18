/**
 * ScanToggle - Toggle button for enabling/disabling parameter scan.
 */

import './ScanToggle.css';

interface ScanToggleProps {
  isScanned: boolean;
  onChange: (enabled: boolean) => void;
  disabled?: boolean;
  title?: string;
}

export function ScanToggle({
  isScanned,
  onChange,
  disabled = false,
  title,
}: ScanToggleProps) {
  return (
    <button
      className={`scan-toggle ${isScanned ? 'scan-toggle--active' : ''}`}
      onClick={() => onChange(!isScanned)}
      disabled={disabled}
      title={title || (isScanned ? 'Disable scan' : 'Enable scan')}
      type="button"
    >
      <span className="scan-toggle__icon">📊</span>
      <span className="scan-toggle__label">{isScanned ? 'Scan' : 'Value'}</span>
    </button>
  );
}

