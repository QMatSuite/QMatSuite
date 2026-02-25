/**
 * QMatSuite GUI - Main Application Component
 *
 * Provider tree:
 *   AppShellProvider  → UI chrome (view, settings, updater, notifications, dialogs)
 *     ProjectProvider → Project data + CRUD
 *       StructureProvider → Structure viewer + import mode
 *         CalculationProvider → Calculation selection + detail
 *           AppLayout → View rendering + cross-context orchestration
 */

import {
  AppShellProvider,
  ProjectProvider,
  StructureProvider,
  CalculationProvider,
} from './contexts';
import AppLayout from './components/AppLayout';
import './App.css';

function App() {
  return (
    <AppShellProvider>
      <ProjectProvider>
        <StructureProvider>
          <CalculationProvider>
            <AppLayout />
          </CalculationProvider>
        </StructureProvider>
      </ProjectProvider>
    </AppShellProvider>
  );
}

export default App;
