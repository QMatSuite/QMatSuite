/**
 * AppShell - Main layout wrapper for QuantumVITAS GUI
 * 
 * Provides the overall layout structure with sidebar and main content area.
 */

import { ReactNode } from 'react';
import './AppShell.css';

interface AppShellProps {
  sidebar: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
}

export function AppShell({ sidebar, children, footer }: AppShellProps) {
  return (
    <div className="app-shell">
      <aside className="app-shell__sidebar">
        {sidebar}
      </aside>
      <main className="app-shell__main">
        <div className="app-shell__content">
          {children}
        </div>
        {footer && (
          <footer className="app-shell__footer">
            {footer}
          </footer>
        )}
      </main>
    </div>
  );
}

