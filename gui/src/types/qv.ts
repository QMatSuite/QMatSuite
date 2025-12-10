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
  kind?: string;  // Resource kind for resource_not_found errors (e.g., "step", "workflow", "structure")
  selector?: string;  // Selector that was not found
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

export interface WorkflowTemplateInfo {
  name: string;
  path: string;
  description?: string;
  n_steps: number;
  step_types: string[];
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

/** Analysis type for ensure_workflow_analysis */
export type AnalysisType = 'scf' | 'dos' | 'bands';

/** Result of ensure_workflow_analysis RPC call */
export interface AnalysisStatus {
  ok: boolean;
  analysis_type: AnalysisType;
  artifact_path: string | null;
  parsed_fresh: boolean;  // True if just parsed (vs loaded from cache)
  error: string | null;
  summary: {
    // SCF summary
    converged?: boolean;
    n_iterations?: number;
    total_energy_ry?: number;
    // DOS/bands summary
    n_points?: number;
    n_bands?: number;
    n_kpoints?: number;
    n_high_symmetry_points?: number;
    // Common
    fermi_energy_ev?: number | null;
    energy_range_ev?: [number, number];
  } | null;
}

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
  target_name: string | null;
  project_root: string | null;
  output_file: string | null;
  last_log_line: string | null;
}

export interface JobSummary {
  id: string;
  job_type: string;
  status: JobStatus;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  target_name: string | null;
  project_root: string | null;
  error: string | null;
  last_log_line: string | null;
}

export interface JobSubmitResult {
  job_id: string;
  status: JobStatus;
  target_name: string;
}

export interface JobLogs {
  job_id: string;
  logs: string[];
  total_lines: number;
  has_more: boolean;
  output_file: string | null;
}

export interface JobCounts {
  counts: Record<string, number>;
  running: number;
  pending: number;
}

// =============================================================================
// Command Map - Central Type-Safe API Definition
// =============================================================================

// =============================================================================
// Data Types - Environment
// =============================================================================

export interface QEDetectionResult {
  found: boolean;
  qe_home: string | null;
  version: string | null;
  executables: string[];
  detection_source: string | null;
}

export interface EnvironmentInfo {
  python_version: string;
  python_executable: string;
  qv_version: string;
  qe_home: string | null;
  qe_found: boolean;
}

// =============================================================================
// Data Types - Step Detail
// =============================================================================

export interface StepDetail {
  id: string;
  name: string;
  slug: string;
  path: string;
  absolute_path: string;
  step_type: string;
  structure: string | null;
  parent_workflow_id: string | null;
  parameters: Record<string, Record<string, unknown>>;
  cards: Record<string, Record<string, unknown>>;
  species_overrides: Record<string, Record<string, unknown>>;
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
  
