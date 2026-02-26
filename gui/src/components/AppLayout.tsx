/**
 * AppLayout — View rendering + cross-context orchestration
 *
 * Consumes all 4 contexts. Contains:
 * - Cross-context orchestration callbacks
 * - renderMainContent() view switch
 * - AppShell / Sidebar / StatusBar / header / ErrorBoundary / dialogs
 */

import { useCallback, useRef } from 'react';
import { useQMSClient, useDaemonStatus } from '../hooks';
import { useJobs } from '../hooks/useJobs';
import { useAppShell, useProject, useStructure, useCalculation } from '../contexts';
import {
  AppShell,
  Sidebar,
  StatusBar,
  ResizablePane,
  type ResizablePaneRef,
  ResizableSplitPane,
  ProjectSummaryPanel,
  StructureListPanel,
  StructureDetailPanel,
  CalculationListPanel,
  StructureViewer3D,
  DebugPanel,
  DaemonErrorBanner,
  CreateProjectDialog,
  ImportStructureDialog,
  CreateCalculationDialog,
  RenameDialog,
  DeleteConfirmDialog,
  JobsPanel,
  SettingsPanel,
  HistoryPanel,
  EngineParameterBrowserPanel,
  ErrorBoundary,
  CalculationOverviewTab,
  CalculationRunTab,
  CalculationAnalysisTab,
  VolumeViewerSandbox,
} from '../components';
import type { CalculationDetailResult, RightSelection } from '../types';

