/**
 * QuantumVITAS JSON-RPC Types
 * 
 * These types mirror the daemon protocol defined in
 * src/quantumvitas/daemon/server.py
 */

// =============================================================================
// Core RPC Types
// =============================================================================

/** Available daemon command types */
export type QVCommandType =
  // System
  | 'ping'
  | 'shutdown'
  // Project/resource listing
  | 'get_project_summary'
  | 'list_structures'
  | 'list_workflows'
  // Visualization data
  | 'get_structure_vis'
  | 'get_scf_convergence'
  | 'get_dos_data'
  | 'get_band_structure_data'
  // Job management
  | 'run_workflow'
  | 'run_step'
  | 'get_job_status'
  | 'list_jobs'
  | 'cancel_job';

/** JSON-RPC request sent to daemon */
export interface QVRequest<T = Record<string, unknown>> {
  id: string;
  type: QVCommandType;
  payload: T;
}

/** Error structure from daemon */
export interface QVError {
  code: string;
  message: string;
  available_commands?: string[];
}

/** JSON-RPC response from daemon */
export interface QVResponse<T = Record<string, unknown>> {
  id: string;
  ok: boolean;
  data?: T;
  error?: QVError;
}

// =============================================================================
// Payload Types (requests)
// =============================================================================

export interface ProjectRootPayload {
  project_root: string;
}

export interface StructureVisPayload extends ProjectRootPayload {
  selector: string;
  supercell?: [number, number, number];
  repeat_boundary?: boolean;
}

export interface WorkflowStepPayload extends ProjectRootPayload {
  workflow: string;
  step?: string;
}

export interface RunWorkflowPayload extends ProjectRootPayload {
  workflow: string;
  strict?: boolean;
  verbose?: boolean;
}

export interface RunStepPayload extends ProjectRootPayload {
  workflow: string;
  step: string;
  verbose?: boolean;
}

export interface JobIdPayload {
  job_id: string;
}

export interface ListJobsPayload {
  status?: JobStatus;
  job_type?: string;
}

// =============================================================================
// Response Data Types
// =============================================================================

export interface PingData {
  pong: boolean;
  version: string;
}

export interface ShutdownData {
  shutdown: boolean;
}

export interface ProjectSummaryData {
  name: string;
  path: string;
  structure_count: number;
  workflow_count: number;
  structures: string[];
  workflows: string[];
}

export interface StructureInfo {
  name: string;
  slug: string;
  ulid: string;
  path: string;
  formula?: string;
  num_atoms?: number;
  lattice_type?: string;
}

export interface ListStructuresData {
  structures: StructureInfo[];
  count: number;
}

export interface WorkflowInfo {
  name: string;
  slug: string;
  ulid: string;
  path: string;
  step_count?: number;
  steps?: string[];
}

export interface ListWorkflowsData {
  workflows: WorkflowInfo[];
  count: number;
}

export interface AtomVisData {
  element: string;
  position: [number, number, number];
  color: string;
  radius: number;
}

export interface BondVisData {
  start: [number, number, number];
  end: [number, number, number];
}

export interface StructureVisData {
  lattice_vectors: [[number, number, number], [number, number, number], [number, number, number]];
  atoms: AtomVisData[];
  bonds: BondVisData[];
  formula: string;
  num_atoms: number;
}

export interface ScfConvergenceData {
  iterations: number[];
  energies: number[];
  delta_energies: number[];
  converged: boolean;
  final_energy: number | null;
}

export interface DosData {
  energies: number[];
  dos_up: number[];
  dos_down?: number[];
  fermi_energy: number | null;
  integrated_dos?: number[];
}

export interface BandPoint {
  label: string;
  k_distance: number;
  k_coords: [number, number, number] | null;
}

export interface BandStructureData {
  k_distances: number[];
  energies: number[][];  // [band_index][k_index]
  fermi_energy: number | null;
  high_symmetry_points: BandPoint[];
  num_bands: number;
  num_kpoints: number;
}

// Job status enum
export type JobStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';

export interface JobInfo {
  job_id: string;
  job_type: string;
  status: JobStatus;
  submitted_at: string;
  started_at?: string;
  completed_at?: string;
  error?: string;
  result?: Record<string, unknown>;
}

export interface JobSubmitData {
  job_id: string;
  status: JobStatus;
}

export interface ListJobsData {
  jobs: JobInfo[];
  count: number;
}

export interface CancelJobData {
  job_id: string;
  cancelled: boolean;
}

// =============================================================================
// Window API Type (for preload)
// =============================================================================

export interface QVApi {
  /**
   * Send a request to the Python daemon
   * @param type - Command type
   * @param payload - Command payload
   * @returns Promise with response data
   */
  request: <T = Record<string, unknown>>(
    type: QVCommandType,
    payload?: Record<string, unknown>
  ) => Promise<QVResponse<T>>;
  
  /**
   * Subscribe to daemon log messages
   * @param callback - Function to call with log messages
   * @returns Unsubscribe function
   */
  onLog: (callback: (message: string) => void) => () => void;
  
  /**
   * Check if daemon is connected
   */
  isConnected: () => Promise<boolean>;
  
  /**
   * Subscribe to main process messages (e.g., 'ready')
   * @param callback - Function to call with message data
   * @returns Unsubscribe function
   */
  onMainMessage: (callback: (data: unknown) => void) => () => void;
}

// Extend Window interface
declare global {
  interface Window {
    qv: QVApi;
  }
}

