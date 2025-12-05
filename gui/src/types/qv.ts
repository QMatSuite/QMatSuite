/**
 * QuantumVITAS JSON-RPC Types
 * 
 * These types mirror the daemon protocol defined in
 * src/quantumvitas/daemon/server.py
 * 
 * Uses a centralized QVCommandMap for end-to-end type safety.
 */

// =============================================================================
// Daemon Status
// =============================================================================

export interface DaemonStatus {
  connected: boolean;
  startupError: string | null;
  pythonPath: string | null;
  projectRoot: string | null;
}

// =============================================================================
// Response Types
// =============================================================================

export interface QVError {
  code: string;
  message: string;
  available_commands?: string[];
}

export interface QVResponse<T = unknown> {
  id: string;
  ok: boolean;
  data?: T;
  error?: QVError;
}

// =============================================================================
// Data Types - Structures
// =============================================================================

export interface LatticeParams {
  a: number;
  b: number;
  c: number;
  alpha: number;
  beta: number;
  gamma: number;
  volume?: number;
}

export interface StructureInfo {
  id: string;
  name: string;
  slug: string;
  path: string;
  absolute_path: string;
  formula: string;
  n_atoms: number;
  n_species: number;
  lattice_params: LatticeParams;
}

export interface AtomVisData {
  index: number;
  element: string;
  cart_coords: [number, number, number];
  frac_coords: [number, number, number];
  color: string;
  radius: number;
}

export interface BondVisData {
  idx1: number;
  idx2: number;
  coord1: [number, number, number];
  coord2: [number, number, number];
  distance: number;
}

export interface LatticeVisData {
  matrix: [[number, number, number], [number, number, number], [number, number, number]];
  a: number;
  b: number;
  c: number;
  alpha: number;
  beta: number;
  gamma: number;
  volume: number;
}

export interface StructureVisData {
  structure_id: string;
  structure_name: string;
  formula: string;
  n_atoms: number;
  n_boundary_atoms: number;
  n_bonds: number;
  supercell: [number, number, number];
  lattice: LatticeVisData;
  atoms: AtomVisData[];
  boundary_atoms: AtomVisData[];
  bonds: BondVisData[];
  element_colors: Record<string, string>;
}

// =============================================================================
// Data Types - Workflows
// =============================================================================

export interface StepInfo {
  id: string;
  type: string;
  step_file: string;
}

export interface WorkflowInfo {
  id: string;
  name: string;
  slug: string;
  path: string;
  absolute_path: string;
  structure: string;
  mode: string;
  n_steps: number;
  steps: StepInfo[];
}

// =============================================================================
// Data Types - Project
// =============================================================================

export interface ProjectSummary {
  id: string;
  name: string;
  slug: string;
  path: string;
  n_structures: number;
  n_workflows: number;
  structure_names: string[];
  workflow_names: string[];
}

// =============================================================================
// Data Types - Analysis
// =============================================================================

export interface ScfIteration {
  iteration: number;
  total_energy_ry: number;
  scf_accuracy_ry: number;
}

export interface ScfConvergenceData {
  workflow: string;
  step: string;
  output_file: string;
  converged: boolean;
  n_iterations: number;
  total_energy_ry: number;
  fermi_energy_ev: number | null;
  iterations: ScfIteration[];
  calculation_type: string;
  n_electrons: number;
  n_kpoints: number;
  ecutwfc_ry: number;
  units: { energy: string; fermi: string };
}

export interface DosData {
  workflow: string;
  step: string;
  data_file: string;
  n_points: number;
  fermi_energy_ev: number | null;
  energy_range_ev: [number, number];
  energies_ev: number[];
  dos_states_per_ev: number[];
  idos: number[];
  units: { energy: string; dos: string };
}

export interface HighSymmetryPoint {
  label: string;
  k_distance: number;
  k_coords: [number, number, number] | null;
}

export interface BandStructureData {
  workflow: string;
  step: string;
  data_file: string;
  n_bands: number;
  n_kpoints: number;
  fermi_energy_ev: number | null;
  k_distances: number[];
  energies_ev: number[][];
  high_symmetry_points: HighSymmetryPoint[];
  units: { energy: string; k_distance: string };
}