export default function AppLayout() {
  // --- Contexts -------------------------------------------------------------
  const shell = useAppShell();
  const project = useProject();
  const structure = useStructure();
  const calc = useCalculation();
  const qms = useQMSClient();
  const daemonStatus = useDaemonStatus();
  const { counts: jobCounts } = useJobs({ autoStart: true, pollInterval: 5000 });

  // --- Refs -----------------------------------------------------------------
  const calculationsPaneRef = useRef<ResizablePaneRef>(null);

  const handleToggleCalculationsPane = useCallback(() => {
    calculationsPaneRef.current?.toggle();
  }, []);

  // --- Cross-context orchestration ------------------------------------------

  // Open recent project: clear calc+struct selection, then delegate to project
  const handleOpenRecentProject = useCallback(async (path: string) => {
    calc.setSelectedCalculationSummary(null);
    calc.setSelectedCalculationDetail(null);
    calc.setSelectedStepId(null);
    structure.setSelectedStructure(null);
    await project.handleOpenRecentProject(path);
  }, [calc, structure, project]);

  // Browse and load: same pattern
  const handleBrowseAndLoad = useCallback(async () => {
    calc.setSelectedCalculationSummary(null);
    calc.setSelectedCalculationDetail(null);
    calc.setSelectedStepId(null);
    structure.setSelectedStructure(null);
    await project.handleBrowseAndLoad();
  }, [calc, structure, project]);

  // Create project success: clear selections, delegate to project
  const handleCreateProjectSuccess = useCallback(async (newProjectRoot: string) => {
    calc.setSelectedCalculationSummary(null);
    calc.setSelectedCalculationDetail(null);
    calc.setSelectedStepId(null);
    structure.setSelectedStructure(null);
    await project.handleCreateProjectSuccess(newProjectRoot);
  }, [calc, structure, project]);

  // Close project: clear all state across all contexts
  const handleCloseProject = useCallback(() => {
    project.handleCloseProject();
    structure.setSelectedStructure(null);
    structure.setCurrentStructureModel(null);
    structure.setStructureVisData(null);
    calc.setSelectedCalculationSummary(null);
    calc.setSelectedCalculationDetail(null);
    calc.setSelectedStepId(null);
    shell.setCurrentView('home');
  }, [project, structure, calc, shell]);

  // Import structure success: refresh + select
  const handleImportStructureSuccess = useCallback(async (structureId: string) => {
    await project.fetchStructures();
    await project.refreshSummary();
    if (project.structures) {
      const newStruct = project.structures.find(s => s.ulid === structureId);
      if (newStruct) {
        structure.handleSelectStructure(newStruct);
      }
    }
  }, [project, structure]);

  // Create calculation success: rebuild + fetch + select
  const handleCreateCalculationSuccess = useCallback(async (calculationId: string) => {
    const rebuildResponse = await qms.call('rebuild_project_registry', {
      project_root: project.projectRoot,
    });

    if (!rebuildResponse.ok) {
      console.error('[AppLayout] Failed to rebuild registry after calculation creation', rebuildResponse.error);
    }

    await project.refreshSummary();
    const calculationsList = await project.fetchCalculations();

    let newWf = calculationsList?.find(w => w.calc_ulid === calculationId);

    if (!newWf) {
      for (let i = 0; i < 3; i++) {
        await new Promise(resolve => setTimeout(resolve, 100));
        const retryList = await project.fetchCalculations();
        newWf = retryList?.find(w => w.calc_ulid === calculationId);
        if (newWf) break;
      }
    }

    if (newWf) {
      calc.handleSelectCalculation(newWf);
    } else {
      console.error('[AppLayout] Created calculation not found after refresh', { calculationId });
    }
  }, [qms, project, calc]);

  // View analysis from Jobs panel
  const handleViewAnalysisFromJob = useCallback(async (calculationSlug: string) => {
    shell.setCurrentView('calculations');

    if (!project.calculations) {
      await project.fetchCalculations();
    }

    const wf = project.calculations?.find(w => w.slug === calculationSlug || w.name === calculationSlug);
    if (wf) {
      calc.handleSelectCalculation(wf);
      calc.setActiveCalcTab('analysis');
    }
  }, [shell, project, calc]);

  // Navigate to structure
  const handleNavigateToStructure = useCallback(async (structureName: string) => {
    shell.setCurrentView('structures');
    if (!structureName) return;

    let currentStructures = project.structures;
    if (!currentStructures) {
      const response = await qms.listStructures(project.projectRoot);
      if (response.ok && response.data) {
        currentStructures = response.data.structures;
        project.setStructures(currentStructures);
      }
    }

    if (currentStructures) {
      const struct = currentStructures.find(s => s.name === structureName || s.slug === structureName);
      if (struct) {
        structure.handleSelectStructure(struct);
      }
    }
  }, [shell, project, structure, qms]);

  // Navigate to calculation
  const handleNavigateToCalculation = useCallback(async (calculationName: string) => {
    shell.setCurrentView('calculations');
    if (!calculationName) return;

    let currentCalculations = project.calculations;
    if (!currentCalculations) {
      const response = await qms.listCalculations(project.projectRoot);
      if (response.ok && response.data) {
        currentCalculations = response.data.calculations;
        project.setCalculations(currentCalculations);
      }
    }

    if (currentCalculations) {
      const wf = currentCalculations.find(w => w.name === calculationName || w.slug === calculationName);
      if (wf) {
        calc.handleSelectCalculation(wf);
      }
    }
  }, [shell, project, calc, qms]);

  // CRUD completion: clear selection if the renamed/deleted item was selected
  const handleRenameStructure = useCallback(async (newName: string): Promise<boolean> => {
    const wasSelected = structure.selectedStructure?.ulid === project.renameStructure?.ulid;
    const ok = await project.handleRenameStructure(newName);
    if (ok && wasSelected) {
      structure.setSelectedStructure(null);
      structure.setStructureVisData(null);
    }
    return ok;
  }, [project, structure]);

  const handleDeleteStructure = useCallback(async (force: boolean): Promise<boolean> => {
    const wasSelected = structure.selectedStructure?.ulid === project.deleteStructure?.ulid;
    const ok = await project.handleDeleteStructure(force);
    if (ok && wasSelected) {
      structure.setSelectedStructure(null);
      structure.setStructureVisData(null);
    }
    return ok;
  }, [project, structure]);

  const handleRenameCalculation = useCallback(async (newName: string): Promise<boolean> => {
    const wasSelected = calc.selectedCalculation?.calc_ulid === project.renameCalculation?.calc_ulid;
    const ok = await project.handleRenameCalculation(newName);
    if (ok && wasSelected) {
      calc.setSelectedCalculationSummary(null);
      calc.setSelectedCalculationDetail(null);
      calc.setSelectedStepId(null);
    }
    return ok;
  }, [project, calc]);

  const handleDeleteCalculation = useCallback(async (force: boolean): Promise<boolean> => {
    const wasSelected = calc.selectedCalculation?.calc_ulid === project.deleteCalculation?.calc_ulid;
    const ok = await project.handleDeleteCalculation(force);
    if (ok && wasSelected) {
      calc.setSelectedCalculationSummary(null);
      calc.setSelectedCalculationDetail(null);
      calc.setSelectedStepId(null);
    }
    return ok;
  }, [project, calc]);

  // --- Render helpers -------------------------------------------------------

  const renderNoProjectMessage = () => (
    <div className="no-project-message">
      <div className="no-project-content">
        <span className="no-project-icon">📦</span>
        <h3>No Project Loaded</h3>
        <p>Load or create a project to view this section.</p>
        <div className="no-project-actions">
          <button className="action-btn" onClick={handleBrowseAndLoad}>
            📂 Browse & Load
          </button>
          <button className="action-btn action-btn--secondary" onClick={() => shell.setShowCreateProject(true)}>
            ✨ Create Project
          </button>
        </div>
      </div>
    </div>
  );

  const renderMainContent = () => {
    switch (shell.currentView) {
      case 'home':
        return (
          <ProjectSummaryPanel
            summary={project.projectSummary}
            isLoading={project.isLoadingProject}
            error={project.projectError}
            recentProjects={shell.recentProjects}
            homeMode={shell.homeMode}
            onHomeModeChange={shell.setHomeMode}
            onBrowseAndLoad={handleBrowseAndLoad}
            onCreateProject={() => shell.setShowCreateProject(true)}
            onOpenDemoGallery={shell.handleOpenDemoGallery}
            onOpenRecentProject={handleOpenRecentProject}
            onRemoveRecentProject={shell.removeFromRecentProjects}
            onNavigateToStructure={handleNavigateToStructure}
            onNavigateToCalculation={handleNavigateToCalculation}
            onCloseProject={handleCloseProject}
            onProjectCreated={handleCreateProjectSuccess}
          />
        );

      case 'structures':
        if (!project.projectLoaded) return renderNoProjectMessage();
        return (
          <div className="structures-view">
            <ResizablePane
              defaultWidth={400}
              minWidth={300}
              maxWidth={550}
              storageKey="qms-structures-list-width"
              className="structures-view__list"
            >
              <StructureListPanel
                onRefreshProjectRegistry={project.handleRefreshProjectRegistry}
                structures={project.structures}
                isLoading={project.isLoadingStructures}
                selectedId={structure.leftMode === 'project' ? structure.selectedStructure?.ulid : null}
                onSelect={structure.leftMode === 'project' ? structure.handleSelectStructure : undefined}
                onRename={project.setRenameStructure}
                onDelete={project.setDeleteStructure}
                projectRoot={project.projectRoot}
                leftMode={structure.leftMode}
                onEnterImportMode={structure.handleEnterImportMode}
                onExitImportMode={structure.handleExitImportMode}
                onSelectOnlineCandidate={structure.handleSelectOnlineCandidate}
                selectedOnlineCandidateId={structure.selectedOnlineCandidateId}
                onlineSessionId={structure.onlineSessionId}
                onlineCandidates={structure.onlineCandidates}
              />
              {structure.leftMode === 'project' && (
                <button
                  className="view-action-btn"
                  onClick={() => shell.setShowImportStructure(true)}
                  data-testid="qms-btn-import-structure"
                >
                  ➕ Import Structure
                </button>
              )}
            </ResizablePane>
            {structure.currentStructureModel ? (
              <div className="structures-view__detail">
                <ResizableSplitPane
                  storageKey="qms.structures.detailsHeightPx"
                  defaultTopHeight={260}
                  minTopHeight={180}
                  minBottomHeight={360}
                  top={
                    <div className="structures-view__detail-panel-wrapper" data-testid="qms-structure-detail">
                      <StructureDetailPanel
                        model={structure.currentStructureModel}
                        onClose={structure.leftMode === 'project' ? () => {
                          structure.setSelectedStructure(null);
                          structure.setStructureVisData(null);
                          structure.setCurrentStructureModel(null);
                          structure.setRightSelection(null);
                          structure.setStructureLoadError(null);
                        } : undefined}
                      />
                    </div>
                  }
                  bottom={
                    <div className="structures-view__3d-wrapper" data-testid="qms-structure-viewer">
                      <StructureViewer3D
                        data={structure.currentStructureModel.vis || null}
                        isLoading={structure.isLoading3D || structure.isStructureLoading}
                        showBonds={structure.viewerSettings.showBonds}
                        showUnitCell={structure.viewerSettings.showUnitCell}
                        showLabels={structure.viewerSettings.showLabels}
                        atomScale={structure.viewerSettings.atomScale}
                        bondScale={structure.viewerSettings.bondScale}
                        structureId={structure.currentStructureModel.id}
                        onSupercellChange={(supercell) => {
                          structure.setViewerSettings(prev => ({ ...prev, supercell }));
                          if (structure.leftMode === 'project') {
                            structure.setCurrentSupercell(supercell);
                          }
                        }}
                        onRepeatBoundaryChange={(repeat) => {
                          structure.setViewerSettings(prev => ({ ...prev, repeatBoundary: repeat }));
                          if (structure.leftMode === 'project') {
                            structure.setCurrentRepeatBoundary(repeat);
                          }
                        }}
                        onDisplayModeChange={(mode) => {
                          const selectionKey = structure.rightSelection ? (structure.rightSelection.kind === 'project' ? `project:${structure.rightSelection.structureId}` : `online:${structure.rightSelection.sessionId}:${structure.rightSelection.candidateId}`) : 'none';
                          console.log('[LOAD_TRIGGER]', { reason: 'onDisplayModeChange', selectionKey, ts: Date.now() });
                          structure.setViewerSettings(prev => ({ ...prev, displayMode: mode }));
                          structure.setCurrentDisplayMode(mode);
                          if (structure.rightSelection) {
                            const token = ++structure.loadTokenRef.current;
                            structure.setIsStructureLoading(true);
                            structure.loadStructureModel(structure.rightSelection, {
                              ...structure.viewerSettings,
                              displayMode: mode,
                            }).then(model => {
                              if (token === structure.loadTokenRef.current) {
                                structure.setCurrentStructureModel(model);
                                structure.setIsStructureLoading(false);
                                if (model.vis) {
                                  structure.setStructureVisData(model.vis);
                                  structure.viewerStartTimeRef.current = performance.now();
                                }
                              }
                            }).catch(err => {
                              if (token === structure.loadTokenRef.current) {
                                console.error('[AppLayout] Failed to reload structure with new display mode', err);
                                structure.setStructureLoadError(`Failed to reload: ${err instanceof Error ? err.message : String(err)}`);
                                structure.setIsStructureLoading(false);
                              }
                            });
                          }
                        }}
                        onBoxBoundsChange={(bounds) => {
                          structure.setViewerSettings(prev => ({ ...prev, boxBounds: bounds }));
                          if (structure.leftMode === 'project') {
                            structure.setCurrentBoxBounds(bounds);
                          }
                        }}
                        currentDisplayMode={structure.viewerSettings.displayMode}
                        currentBoxBounds={structure.viewerSettings.boxBounds}
                        onFirstFrame={structure.handleViewerFirstFrame}
                        traceId={structure.currentTraceIdRef.current || undefined}
                      />
                    </div>
                  }
                />
                {structure.leftMode === 'import' && (
                  <div className="structures-view__import-actions">
                    <button
                      className="qms-button qms-button--primary structures-view__import-btn"
                      onClick={structure.handleImportOnlineCandidate}
                    >
                      Import
                    </button>
                    <button
                      className="qms-button qms-button--secondary structures-view__import-btn"
                      onClick={structure.handleExitImportMode}
                    >
                      Cancel
                    </button>
                  </div>
                )}
              </div>
            ) : structure.structureLoadError ? (
              <div className="structures-view__detail structures-view__detail--error">
                <div className="error-panel">
                  <h3>Failed to Load Structure</h3>
                  {structure.rightSelection && (
                    <p className="error-panel__selection-hint">
                      Selection: {structure.rightSelection.kind === 'project'
                        ? `project:${structure.rightSelection.structureId}`
                        : `online:${structure.rightSelection.sessionId}:${structure.rightSelection.candidateId}`}
                    </p>
                  )}
                  <p>{structure.structureLoadError}</p>
                  <button
                    className="qms-button qms-button--secondary"
                    onClick={() => {
                      if (structure.rightSelection) {
                        const selectionKey = structure.rightSelection.kind === 'project' ? `project:${structure.rightSelection.structureId}` : `online:${structure.rightSelection.sessionId}:${structure.rightSelection.candidateId}`;
                        console.log('[LOAD_TRIGGER]', { reason: 'retry-button', selectionKey, ts: Date.now() });
                        const token = ++structure.loadTokenRef.current;
                        const selection = structure.rightSelection;
                        structure.setIsStructureLoading(true);
                        structure.setStructureLoadError(null);

                        structure.loadStructureModel(selection, {
                          supercell: structure.currentSupercell,
                          repeatBoundary: structure.currentRepeatBoundary,
                          displayMode: structure.currentDisplayMode,
                          boxBounds: structure.currentBoxBounds,
                        }).then(model => {
                          if (token === structure.loadTokenRef.current) {
                            structure.setCurrentStructureModel(model);
                            structure.setStructureLoadError(null);
                            structure.setIsStructureLoading(false);
                            if (model.vis) {
                              structure.setStructureVisData(model.vis);
                              structure.viewerStartTimeRef.current = performance.now();
                            }
                          }
                        }).catch(err => {
                          if (token === structure.loadTokenRef.current) {
                            console.error('[AppLayout] Retry failed', err);
                            structure.setStructureLoadError(`Failed to load structure: ${err instanceof Error ? err.message : String(err)}`);
                            structure.setIsStructureLoading(false);
                          }
                        });
                      } else if (structure.selectedStructure && structure.leftMode === 'project') {
                        const token = ++structure.loadTokenRef.current;
                        const selection: RightSelection = {
                          kind: 'project',
                          structureId: structure.selectedStructure.ulid,
                        };
                        structure.setIsStructureLoading(true);
                        structure.setStructureLoadError(null);
                        structure.setRightSelection(selection);

                        structure.loadStructureModel(selection, {
                          supercell: structure.currentSupercell,
                          repeatBoundary: structure.currentRepeatBoundary,
                          displayMode: structure.currentDisplayMode,
                          boxBounds: structure.currentBoxBounds,
                        }).then(model => {
                          if (token === structure.loadTokenRef.current) {
                            structure.setCurrentStructureModel(model);
                            structure.setStructureLoadError(null);
                            structure.setIsStructureLoading(false);
                            if (model.vis) {
                              structure.setStructureVisData(model.vis);
                              structure.viewerStartTimeRef.current = performance.now();
                            }
                          }
                        }).catch(err => {
                          if (token === structure.loadTokenRef.current) {
                            console.error('[AppLayout] Retry failed', err);
                            structure.setStructureLoadError(`Failed to load structure: ${err instanceof Error ? err.message : String(err)}`);
                            structure.setIsStructureLoading(false);
                          }
                        });
                      }
                    }}
                  >
                    Retry
                  </button>
                </div>
              </div>
            ) : structure.isStructureLoading || (structure.selectedStructure && !structure.currentStructureModel) ? (
              <div className="structures-view__detail structures-view__detail--loading">
                <div className="loading-panel">
                  <div className="loading-spinner" />
                  <p>Loading structure...</p>
                </div>
              </div>
            ) : null}
          </div>
        );

      case 'calculations':
        if (!project.projectLoaded) return renderNoProjectMessage();
        return (
          <div className="calculations-view">
            <ResizablePane
              ref={calculationsPaneRef}
              defaultWidth={200}
              minWidth={56}
              maxWidth={420}
              storageKey="qms-calculations-list-width"
              className="calculations-view__list"
              collapsedWidth={56}
            >
              <CalculationListPanel
                onRefreshProjectRegistry={project.handleRefreshProjectRegistry}
                calculations={project.calculations}
                isLoading={project.isLoadingCalculations}
                selectedId={calc.selectedCalculation?.calc_ulid}
                onSelect={calc.handleSelectCalculation}
                onRename={project.setRenameCalculation}
                onDelete={project.setDeleteCalculation}
                onToggleCollapse={handleToggleCalculationsPane}
                paneRef={calculationsPaneRef}
              />
              <button
                className="view-action-btn"
                onClick={() => shell.setShowCreateCalculation(true)}
                data-testid="qms-btn-new-calculation"
              >
                ➕ New Calculation
              </button>
            </ResizablePane>

            <div className="calculations-view__workspace">
              <div className="calculations-workspace-tabs">
                <button
                  className={`calculations-workspace-tab ${calc.activeCalcTab === 'overview' ? 'calculations-workspace-tab--active' : ''}`}
                  onClick={() => calc.setActiveCalcTab('overview')}
                  data-testid="qms-calc-tab-overview"
                >
                  Overview & Steps
                </button>
                <button
                  className={`calculations-workspace-tab ${calc.activeCalcTab === 'run' ? 'calculations-workspace-tab--active' : ''}`}
                  onClick={() => calc.setActiveCalcTab('run')}
                  data-testid="qms-calc-tab-run"
                >
                  Run & Logs
                </button>
                <button
                  className={`calculations-workspace-tab ${calc.activeCalcTab === 'analysis' ? 'calculations-workspace-tab--active' : ''}`}
                  onClick={() => calc.setActiveCalcTab('analysis')}
                  data-testid="qms-calc-tab-analysis"
                >
                  Analysis
                </button>
              </div>

              <div className="calculations-workspace-content">
                {calc.missingEngineGuidance && (
                  <div className="missing-engine-panel" data-testid="qms-missing-engine-panel">
                    <div className="missing-engine-panel__title">
                      {calc.ENGINE_DISPLAY_NAMES[calc.missingEngineGuidance.engineFamily] || calc.missingEngineGuidance.engineFamily} is not installed
                    </div>
                    <div className="missing-engine-panel__message">
                      {calc.missingEngineGuidance.message}
                    </div>
                    {calc.missingEngineGuidance.installStatus && (
                      <div className="missing-engine-panel__status">
                        {calc.missingEngineGuidance.installStatus}
                      </div>
                    )}
                    {calc.missingEngineGuidance.installError && (
                      <div className="missing-engine-panel__error">
                        {calc.missingEngineGuidance.installError}
                      </div>
                    )}
                    <div className="missing-engine-panel__actions">
                      {!calc.missingEngineGuidance.installed && (
                        <button
                          className="settings-btn"
                          onClick={() => void calc.handleInstallMissingEngine()}
                          disabled={!!calc.missingEngineGuidance.installJobId}
                          data-testid="qms-missing-engine-install"
                        >
                          {calc.missingEngineGuidance.installJobId ? 'Installing...' : `Install ${calc.ENGINE_DISPLAY_NAMES[calc.missingEngineGuidance.engineFamily] || calc.missingEngineGuidance.engineFamily}`}
                        </button>
                      )}
                      <button
                        className="settings-btn"
                        onClick={() => void calc.handleConfigureMissingEnginePath()}
                        data-testid="qms-missing-engine-configure-path"
                      >
                        Configure Path
                      </button>
                      <button
                        className="settings-btn"
                        onClick={() => shell.setCurrentView('settings')}
                        data-testid="qms-missing-engine-open-manager"
                      >
                        Open Engine Manager
                      </button>
                      {calc.missingEngineGuidance.installed && calc.selectedCalculationSummary && (
                        <button
                          className="settings-btn settings-btn--primary"
                          onClick={() => void calc.handleRunCalculation(calc.selectedCalculationSummary!, 'incremental')}
                          data-testid="qms-missing-engine-run-again"
                        >
                          Run Again
                        </button>
                      )}
                      <button
                        className="settings-btn settings-btn--sm"
                        onClick={() => calc.clearMissingEngineGuidance()}
                        data-testid="qms-missing-engine-dismiss"
                      >
                        Dismiss
                      </button>
                    </div>
                  </div>
                )}

                {calc.activeCalcTab === 'overview' && (
                  <CalculationOverviewTab
                    calculationSummary={calc.selectedCalculationSummary}
                    calculationDetail={calc.selectedCalculationDetail}
                    projectRoot={project.projectRoot}
                    structures={project.structures || undefined}
                    selectedStepId={calc.selectedStepId}
                    onSelectStep={calc.handleSelectStep}
                    onRunCalculation={calc.handleRunCalculation}
                    onDeleteStep={calc.handleDeleteStep}
                    onGoToJobs={calc.handleGoToJobs}
                    onCalculationUpdated={async () => {
                      console.log('[AppLayout] onCalculationUpdated: refreshing calculation detail after step creation');
                      await project.fetchCalculations();

                      if (calc.selectedCalculationSummary) {
                        const response = await qms.call('get_calculation_detail', {
                          project_root: project.projectRoot,
                          calculation: calc.selectedCalculationSummary.calc_ulid,
                        });
                        if (response.ok && response.data) {
                          const updatedDetail = response.data as CalculationDetailResult;
                          console.log('[AppLayout] Calculation detail refreshed', {
                            calculationSlug: updatedDetail.slug,
                            stepCount: updatedDetail.steps?.length ?? 0,
                            stepUlids: (updatedDetail.steps ?? []).map(s => s.ulid),
                            stepOrder: (updatedDetail.steps ?? []).map((s, i) => ({ index: i, ulid: s.ulid, step_type_gen: s.step_type_gen })),
                          });
                          calc.setSelectedCalculationDetail(updatedDetail);
                        } else {
                          console.error('[AppLayout] Failed to refresh calculation detail', response.error);
                        }
                      }
                    }}
                    onCalculationDetailUpdated={(detail) => {
                      console.log('[AppLayout] Calculation detail updated from reorder', {
                        calculationSlug: detail.slug,
                        stepCount: detail.steps?.length ?? 0,
                        stepOrder: (detail.steps ?? []).map((s, i) => ({ index: i, ulid: s.ulid, step_type_gen: s.step_type_gen })),
                      });
                      calc.setSelectedCalculationDetail(detail);
                    }}
                  />
                )}

                {calc.activeCalcTab === 'run' && (
                  <CalculationRunTab
                    projectRoot={project.projectRoot}
                    calculation={calc.selectedCalculationDetail || calc.selectedCalculationSummary}
                  />
                )}

                {calc.activeCalcTab === 'analysis' && (
                  <CalculationAnalysisTab
                    projectRoot={project.projectRoot}
                    calculation={calc.selectedCalculationDetail || calc.selectedCalculationSummary}
                  />
                )}
              </div>
            </div>
          </div>
        );

      case 'jobs':
        return (
          <JobsPanel
            projectRoot={project.projectLoaded ? project.projectRoot : undefined}
            onViewAnalysis={handleViewAnalysisFromJob}
          />
        );

      case 'history':
        return (
          <HistoryPanel
            projectRoot={project.projectRoot}
          />
        );

      case 'resources':
        return <EngineParameterBrowserPanel />;

      case 'settings':
        return (
          <SettingsPanel
            settings={shell.appSettings}
            onSettingsChange={shell.setAppSettings}
          />
        );

      case 'dev-volume':
        return import.meta.env.DEV ? <VolumeViewerSandbox /> : null;

      default:
        return null;
    }
  };

  const showUpdaterBanner = Boolean(
    shell.updaterState &&
    !shell.updaterDismissed &&
    ['available', 'downloading', 'downloaded', 'error'].includes(shell.updaterState.state),
  );

  return (
    <>
      <AppShell
        sidebar={
          <Sidebar
            qms={qms}
            projectRoot={project.projectRoot}
            projectLoaded={project.projectLoaded}
            projectError={project.projectError}
            onBrowseAndLoad={handleBrowseAndLoad}
            onCreateProject={() => shell.setShowCreateProject(true)}
            onOpenDemoGallery={shell.handleOpenDemoGallery}
            currentView={shell.currentView}
            onViewChange={shell.setCurrentView}
            daemonStatus={daemonStatus}
            jobCounts={jobCounts}
          />
        }
        footer={shell.showDebugFooter ? <DebugPanel /> : null}
        statusBar={
          <StatusBar
            projectRoot={project.projectLoaded ? project.projectRoot : null}
            projectName={project.projectSummary?.name || null}
            daemonConnected={daemonStatus?.connected ?? false}
            onOpenSettings={() => shell.setCurrentView('settings')}
            onOpenJobs={() => shell.setCurrentView('jobs')}
            onNavigateToHome={() => shell.setCurrentView('home')}
          />
        }
      >
        <div className="main-content">
          <DaemonErrorBanner status={daemonStatus} />

          {shell.jobNotification && (
            <div className={`job-notification job-notification--${shell.jobNotification.type}`}>
              <span className="job-notification__message">{shell.jobNotification.message}</span>
              <button
                className="job-notification__close"
                onClick={() => shell.setJobNotification(null)}
              >
                ×
              </button>
            </div>
          )}

          {showUpdaterBanner && shell.updaterState && (
            <div className="updater-banner" data-testid="qms-updater-banner">
              <div className="updater-banner__content">
                <div className="updater-banner__title">
                  {shell.updaterState.state === 'error'
                    ? 'Update check failed'
                    : shell.updaterState.state === 'downloaded'
                      ? `Update ${shell.updaterState.version || ''} is ready`
                      : `Update available${shell.updaterState.version ? `: v${shell.updaterState.version}` : ''}`}
                </div>
                {shell.updaterState.message && (
                  <div className="updater-banner__message">{shell.updaterState.message}</div>
                )}
                {shell.updaterState.state === 'downloading' && (
                  <div className="updater-banner__progress-wrap">
                    <div className="updater-banner__progress-track">
                      <div
                        className="updater-banner__progress-fill"
                        style={{ width: `${Math.max(0, Math.min(100, shell.updaterState.progress || 0))}%` }}
                      />
                    </div>
                    <span className="updater-banner__progress-text">
                      {(shell.updaterState.progress || 0).toFixed(0)}%
                    </span>
                  </div>
                )}
              </div>
              <div className="updater-banner__actions">
                {shell.updaterState.state === 'available' && (
                  <button
                    className="settings-btn settings-btn--sm"
                    onClick={() => void shell.handleDownloadUpdate()}
                    data-testid="qms-updater-download"
                  >
                    Download
                  </button>
                )}
                {shell.updaterState.state === 'error' && (
                  <button
                    className="settings-btn settings-btn--sm"
                    onClick={() => void shell.handleCheckForUpdates()}
                    data-testid="qms-updater-retry"
                  >
                    Retry
                  </button>
                )}
                {shell.updaterState.state === 'downloaded' && (
                  <button
                    className="settings-btn settings-btn--primary settings-btn--sm"
                    onClick={() => void shell.handleInstallDownloadedUpdate()}
                    data-testid="qms-updater-restart"
                  >
                    Restart Now
                  </button>
                )}
                <button
                  className="settings-btn settings-btn--sm"
                  onClick={() => shell.setUpdaterDismissed(true)}
                  data-testid="qms-updater-later"
                >
                  Later
                </button>
              </div>
            </div>
          )}

          <div className="app-header">
            <h2 className="app-header__title">
              {shell.currentView === 'home' && 'Home'}
              {shell.currentView === 'structures' && 'Structures'}
              {shell.currentView === 'calculations' && 'Calculations'}
              {shell.currentView === 'jobs' && 'Jobs'}
              {shell.currentView === 'history' && 'History'}
              {shell.currentView === 'resources' && 'Resources'}
              {shell.currentView === 'settings' && 'Settings'}
              {import.meta.env.DEV && shell.currentView === 'dev-volume' && 'Volume Viewer (DEV)'}
            </h2>
            <div className="app-header__actions">
              <button
                className="app-header__toggle"
                onClick={() => void shell.handleCheckForUpdates()}
              >
                Check Updates
              </button>
              <button
                className="app-header__toggle"
                onClick={() => shell.setShowDebugFooter(!shell.showDebugFooter)}
              >
                {shell.showDebugFooter ? '🔽 Hide Logs' : '🔼 Show Logs'}
              </button>
            </div>
          </div>

          <div className="main-content__body">
            <ErrorBoundary
              fallbackTitle="View Error"
              onReset={() => shell.setCurrentView('home')}
            >
              {renderMainContent()}
            </ErrorBoundary>
          </div>
        </div>
      </AppShell>

      {/* Dialogs */}
      <CreateProjectDialog
        isOpen={shell.showCreateProject}
        onClose={() => shell.setShowCreateProject(false)}
        onSuccess={handleCreateProjectSuccess}
        defaultParentDir={shell.appSettings.defaultProjectsDir}
      />

      <CreateProjectDialog
        isOpen={shell.showCreateDemoProject}
        onClose={() => shell.setShowCreateDemoProject(false)}
        onSuccess={handleCreateProjectSuccess}
        isDemoProject={true}
        defaultParentDir={shell.appSettings.defaultProjectsDir}
      />

      <ImportStructureDialog
        isOpen={shell.showImportStructure}
        projectRoot={project.projectRoot}
        onClose={() => shell.setShowImportStructure(false)}
        onSuccess={handleImportStructureSuccess}
      />

      <CreateCalculationDialog
        isOpen={shell.showCreateCalculation}
        projectRoot={project.projectRoot}
        structures={project.structures || []}
        onClose={() => shell.setShowCreateCalculation(false)}
        onSuccess={handleCreateCalculationSuccess}
      />

      {/* Rename Dialogs */}
      <RenameDialog
        isOpen={!!project.renameStructure}
        onClose={() => project.setRenameStructure(null)}
        currentName={project.renameStructure?.name || ''}
        title="Rename Structure"
        onRename={handleRenameStructure}
        isLoading={project.isRenaming}
      />

      <RenameDialog
        isOpen={!!project.renameCalculation}
        onClose={() => project.setRenameCalculation(null)}
        currentName={project.renameCalculation?.name || ''}
        title="Rename Calculation"
        onRename={handleRenameCalculation}
        isLoading={project.isRenaming}
      />

      {/* Delete Dialogs */}
      <DeleteConfirmDialog
        isOpen={!!project.deleteStructure}
        onClose={() => project.setDeleteStructure(null)}
        resourceName={project.deleteStructure?.name || ''}
        resourceType="Structure"
        warningMessage="This structure may be used by one or more calculations."
        onConfirm={handleDeleteStructure}
        isLoading={project.isDeleting}
        forceDeleteOption={true}
      />

      <DeleteConfirmDialog
        isOpen={!!project.deleteCalculation}
        onClose={() => project.setDeleteCalculation(null)}
        resourceName={project.deleteCalculation?.name || ''}
        resourceType="Calculation"
        warningMessage="This will permanently delete the calculation and all its step files."
        onConfirm={handleDeleteCalculation}
        isLoading={project.isDeleting}
        forceDeleteOption={false}
      />
    </>
  );
}