  // Environment and settings
  detect_qe: {
    payload: Record<string, never>;
    result: QEDetectionResult;
  };
  get_env_info: {
    payload: Record<string, never>;
    result: EnvironmentInfo;
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
  
  // Analysis - ensure artifacts exist
  ensure_workflow_analysis: {
    payload: {
      project_root: string;
      workflow: string;
      analysis_type: AnalysisType;
      step?: string;
      force?: boolean;
    };
    result: AnalysisStatus;
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
  
  get_reference_analysis: {
    payload: {
      project_root: string;
      workflow: string;
      analysis_type: 'scf' | 'dos' | 'bands';
    };
    result: {
      data: ScfConvergenceData | DosData | BandStructureData | null;
      has_reference: boolean;
    };
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
  get_job_logs: {
    payload: {
      job_id: string;
      tail_lines?: number;
      offset?: number;
    };
    result: JobLogs;
  };
  list_jobs: {
    payload: {
      status?: JobStatus;
      job_type?: string;
      project_root?: string;
      limit?: number;
    };
    result: { jobs: JobSummary[]; count: number };
  };
  job_counts: {
    payload: Record<string, never>;
    result: JobCounts;
  };
  cancel_job: {
    payload: { job_id: string };
    result: { job_id: string; cancelled: boolean };
  };
  
  // Project creation
  create_project: {
    payload: {
      target_dir: string;
      name?: string;
      template?: string;
    };
    result: {
      project_root: string;
      name: string;
      id: string;
    };
  };
  
  // Structure import
  import_structure: {
    payload: {
      project_root: string;
      source_file: string;
      name?: string;
    };
    result: {
      structure_id: string;
      name: string;
      slug: string;
      formula: string;
      n_atoms: number;
    };
  };
  
  // Structure management
  rename_structure: {
    payload: {
      project_root: string;
      selector: string;
      new_name: string;
    };
    result: {
      success: boolean;
      old_name: string;
      new_name: string;
      new_slug: string;
    };
  };
  can_delete_structure: {
    payload: {
      project_root: string;
      selector: string;
    };
    result: {
      can_delete: boolean;
      using_workflows: string[];
      structure_name: string;
    };
  };
  delete_structure: {
    payload: {
      project_root: string;
      selector: string;
      force?: boolean;
    };
    result: {
      success: boolean;
      name: string;
    };
  };
  
  // Workflow templates
  list_workflow_templates: {
    payload: Record<string, never>;
    result: {
      templates: WorkflowTemplateInfo[];
      count: number;
    };
  };
  
  create_workflow: {
    payload: {
      project_root: string;
      name: string;
      structure?: string;
      template?: string;
    };
    result: {
      workflow_id: string;
      name: string;
      slug: string;
      n_steps: number;
    };
  };
  
  // Workflow management
  rename_workflow: {
    payload: {
      project_root: string;
      selector: string;
      new_name: string;
    };
    result: {
      success: boolean;
      old_name: string;
      new_name: string;
      new_slug: string;
    };
  };
  can_delete_workflow: {
    payload: {
      project_root: string;
      selector: string;
    };
    result: {
      workflow_name: string;
      dependent_workflows: string[];
      has_dependencies: boolean;
    };
  };
  delete_workflow: {
    payload: {
      project_root: string;
      selector: string;
      force?: boolean;
    };
    result: {
      success: boolean;
      name: string;
    };
  };
  
  // Step operations
  get_step_detail: {
    payload: {
      project_root: string;
      workflow: string;
      step: string;
    };
    result: StepDetail;
  };
  update_step_params: {
    payload: {
      project_root: string;
      workflow: string;
      step: string;
      parameters: Record<string, Record<string, unknown>>;
      cards?: Record<string, Record<string, unknown>>;
    };
    result: StepDetail;
  };
  reset_step_params: {
    payload: {
      project_root: string;
      workflow: string;
      step: string;
    };
    result: StepDetail;
  };
  import_step_from_qe_input: {
    payload: {
      project_root: string;
      workflow: string;
      input_file: string;
      step_name?: string;
    };
    result: WorkflowDetailResult;
  };
  add_step_to_workflow: {
    payload: {
      project_root: string;
      workflow: string;
      step_type: string;
      step_name?: string;
    };
    result: WorkflowDetailResult;
  };
  
  // Workflow configuration
  get_workflow_detail: {
    payload: {
      project_root: string;
      workflow: string;
    };
    result: WorkflowDetailResult;
  };
  reorder_workflow_steps: {
    payload: {
      project_root: string;
      workflow: string;
      new_order: string[];
    };
    result: WorkflowDetailResult;
  };
  change_workflow_structure: {
    payload: {
      project_root: string;
      workflow: string;
      new_structure: string;
      update_steps?: boolean;
    };
    result: WorkflowStructureChangeResult;
  };
  
  // Pre-flight checks
  preflight_check: {
    payload: {
      project_root: string;
      workflow?: string;
      step?: string;
    };
    result: PreflightCheckResult;
  };
  
  // Demo project
  create_demo_project: {
    payload: {
      target_dir: string;
      name?: string;
      demo_id?: string;
    };
    result: DemoProjectResult;
  };
  list_demo_projects: {
    payload: Record<string, never>;
    result: {
      demos: DemoProjectInfo[];
      count: number;
    };
  };
  
  // Find project root (search up)
  find_project_root: {
    payload: {
      start_dir: string;
    };
    result: {
      found: boolean;
      project_root: string | null;
    };
  };
}

// =============================================================================
// Extended Result Types
// =============================================================================

export interface WorkflowDetailResult {
  id: string;
  name: string;
  slug: string;
  path: string;
  absolute_path: string;
  structure: string | null;
  mode: string;
  n_steps: number;
  steps: Array<{
    id: string;
    slug: string;
    type: string;
    step_file: string;
  }>;
}

export interface WorkflowStructureChangeResult extends WorkflowDetailResult {
  old_structure: string | null;
  updated_steps: Array<{
    step_id: string;
    old_structure: string;
    new_structure: string;
  }>;
  warnings: string[];
}

export interface PreflightCheck {
  name: string;
  ok: boolean;
  message: string;
}

export interface PreflightCheckResult {
  ok: boolean;
  checks: PreflightCheck[];
  errors: string[];
  warnings: string[];
}

export interface DemoProjectInfo {
  id: string;
  name: string;
  title?: string;
  subtitle?: string;
  description: string;
  recommended_use: string;
  recommended_analysis?: string | null;
  tags?: string[];
  difficulty?: string;
  estimated_runtime_scf?: number | null;
}

export interface DemoProjectResult {
  project_root: string;
  project_id: string;
  project_name: string;
  structure: {
    structure_id: string;
    name: string;
    slug: string;
    formula: string;
    n_atoms: number;
  } | null;
  workflow: {
    workflow_id: string;
    name: string;
    slug: string;
    n_steps: number;
  } | null;
  ready_to_run: boolean;
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
  
  /**
   * Open a native directory picker dialog
   */
  openDirectory: () => Promise<string | null>;
  
  /**
   * Open a native file picker dialog
   */
  openFile: (options?: {
    title?: string;
    filters?: { name: string; extensions: string[] }[];
  }) => Promise<string | null>;
  
  /**
   * Set the current project path for log file storage
   */
  setProject: (projectPath: string | null) => Promise<void>;
  
  /**
   * Read logs from a project's log file
   */
  readLogs: (projectPath: string, tailLines?: number) => Promise<string[]>;
  
  /**
   * Reveal a file or folder in the native file manager (Finder/Explorer)
   */
  revealPath: (targetPath: string) => Promise<boolean>;
}

// Extend Window interface
declare global {
  interface Window {
    qv: QVApi;
  }
}
