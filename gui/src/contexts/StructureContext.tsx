/**
 * StructureContext — Structure viewer + import mode
 *
 * Owns: structure selection, viewer settings, 3D state, import mode,
 * loadStructureModel, and all structure loading effects.
 *
 * Dependency: reads AppShellContext (currentView);
 *             reads ProjectContext (projectRoot, structures, fetchStructures).
 */

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  useRef,
  useMemo,
  type ReactNode,
} from 'react';
import { useQMSClient } from '../hooks';
import { useAppShell } from './AppShellContext';
import { useProject } from './ProjectContext';
import type {
  StructureInfo,
  StructureVisData,
  StructureModel,
  RightSelection,
  Provenance,
} from '../types';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ViewerSettings {
  supercell: [number, number, number];
  repeatBoundary: boolean;
  displayMode: 'primitive' | 'supercell' | 'conventional' | 'box';
  boxBounds: [number, number, number, number, number, number] | null;
  showBonds: boolean;
  showUnitCell: boolean;
  showLabels: boolean;
  atomScale: number;
  bondScale: number;
}

export interface StructureContextValue {
  // Selection
  selectedStructure: StructureInfo | null;
  setSelectedStructure: React.Dispatch<React.SetStateAction<StructureInfo | null>>;
  currentStructureModel: StructureModel | null;
  rightSelection: RightSelection | null;
  structureVisData: StructureVisData | null;
  structureLoadError: string | null;

  // Viewer settings
  viewerSettings: ViewerSettings;
  setViewerSettings: React.Dispatch<React.SetStateAction<ViewerSettings>>;

  // Legacy per-field state (used by project loading effect)
  currentSupercell: [number, number, number];
  setCurrentSupercell: (v: [number, number, number]) => void;
  currentRepeatBoundary: boolean;
  setCurrentRepeatBoundary: (v: boolean) => void;
  currentDisplayMode: 'primitive' | 'supercell' | 'conventional' | 'box';
  setCurrentDisplayMode: (v: 'primitive' | 'supercell' | 'conventional' | 'box') => void;
  currentBoxBounds: [number, number, number, number, number, number] | null;
  setCurrentBoxBounds: (v: [number, number, number, number, number, number] | null) => void;

  // Loading
  isStructureLoading: boolean;
  isLoading3D: boolean;
  structureRefreshToken: number;
  setStructureRefreshToken: React.Dispatch<React.SetStateAction<number>>;

  // Import mode
  leftMode: 'project' | 'import';
  onlineSessionId: string | null;
  onlineCandidates: any[];
  selectedOnlineCandidateId: string | null;

  // Refs exposed for AppLayout
  loadTokenRef: React.MutableRefObject<number>;
  viewerStartTimeRef: React.MutableRefObject<number | null>;
  currentTraceIdRef: React.MutableRefObject<string | null>;

  // Handlers
  handleSelectStructure: (structure: StructureInfo) => void;
  handleEnterImportMode: () => void;
  handleExitImportMode: () => Promise<void>;
  handleSelectOnlineCandidate: (sessionId: string, candidateId: string) => void;
  handleImportOnlineCandidate: () => Promise<void>;
  handleViewerFirstFrame: (traceId: string) => void;
  loadStructureModel: (selection: RightSelection, viewerSettingsOverride?: Partial<ViewerSettings>) => Promise<StructureModel>;

  // Setters for display mode reload (used by AppLayout)
  setCurrentStructureModel: React.Dispatch<React.SetStateAction<StructureModel | null>>;
  setStructureVisData: React.Dispatch<React.SetStateAction<StructureVisData | null>>;
  setRightSelection: React.Dispatch<React.SetStateAction<RightSelection | null>>;
  setStructureLoadError: React.Dispatch<React.SetStateAction<string | null>>;
  setIsStructureLoading: React.Dispatch<React.SetStateAction<boolean>>;
  setIsLoading3D: React.Dispatch<React.SetStateAction<boolean>>;
}

// ---------------------------------------------------------------------------
// Context
// ---------------------------------------------------------------------------

const StructureContext = createContext<StructureContextValue | null>(null);

