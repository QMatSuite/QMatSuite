/**
 * QuantumVITAS GUI - Main Application Component
 * 
 * Provides the main application layout with:
 * - Sidebar for navigation and actions
 * - Main panel for displaying results
 * - Debug panel for daemon logs
 */

import { useState, useCallback } from 'react';
import { AppShell, Sidebar, ResultPanel, DebugPanel } from './components';
import { useQVClient } from './hooks';
import type { QVResponse } from './types';
import './App.css';

function App() {
  // Project root path state (persisted in localStorage)
  const [projectRoot, setProjectRoot] = useState<string>(() => {
    return localStorage.getItem('qv-project-root') || '';
  });
  
  // Result state
  const [result, setResult] = useState<QVResponse | null>(null);
  
  // Debug panel visibility
  const [showDebug, setShowDebug] = useState(true);
  
  // QV client hook
  const qv = useQVClient();
  
  // Handle project root change
  const handleProjectRootChange = useCallback((path: string) => {
    setProjectRoot(path);
    localStorage.setItem('qv-project-root', path);
  }, []);
  
  // Handle result from daemon
  const handleResult = useCallback((response: unknown) => {
    setResult(response as QVResponse);
  }, []);
  
  return (
    <AppShell
      sidebar={
        <Sidebar
          qv={qv}
          projectRoot={projectRoot}
          onProjectRootChange={handleProjectRootChange}
          onResult={handleResult}
        />
      }
      footer={<DebugPanel isVisible={showDebug} />}
    >
      <div className="app-header">
        <h2 className="app-header__title">Results</h2>
        <div className="app-header__actions">
          <button
            className="app-header__toggle"
            onClick={() => setShowDebug(!showDebug)}
          >
            {showDebug ? '🔽 Hide Logs' : '🔼 Show Logs'}
          </button>
        </div>
      </div>
      <ResultPanel result={result} />
    </AppShell>
  );
}

export default App;