// =============================================================================
// Data Types - Jobs
// =============================================================================

export type JobStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface JobInfo {
  id: string;
  job_type: string;
  status: JobStatus;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  result: Record<string, unknown> | null;
  error: string | null;
  params: Record<string, unknown>;
}

export interface JobSubmitResult {
  job_id: string;
  status: JobStatus;
}

// =============================================================================
// Command Map - Central Type-Safe API Definition
// =============================================================================

/**
 * Central command map defining all RPC commands with their payloads and results.
 * 
 * This provides end-to-end type safety for RPC calls:
 * - Payload types are enforced at call sites
 * - Result types are inferred from responses
 */
export interface QVCommandMap {
  // System commands
  ping: {
    payload: Record<string, never>;  // Empty object
    result: { pong: boolean; version: string };
  };
  shutdown: {
    payload: Record<string, never>;
    result: { shutdown: boolean };
  };
  
  // Project/resource listing
  get_project_summary: {
    payload: { project_root: string };
    result: ProjectSummary;
  };
  list_structures: {
    payload: { project_root: string };
    result: { structures: StructureInfo[]; count: number };
  };
  list_workflows: {
    payload: { project_root: string };
    result: { workflows: WorkflowInfo[]; count: number };
  };
  
  // Visualization data
  get_structure_vis: {
    payload: {
      project_root: string;
      selector: string;
      supercell?: [number, number, number];
      repeat_boundary?: boolean;
    };
    result: StructureVisData;
  };
  get_scf_convergence: {
    payload: {
      project_root: string;
      workflow: string;
      step: string;
    };
    result: ScfConvergenceData;
  };
  get_dos_data: {
    payload: {
      project_root: string;
      workflow: string;
      step?: string;
    };
    result: DosData;
  };
  get_band_structure_data: {
    payload: {
      project_root: string;
      workflow: string;
      step?: string;
    };
    result: BandStructureData;
  };
  
  // Job management
  run_workflow: {
    payload: {
      project_root: string;
      workflow: string;
      strict?: boolean;
      verbose?: boolean;
    };
    result: JobSubmitResult;
  };
  run_step: {
    payload: {
      project_root: string;
      workflow: string;
      step: string;
      verbose?: boolean;
    };
    result: JobSubmitResult;
  };
  get_job_status: {
    payload: { job_id: string };
    result: JobInfo;
  };
  list_jobs: {
    payload: {
      status?: JobStatus;
      job_type?: string;
    };
    result: { jobs: JobInfo[]; count: number };
  };
  cancel_job: {
    payload: { job_id: string };
    result: { job_id: string; cancelled: boolean };
  };
}

/** All available command types */
export type QVCommandType = keyof QVCommandMap;

/** Get payload type for a command */
export type QVPayload<K extends QVCommandType> = QVCommandMap[K]['payload'];

/** Get result type for a command */
export type QVResult<K extends QVCommandType> = QVCommandMap[K]['result'];

// =============================================================================
// Window API Type (for preload)
// =============================================================================

export interface QVApi {
  /**
   * Send a typed request to the Python daemon
   */
  request: <T = unknown>(
    type: string,
    payload?: Record<string, unknown>
  ) => Promise<QVResponse<T>>;
  
  /**
   * Subscribe to daemon log messages
   */
  onLog: (callback: (message: string) => void) => () => void;
  
  /**
   * Check if daemon is connected
   */
  isConnected: () => Promise<boolean>;
  
  /**
   * Get detailed daemon status
   */
  getDaemonStatus: () => Promise<DaemonStatus>;
  
  /**
   * Subscribe to daemon status changes
   */
  onDaemonStatus: (callback: (status: DaemonStatus) => void) => () => void;
  
  /**
   * Subscribe to main process messages
   */
  onMainMessage: (callback: (data: unknown) => void) => () => void;
}

// Extend Window interface
declare global {
  interface Window {
    qv: QVApi;
  }
}
