/**
 * AppShell - Main layout wrapper for QMatSuite GUI
 * 
 * Provides the overall layout structure with sidebar, main content, 
 * optional footer (debug panel), and status bar.
 */

import { ReactNode } from 'react';
import './AppShell.css';

interface AppShellProps {
  sidebar: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  statusBar?: ReactNode;
}

export function AppShell({ sidebar, children, footer, statusBar }: AppShellProps) {
  return (
    <div className="app-shell">
      <aside className="app-shell__sidebar">
        {sidebar}
      </aside>
      <div className="app-shell__body">
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
        {statusBar && (
          <div className="app-shell__status-bar">
            {statusBar}
          </div>
        )}
      </div>
    </div>
  );
}