export function useStructure(): StructureContextValue {
  const ctx = useContext(StructureContext);
  if (!ctx) throw new Error('useStructure must be used within <StructureProvider>');
  return ctx;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function validateStructureModel(m: any): { ok: true } | { ok: false; msg: string } {
  if (!m) return { ok: false, msg: 'Model is null or undefined' };
  if (!m.id || typeof m.id !== 'string') return { ok: false, msg: 'Missing or invalid id field' };

  const isMolecule = m.structure_type === 'molecule' || (m.pbc && Array.isArray(m.pbc) && m.pbc.every((p: boolean) => p === false));
  if (!isMolecule) {
    if (!m.lattice || !Array.isArray(m.lattice) || m.lattice.length !== 3) {
      return { ok: false, msg: 'Missing or invalid lattice (must be 3x3 matrix)' };
    }
    for (const row of m.lattice) {
      if (!Array.isArray(row) || row.length !== 3) return { ok: false, msg: 'Lattice must be 3x3 matrix' };
      for (const val of row) {
        if (typeof val !== 'number' || !isFinite(val)) return { ok: false, msg: 'Lattice contains non-numeric values' };
      }
    }
  } else {
    if (m.lattice !== null && m.lattice !== undefined) {
      if (Array.isArray(m.lattice) && m.lattice.length === 3) {
        for (const row of m.lattice) {
          if (Array.isArray(row) && row.length === 3) {
            for (const val of row) {
              if (typeof val !== 'number' || !isFinite(val)) return { ok: false, msg: 'Lattice contains non-numeric values' };
            }
          }
        }
      }
    }
  }

  if (!m.atoms || !Array.isArray(m.atoms)) return { ok: false, msg: 'Missing or invalid atoms array' };
  for (const atom of m.atoms) {
    if (!atom.element || typeof atom.element !== 'string') return { ok: false, msg: 'Atom missing element field' };
    if (!atom.frac || !Array.isArray(atom.frac) || atom.frac.length !== 3) return { ok: false, msg: 'Atom missing or invalid frac_coords' };
  }
  if (m.bonds && !Array.isArray(m.bonds)) return { ok: false, msg: 'bonds must be an array if present' };
  return { ok: true };
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function StructureProvider({ children }: { children: ReactNode }) {
  const { currentView } = useAppShell();
  const { projectRoot, structures, fetchStructures } = useProject();
  const qms = useQMSClient();

  // --- Selection state ------------------------------------------------------
  const [selectedStructure, setSelectedStructure] = useState<StructureInfo | null>(null);
  const [currentStructureModel, setCurrentStructureModel] = useState<StructureModel | null>(null);
  const [rightSelection, setRightSelection] = useState<RightSelection | null>(null);
  const [structureVisData, setStructureVisData] = useState<StructureVisData | null>(null);
  const [structureLoadError, setStructureLoadError] = useState<string | null>(null);

  // --- Viewer settings ------------------------------------------------------
  const [viewerSettings, setViewerSettings] = useState<ViewerSettings>({
    supercell: [1, 1, 1],
    repeatBoundary: true,
    displayMode: 'primitive',
    boxBounds: null,
    showBonds: true,
    showUnitCell: true,
    showLabels: false,
    atomScale: 0.4,
    bondScale: 1.0,
  });

  const savedProjectViewerSettingsRef = useRef<ViewerSettings | null>(null);

  // Legacy per-field state
  const [currentSupercell, setCurrentSupercell] = useState<[number, number, number]>([1, 1, 1]);
  const [currentRepeatBoundary, setCurrentRepeatBoundary] = useState(true);
  const [currentDisplayMode, setCurrentDisplayMode] = useState<'primitive' | 'supercell' | 'conventional' | 'box'>('primitive');
  const [currentBoxBounds, setCurrentBoxBounds] = useState<[number, number, number, number, number, number] | null>(null);

  // --- Loading state --------------------------------------------------------
  const [isStructureLoading, setIsStructureLoading] = useState(false);
  const [isLoading3D, setIsLoading3D] = useState(false);
  const [structureRefreshToken, setStructureRefreshToken] = useState(0);

  // --- Import mode ----------------------------------------------------------
  const [leftMode, setLeftMode] = useState<'project' | 'import'>('project');
  const [returnProjectSelectionId, setReturnProjectSelectionId] = useState<string | null>(null);
  const [onlineSessionId, setOnlineSessionId] = useState<string | null>(null);
  const [onlineCandidates, setOnlineCandidates] = useState<any[]>([]);
  const [selectedOnlineCandidateId, setSelectedOnlineCandidateId] = useState<string | null>(null);

  // --- Refs -----------------------------------------------------------------
  const loadTokenRef = useRef(0);
  const viewerStartTimeRef = useRef<number | null>(null);
  const currentTraceIdRef = useRef<string | null>(null);
  const currentOnlineCandidateIdRef = useRef<string | null>(null);
  const didAutoSelectStructureRef = useRef(false);

  const generateTraceId = useCallback(() => {
    return Date.now().toString(36).slice(-4) + Math.random().toString(36).slice(2, 6);
  }, []);

  // --- loadStructureModel ---------------------------------------------------
  const loadStructureModel = useCallback(async (
    selection: RightSelection,
    viewerSettingsOverride?: Partial<ViewerSettings>
  ): Promise<StructureModel> => {
    if (!projectRoot || !qms) {
      throw new Error('Project root or QMS client not available');
    }

    const rpcStart = performance.now();
    const traceId = generateTraceId();
    currentTraceIdRef.current = traceId;

    let visData: StructureVisData | null = null;
    let provenance: Provenance | null = null;
    let formula = '';
    let nsites = 0;
    let rpcMs: number | null = null;

    try {
      if (selection.kind === 'project') {
        const structure = structures?.find(s => s.ulid === selection.structureId);
        if (!structure) {
          throw new Error(`Structure not found: ${selection.structureId}`);
        }

        const settings = viewerSettingsOverride || viewerSettings;
        const response = await qms.call('get_structure_vis', {
          project_root: projectRoot,
          selector: structure.slug,
          supercell: settings.supercell,
          repeat_boundary: settings.repeatBoundary,
          display_mode: settings.displayMode,
          box_bounds: settings.boxBounds ?? undefined,
          trace_id: traceId,
        });

        const rpcEnd = performance.now();
        rpcMs = rpcEnd - rpcStart;

        if (response.ok && response.data) {
          try {
            visData = response.data as StructureVisData;
            formula = visData.formula || '';
            nsites = visData.n_atoms || 0;

            const perf = (response.data as any).perf;
            const backendTotalMs = perf?.total_ms || 0;
            const kind = 'project';
            const atomsCount = visData.atoms?.length || 0;
            const bondsCount = visData.bonds?.length || 0;
            const hasProvenance = !!(response.data as any).provenance;
            console.log(
              `[structure_vis] kind=${kind} structureId=${selection.structureId} atoms=${atomsCount} bonds=${bondsCount} provenance=${hasProvenance}`
            );

            const renderStart = performance.now();
            viewerStartTimeRef.current = renderStart;
            const mode = settings.displayMode;
            const rpcMsStr = rpcMs == null ? "n/a" : `${Math.round(rpcMs)}ms`;
            console.log(
              `[ui] kind=${kind} rpc=${rpcMsStr} backend=${Math.round(backendTotalMs)}ms atoms=${atomsCount} bonds=${bondsCount} mode=${mode} (render pending)`
            );
          } catch (err) {
            console.error('[structure_vis_parse_failed] project path', err, response.data);
            throw err;
          }
        } else {
          const errorMsg = response.error || 'Unknown error';
          throw new Error(`Backend error loading structure: ${errorMsg}`);
        }
      } else {
        // Online candidate path
        const settings = viewerSettingsOverride || viewerSettings;
        const response = await qms.call('structure_get_online_candidate', {
          session_id: selection.sessionId,
          candidate_id: selection.candidateId,
          supercell: settings.supercell,
          repeat_boundary: settings.repeatBoundary,
          display_mode: settings.displayMode,
          box_bounds: settings.boxBounds ?? undefined,
          trace_id: traceId,
        });

        const rpcEnd = performance.now();
        rpcMs = rpcEnd - rpcStart;

        if (response.ok && response.data) {
          try {
            const data = response.data as any;
            formula = data.formula || '';
            nsites = data.n_atoms || 0;
            provenance = data.provenance || null;

            const kind = 'online';
            const atomsCount = data.structure_vis?.atoms?.length || 0;
            const bondsCount = data.structure_vis?.bonds?.length || 0;
            const hasProvenance = !!provenance;
            console.log(
              `[structure_vis] kind=${kind} candidateId=${selection.candidateId} atoms=${atomsCount} bonds=${bondsCount} provenance=${hasProvenance}`
            );

            if (data.structure_vis) {
              const atoms = data.structure_vis.atoms.map((atom: any, idx: number) => {
                const cart = atom.cart_coords || atom.position;
                const frac = atom.frac_coords || atom.position;
                return {
                  index: idx,
                  element: atom.symbol,
                  cart_coords: cart,
                  frac_coords: frac,
                  color: atom.color,
                  radius: atom.radius,
                };
              });

              const boundary_atoms = (data.structure_vis.boundary_atoms || []).map((atom: any, idx: number) => {
                const cart = atom.cart_coords || atom.position;
                const frac = atom.frac_coords || atom.position;
                return {
                  index: atoms.length + idx,
                  element: atom.symbol,
                  cart_coords: cart,
                  frac_coords: frac,
                  color: atom.color,
                  radius: atom.radius,
                };
              });

              visData = {
                structure_id: `online:${selection.candidateId}`,
                structure_name: formula,
                formula: formula,
                n_atoms: atoms.length,
                n_boundary_atoms: boundary_atoms.length,
                n_bonds: data.structure_vis.bonds?.length || 0,
                supercell: data.structure_vis.supercell || [1, 1, 1],
                perf: data.structure_vis.perf,
                display_mode: data.structure_vis.display_mode || 'primitive',
                lattice: data.structure_vis.lattice,
                atoms: atoms,
                boundary_atoms: boundary_atoms,
                bonds: (data.structure_vis.bonds || []).map((bond: any) => ({
                  idx1: bond.idx1 ?? 0,
                  idx2: bond.idx2 ?? 0,
                  coord1: bond.coord1 || atoms[bond.idx1 ?? 0]?.cart_coords || [0, 0, 0],
                  coord2: bond.coord2 || atoms[bond.idx2 ?? 0]?.cart_coords || [0, 0, 0],
                  distance: bond.distance || 0,
                })),
                element_colors: {},
              };

              const perf = (data.structure_vis as any).perf;
              const backendTotalMs = perf?.total_ms || 0;
              const renderStart = performance.now();
              viewerStartTimeRef.current = renderStart;
              const mode = settings.displayMode;
              const rpcMsStr = rpcMs == null ? "n/a" : `${Math.round(rpcMs)}ms`;
              console.log(
                `[ui] kind=online rpc=${rpcMsStr} backend=${Math.round(backendTotalMs)}ms atoms=${atoms.length} bonds=${data.structure_vis.bonds?.length || 0} mode=${mode} (render pending)`
              );
            } else {
              console.error('[structure_vis_parse_failed] online path - missing structure_vis', data);
            }
          } catch (err) {
            console.error('[structure_vis_parse_failed] online path', err, response.data);
            throw err;
          }
        } else {
          const errorMsg = response.error || 'Unknown error';
          throw new Error(`Backend error loading online candidate: ${errorMsg}`);
        }
      }

      if (!visData) {
        throw new Error('No visualization data received from backend');
      }

      try {
        const speciesSet = new Set<string>();
        const primaryAtoms = visData.atoms.filter((a: any) => !a.is_boundary);
        const sourceAtoms = primaryAtoms.length > 0 ? primaryAtoms : visData.atoms;
        if (sourceAtoms && Array.isArray(sourceAtoms)) {
          sourceAtoms.forEach((atom: any) => speciesSet.add(atom.element));
        }
        if (primaryAtoms.length === 0 && visData.boundary_atoms && Array.isArray(visData.boundary_atoms) && visData.boundary_atoms.length > 0) {
          if (visData.atoms && Array.isArray(visData.atoms)) {
            visData.atoms.forEach((atom: any) => speciesSet.add(atom.element));
          }
          if (process.env.NODE_ENV === 'development') {
            console.warn('[Structure] Legacy payload: using all atoms for species (no is_boundary flag)');
          }
        }
        const species = Array.from(speciesSet).sort();

        const isMolecule = visData.structure_type === 'molecule' ||
          (visData.pbc && Array.isArray(visData.pbc) && visData.pbc.every((p: boolean) => p === false));
        if (!isMolecule && (!visData.lattice || !visData.lattice.matrix)) {
          throw new Error('Missing lattice data in response (required for crystals)');
        }
        if (!visData.atoms || !Array.isArray(visData.atoms)) {
          throw new Error('Missing or invalid atoms array in response');
        }
        if (visData.bonds && !Array.isArray(visData.bonds)) {
          throw new Error('bonds must be an array if present');
        }

        const model: StructureModel = {
          id: selection.kind === 'project' ? selection.structureId : `online:${selection.candidateId}`,
          name: visData.structure_name || formula,
          formula: formula,
          nsites: nsites,
          species: species,
          lattice: isMolecule ? null : (visData.lattice?.matrix || null),
          structure_type: visData.structure_type || (isMolecule ? 'molecule' : 'crystal'),
          pbc: visData.pbc || (isMolecule ? [false, false, false] : [true, true, true]),
          atoms: visData.atoms.map(atom => ({
            element: atom.element,
            frac: atom.frac_coords,
            cart: atom.cart_coords,
            index: atom.index,
          })),
          bonds: (visData.bonds || []).map(bond => ({
            i: bond.idx1 ?? 0,
            j: bond.idx2 ?? 0,
            distance: bond.distance ?? 0,
          })),
          vis: visData,
          provenance: provenance || null,
          n_boundary_atoms: visData.atoms.filter((a: any) => a.is_boundary === true).length || visData.n_boundary_atoms || 0,
          supercell: visData.supercell || [1, 1, 1],
          display_mode: visData.display_mode || 'primitive',
          element_colors: visData.element_colors || {},
        };

        if (process.env.NODE_ENV === 'development') {
          const selectionKey = selection.kind === 'project'
            ? `project:${selection.structureId}`
            : `online:${selection.sessionId}:${selection.candidateId}`;
          const atomsLen = model.atoms.length;
          const bondsLen = model.bonds.length;
          const boundaryAtomsCount = visData.atoms.filter((a: any) => a.is_boundary === true).length;
          const hasBoundaryAtoms = boundaryAtomsCount > 0;
          const repeatBoundary = viewerSettingsOverride?.repeatBoundary ?? (selection.kind === 'project' ? currentRepeatBoundary : viewerSettings.repeatBoundary);

          if (repeatBoundary && !hasBoundaryAtoms && visData.boundary_atoms?.length === 0) {
            console.warn('[FRONTEND] P1-2 ASSERTION: repeat_boundary=true but no boundary atoms found in atoms array');
          }

          if (bondsLen > 0) {
            const maxBondIndex = Math.max(...model.bonds.map(b => Math.max(b.i, b.j)));
            if (maxBondIndex >= atomsLen) {
              const firstBondKeys = Object.keys(visData.bonds[0]);
              const firstBond = visData.bonds[0];
              const secondBond = visData.bonds[1] || null;
              console.error(
                `[FRONTEND] PAYLOAD_EVIDENCE selectionKey=${selectionKey} ` +
                `atoms.length=${atomsLen} bonds.length=${bondsLen} ` +
                `maxBondIndex=${maxBondIndex} maxBondIndex_valid=false ` +
                `firstBondKeys=${JSON.stringify(firstBondKeys)} ` +
                `firstBond=${JSON.stringify(firstBond)} secondBond=${JSON.stringify(secondBond)}`
              );
              console.error(`[FRONTEND] P1-2 ASSERTION FAILED: maxBondIndex=${maxBondIndex} >= atoms.length=${atomsLen}`);
            }
          }
        }

        (model.vis as any).__traceId = traceId;
        (model.vis as any).__backendTotalMs = (visData as any).perf?.total_ms || '?';
        (model.vis as any).__atoms = (visData as any).perf?.atoms || nsites;
        (model.vis as any).__bonds = (visData as any).perf?.bonds || visData.n_bonds;
        if (selection.kind === 'online') {
          (model.vis as any).__candidateId = selection.candidateId;
        }

        const validation = validateStructureModel(model);
        if (!validation.ok) {
          throw new Error(`Invalid structure model: ${validation.msg}`);
        }

        return model;
      } catch (e) {
        console.error('[structure_vis_parse_failed] model construction', e, { visData, selection });
        throw e instanceof Error ? e : new Error(`Failed to construct structure model: ${String(e)}`);
      }
    } catch (e) {
      console.error('[structure_vis_parse_failed] outer catch', e, { selection });
      throw e instanceof Error ? e : new Error(`Failed to load structure: ${String(e)}`);
    }
  }, [qms, projectRoot, structures, viewerSettings, generateTraceId, currentRepeatBoundary]);

  // --- Viewer first frame callback ------------------------------------------
  const handleViewerFirstFrame = useCallback((traceId: string) => {
    if (traceId !== currentTraceIdRef.current) return;
    const viewerStart = viewerStartTimeRef.current;
    if (viewerStart === null) return;

    const viewerEnd = performance.now();
    const renderMs = viewerEnd - viewerStart;
    const data = structureVisData as any;
    if (!data) return;
    if (data.__traceId !== traceId) return;

    const rpcMs = data.__rpcMs;
    const backendTotalMs = data.__backendTotalMs || '?';
    const atoms = data.__atoms || 0;
    const bonds = data.__bonds || 0;
    const source = data.__candidateId ? 'online' : 'project';
    const id = data.__candidateId || data.structure_id || 'unknown';
    const mode = (data.display_mode || 'primitive') as string;
    const rpcMsStr = rpcMs == null ? "n/a" : `${Math.round(rpcMs)}ms`;

    console.log(`[ui] kind=${source} rpc=${rpcMsStr} render=${Math.round(renderMs)}ms atoms=${atoms} bonds=${bonds} mode=${mode}`);
    const rpcMsDetail = rpcMs == null ? "n/a" : rpcMs.toFixed(1);
    console.log(
      `[PERF] structure_view trace=${traceId} rpc=${rpcMsDetail}ms backend=${backendTotalMs}ms render=${renderMs.toFixed(1)}ms atoms=${atoms} bonds=${bonds} source=${source} id=${id}`
    );
    viewerStartTimeRef.current = null;
  }, [structureVisData]);

  // --- Selection handlers ---------------------------------------------------

  const handleSelectStructure = useCallback((structure: StructureInfo) => {
    if (leftMode !== 'project') return;

    const selectionKey = `project:${structure.ulid}`;
    setStructureRefreshToken(t => {
      const newToken = t + 1;
      console.log('[UI_CLICK]', { selectionKey, refreshToken: newToken, ts: Date.now() });
      return newToken;
    });

    setSelectedStructure(structure);
    didAutoSelectStructureRef.current = true;
    setCurrentSupercell([1, 1, 1]);
    setCurrentRepeatBoundary(true);
    setCurrentDisplayMode('primitive');
    setCurrentBoxBounds(null);
    console.log(`[PERF] selection mode=project source=project id=${structure.ulid}`);
  }, [leftMode]);

  // --- Import mode handlers -------------------------------------------------

  const handleEnterImportMode = useCallback(() => {
    setReturnProjectSelectionId(selectedStructure?.ulid || null);
    savedProjectViewerSettingsRef.current = { ...viewerSettings };
    setViewerSettings({
      supercell: [1, 1, 1],
      repeatBoundary: true,
      displayMode: 'primitive',
      boxBounds: null,
      showBonds: true,
      showUnitCell: true,
      showLabels: false,
      atomScale: 0.4,
      bondScale: 1.0,
    });
    setLeftMode('import');
  }, [selectedStructure, viewerSettings]);

  const handleExitImportMode = useCallback(async () => {
    setOnlineSessionId(null);
    setOnlineCandidates([]);
    setSelectedOnlineCandidateId(null);
    currentOnlineCandidateIdRef.current = null;
    setRightSelection(null);
    setCurrentStructureModel(null);
    setLeftMode('project');

    if (savedProjectViewerSettingsRef.current) {
      setViewerSettings(savedProjectViewerSettingsRef.current);
      savedProjectViewerSettingsRef.current = null;
    }

    setStructureVisData(null);
    setIsLoading3D(false);

    if (returnProjectSelectionId && structures) {
      const structureToRestore = structures.find(s => s.ulid === returnProjectSelectionId);
      if (structureToRestore) {
        setSelectedStructure(structureToRestore);
      }
    }
    setReturnProjectSelectionId(null);
  }, [returnProjectSelectionId, structures]);

  const handleSelectOnlineCandidate = useCallback((sessionId: string, candidateId: string) => {
    const selectionKey = `online:${sessionId}:${candidateId}`;
    setStructureRefreshToken(t => {
      const newToken = t + 1;
      console.log('[UI_CLICK]', { selectionKey, refreshToken: newToken, ts: Date.now() });
      return newToken;
    });
    setSelectedOnlineCandidateId(candidateId);
    setOnlineSessionId(sessionId);
    setIsLoading3D(true);
    setStructureVisData(null);
  }, []);

  const handleImportOnlineCandidate = useCallback(async () => {
    if (!projectRoot || !onlineSessionId || !selectedOnlineCandidateId) return;

    try {
      const response = await qms.call('structure_import_online_candidate', {
        project_root: projectRoot,
        session_id: onlineSessionId,
        candidate_id: selectedOnlineCandidateId,
      });

      if (response.ok && response.data) {
        await fetchStructures();
        const newStructures = await qms.call('list_structures', { project_root: projectRoot });
        if (newStructures.ok && newStructures.data) {
          const structuresList = newStructures.data.structures || [];
          const newStructure = structuresList.find((s: StructureInfo) => s.ulid === (response.data as any).new_structure_ulid);
          if (newStructure) {
            handleSelectStructure(newStructure);
          }
        }
        await handleExitImportMode();
      }
    } catch (e) {
      console.error('Failed to import online candidate:', e);
    }
  }, [projectRoot, onlineSessionId, selectedOnlineCandidateId, qms, handleExitImportMode, handleSelectStructure, fetchStructures]);

  // --- Effects --------------------------------------------------------------

  // Effect 1: Reset auto-select ref when leaving structures view
  useEffect(() => {
    if (currentView !== 'structures') {
      didAutoSelectStructureRef.current = false;
    }
  }, [currentView]);

  // Effect 2: Auto-select first structure + sync list
  useEffect(() => {
    if (currentView === 'structures' && structures && structures.length > 0 && !selectedStructure && !didAutoSelectStructureRef.current) {
      const firstStructure = structures[0];
      didAutoSelectStructureRef.current = true;
      console.log(`[Structure] Auto-selecting first structure: ${firstStructure.ulid}`);
      setSelectedStructure(firstStructure);
      setRightSelection({
        kind: 'project',
        structureId: firstStructure.ulid,
      });
    }

    if (selectedStructure && structures) {
      const foundInList = structures.find(s => s.ulid === selectedStructure.ulid);
      if (!foundInList) {
        if (structures.length > 0) {
          setSelectedStructure(structures[0]);
        } else {
          setSelectedStructure(null);
        }
      } else if (foundInList !== selectedStructure) {
        setSelectedStructure(foundInList);
      }
    }
  }, [currentView, structures, selectedStructure]);

  // Effect 3: Project structure loading (PROJECT MODE ONLY)
  useEffect(() => {
    if (leftMode !== 'project') return;

    if (currentView === 'structures' && selectedStructure && projectRoot && qms) {
      const selectionKey = `project:${selectedStructure.ulid}`;
      const refreshToken = structureRefreshToken;

      console.log('[LOAD_START]', {
        selectionKey,
        refreshToken,
        mode: currentDisplayMode,
        sc: currentSupercell,
        repeat: currentRepeatBoundary,
        ts: Date.now()
      });

      const token = ++loadTokenRef.current;
      const selection: RightSelection = {
        kind: 'project',
        structureId: selectedStructure.ulid,
      };

      setIsStructureLoading(true);
      setStructureLoadError(null);
      setRightSelection(selection);

      const timeoutId = setTimeout(() => {
        if (token === loadTokenRef.current) {
          console.error('[Structure] Project structure load timeout after 10s');
          setStructureLoadError('Failed to load structure: Request timed out after 10 seconds');
          setIsStructureLoading(false);
        }
      }, 10000);

      loadStructureModel(selection, {
        supercell: currentSupercell,
        repeatBoundary: currentRepeatBoundary,
        displayMode: currentDisplayMode,
        boxBounds: currentBoxBounds,
      }).then(model => {
        clearTimeout(timeoutId);
        if (token !== loadTokenRef.current) {
          console.log(`[loadStructureModel:discard] token=${token} current=${loadTokenRef.current} - stale response discarded`);
          return;
        }

        const currentLeftMode = leftMode;
        const currentSelectedId = selectedStructure?.ulid;

        if (currentLeftMode === 'project' && selection.kind === 'project' && selection.structureId === currentSelectedId) {
          const loadStartTime = viewerStartTimeRef.current || performance.now();
          const rpcMs = performance.now() - loadStartTime;
          const atomsCount = model.vis?.n_atoms || 0;
          const bondsCount = model.vis?.n_bonds || 0;
          console.log('[LOAD_DONE]', {
            selectionKey: `project:${currentSelectedId}`,
            refreshToken,
            rpcMs: Math.round(rpcMs),
            atoms: atomsCount,
            bonds: bondsCount,
            ts: Date.now()
          });

          setCurrentStructureModel(model);
          setRightSelection(selection);
          setStructureLoadError(null);
          setIsStructureLoading(false);
          if (model.vis) {
            setStructureVisData(model.vis);
            viewerStartTimeRef.current = performance.now();
          }
        } else {
          console.warn(`[Structure] Skipping model update: mode=${currentLeftMode} selectedId=${currentSelectedId} selectionId=${selection.structureId}`);
          setIsStructureLoading(false);
        }
      }).catch(err => {
        clearTimeout(timeoutId);
        if (token !== loadTokenRef.current) {
          console.log(`[loadStructureModel:discard] token=${token} current=${loadTokenRef.current} - stale error discarded`);
          return;
        }
        console.error('[Structure] Failed to load structure model', err);
        setStructureLoadError(`Failed to load structure: ${err instanceof Error ? err.message : String(err)}`);
        setIsStructureLoading(false);
      });
    } else if (currentView !== 'structures' && structureVisData) {
      setStructureVisData(null);
      setIsStructureLoading(false);
    }
  }, [
    currentView,
    leftMode,
    selectedStructure?.ulid,
    structureRefreshToken,
    projectRoot,
    qms,
    loadStructureModel,
    currentSupercell,
    currentRepeatBoundary,
    currentDisplayMode,
    currentBoxBounds,
  ]);

  // Effect 4: Online candidate loading (IMPORT MODE ONLY)
  useEffect(() => {
    if (leftMode !== 'import') return;

    if (currentView === 'structures' && selectedOnlineCandidateId && onlineSessionId && projectRoot && qms) {
      const selectionKey = `online:${onlineSessionId}:${selectedOnlineCandidateId}`;
      const refreshToken = structureRefreshToken;

      console.log('[LOAD_START]', {
        selectionKey,
        refreshToken,
        mode: viewerSettings.displayMode || 'primitive',
        sc: viewerSettings.supercell,
        repeat: viewerSettings.repeatBoundary,
        ts: Date.now()
      });

      const token = ++loadTokenRef.current;
      const capturedCandidateId = selectedOnlineCandidateId;
      const selection: RightSelection = {
        kind: 'online',
        sessionId: onlineSessionId!,
        candidateId: capturedCandidateId,
      };

      setIsStructureLoading(true);
      setStructureLoadError(null);
      currentOnlineCandidateIdRef.current = capturedCandidateId;
      setStructureVisData(null);
      viewerStartTimeRef.current = performance.now();

      const timeoutId = setTimeout(() => {
        if (token === loadTokenRef.current) {
          console.error('[Structure] Online candidate load timeout after 10s');
          setStructureLoadError('Failed to load structure: Request timed out after 10 seconds');
          setIsStructureLoading(false);
          setIsLoading3D(false);
        }
      }, 10000);

      loadStructureModel(selection, {
        supercell: viewerSettings.supercell,
        repeatBoundary: viewerSettings.repeatBoundary,
        displayMode: viewerSettings.displayMode || 'primitive',
        boxBounds: viewerSettings.boxBounds,
        showBonds: true,
        showUnitCell: true,
        showLabels: false,
        atomScale: 0.4,
        bondScale: 1.0,
      }).then(model => {
        clearTimeout(timeoutId);
        if (token !== loadTokenRef.current) {
          console.log(`[loadStructureModel:discard] token=${token} current=${loadTokenRef.current} - stale response discarded`);
          return;
        }

        if (leftMode === 'import' && capturedCandidateId === currentOnlineCandidateIdRef.current) {
          const rpcMs = performance.now() - (viewerStartTimeRef.current || performance.now());
          const atomsCount = model.vis?.n_atoms || 0;
          const bondsCount = model.vis?.n_bonds || 0;
          console.log('[LOAD_DONE]', {
            selectionKey: `online:${onlineSessionId}:${capturedCandidateId}`,
            refreshToken,
            rpcMs: Math.round(rpcMs),
            atoms: atomsCount,
            bonds: bondsCount,
            ts: Date.now()
          });

          setCurrentStructureModel(model);
          setRightSelection(selection);
          setStructureLoadError(null);
          setIsStructureLoading(false);
          setIsLoading3D(false);
          if (model.vis) {
            setStructureVisData(model.vis);
            viewerStartTimeRef.current = performance.now();
          }
        } else {
          console.warn(`[Structure] Skipping online model update: mode=${leftMode} candidateId=${capturedCandidateId}`);
          setIsStructureLoading(false);
          setIsLoading3D(false);
        }
      }).catch(err => {
        clearTimeout(timeoutId);
        if (token !== loadTokenRef.current) {
          console.log(`[loadStructureModel:discard] token=${token} current=${loadTokenRef.current} - stale error discarded`);
          return;
        }
        console.error('[Structure] Failed to load online candidate model', err);
        setStructureLoadError(`Failed to load structure: ${err instanceof Error ? err.message : String(err)}`);
        setIsStructureLoading(false);
        setIsLoading3D(false);
      });
    } else if (currentView !== 'structures' && structureVisData) {
      setStructureVisData(null);
    }
  }, [
    currentView,
    leftMode,
    selectedOnlineCandidateId,
    onlineSessionId,
    structureRefreshToken,
    projectRoot,
    qms,
    loadStructureModel,
    viewerSettings.supercell,
    viewerSettings.repeatBoundary,
    viewerSettings.displayMode,
    viewerSettings.boxBounds,
  ]);

  // Effect 5: Clear all on project root change
  useEffect(() => {
    setSelectedStructure(null);
    setCurrentStructureModel(null);
    setRightSelection(null);
    setStructureVisData(null);
    setStructureLoadError(null);
    setIsStructureLoading(false);
    setIsLoading3D(false);
    didAutoSelectStructureRef.current = false;
  }, [projectRoot]);

  // --- Memoised context value -----------------------------------------------
  const value = useMemo<StructureContextValue>(() => ({
    selectedStructure,
    setSelectedStructure,
    currentStructureModel,
    rightSelection,
    structureVisData,
    structureLoadError,
    viewerSettings,
    setViewerSettings,
    currentSupercell,
    setCurrentSupercell,
    currentRepeatBoundary,
    setCurrentRepeatBoundary,
    currentDisplayMode,
    setCurrentDisplayMode,
    currentBoxBounds,
    setCurrentBoxBounds,
    isStructureLoading,
    isLoading3D,
    structureRefreshToken,
    setStructureRefreshToken,
    leftMode,
    onlineSessionId,
    onlineCandidates,
    selectedOnlineCandidateId,
    loadTokenRef,
    viewerStartTimeRef,
    currentTraceIdRef,
    handleSelectStructure,
    handleEnterImportMode,
    handleExitImportMode,
    handleSelectOnlineCandidate,
    handleImportOnlineCandidate,
    handleViewerFirstFrame,
    loadStructureModel,
    setCurrentStructureModel,
    setStructureVisData,
    setRightSelection,
    setStructureLoadError,
    setIsStructureLoading,
    setIsLoading3D,
  }), [
    selectedStructure,
    currentStructureModel,
    rightSelection,
    structureVisData,
    structureLoadError,
    viewerSettings,
    currentSupercell,
    currentRepeatBoundary,
    currentDisplayMode,
    currentBoxBounds,
    isStructureLoading,
    isLoading3D,
    structureRefreshToken,
    leftMode,
    onlineSessionId,
    onlineCandidates,
    selectedOnlineCandidateId,
    handleSelectStructure,
    handleEnterImportMode,
    handleExitImportMode,
    handleSelectOnlineCandidate,
    handleImportOnlineCandidate,
    handleViewerFirstFrame,
    loadStructureModel,
  ]);

  return (
    <StructureContext.Provider value={value}>
      {children}
    </StructureContext.Provider>
  );
}
