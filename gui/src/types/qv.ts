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
  kind?: string;  // Resource kind for resource_not_found/registry_out_of_sync errors (e.g., "step", "calculation", "structure")
  selector?: string;  // Selector that was not found
  id?: string;  // Resource ID if known
  expected_path?: string;  // Expected path from registry (for registry_out_of_sync)
  actual_state?: string;  // Description of what was wrong (for registry_out_of_sync)
  details?: {
    project_root?: string;
    hint?: string;
    calculation_path?: string;
    expected_step_path?: string;
    expected_path?: string;
    step_id?: string;
    structure_id?: string;
    reason?: string;  // e.g., "step_file_missing", "step_not_in_calculation_dag"
    actual_state?: string;
  };
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
  is_boundary?: boolean;  // P1-2: Flag to mark boundary atoms (new contract)
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
  display_mode?: 'primitive' | 'supercell' | 'conventional' | 'box';
  lattice: LatticeVisData;
  atoms: AtomVisData[];
  boundary_atoms: AtomVisData[];
  bonds: BondVisData[];
  element_colors: Record<string, string>;
  perf?: {  // Optional performance metrics from backend
    trace_id: string;
    prep_ms: number;
    bonds_ms: number;
    ser_ms: number;
    total_ms: number;
    atoms: number;
    bonds: number;
    bytes: number;
  };
}

// =============================================================================
// Unified Structure Model (for both project and online)
// =============================================================================

export interface Provenance {
  source_name: string;
  provider?: string;
  database?: string;
  base_url?: string;
  optimade_id?: string;
  aiida_uuid?: string;
  created?: string;
  modified?: string;
  owner?: string;
  node_type?: string;
  extras?: Record<string, any>;
  attributes?: Record<string, any>;
  raw?: Record<string, any>;
  cod_id?: string;
}

export interface StructureModel {
  id: string;  // project id or "online:<candidateId>"
  name: string;
  formula: string;
  nsites: number;
  species: string[];  // unique species symbols
  lattice: number[][];  // 3x3 matrix
  atoms: Array<{
    element: string;
    frac: [number, number, number];
    cart?: [number, number, number];
    index?: number;
  }>;
  bonds: Array<{
    i: number;
    j: number;
    order?: number;
    distance?: number;
  }>;
  // Viewer data (from StructureVisData)
  vis?: StructureVisData;
  // Provenance (for online structures)
  provenance?: Provenance | null;
  // Additional fields from existing payload
  n_boundary_atoms?: number;
  supercell?: [number, number, number];
  display_mode?: 'primitive' | 'supercell' | 'conventional' | 'box';
  element_colors?: Record<string, string>;
}

export type RightSelection =
  | { kind: "project"; structureId: string }
  | { kind: "online"; sessionId: string; candidateId: string };

// =============================================================================
// Data Types - Calculations
// =============================================================================

export interface StepInfo {
  id: string;
  type: string;
  step_file: string;
}

export interface CalculationInfo {
  id: string;
  name: string;
  slug: string;
  path: string;
  absolute_path: string;
  structure: string | null;  // Can be null in DAG + ULID model
  mode: string;
  n_steps: number;
  steps: StepInfo[];
}

export interface CalculationTemplateInfo {
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
  n_calculations: number;
  structure_names: string[];
  calculation_names: string[];
}

// =============================================================================
// Data Types - Analysis
// =============================================================================

/** Analysis type for ensure_calculation_analysis */
export type AnalysisType = 'scf' | 'dos' | 'bands';

/** Result of ensure_calculation_analysis RPC call */
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
  calculation: string;
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
  calculation: string;
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
  calculation: string;
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

export interface JobStepInfo {
  step_id?: string;
  step_type: string;
  status: JobStatus;
  started_at?: string | null;
  ended_at?: string | null;
}

export interface JobInfo {
  id: string;  // Job ID (ULID) - equals run_id in History for unified identity
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
  // TODO: Backend should include these fields in get_job_status response
  steps?: JobStepInfo[];  // Step-level progress info
  io_dir?: string | null;  // Absolute path to I/O directory (the actual directory used by the runner to write QE input/output and artifacts)
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
  // TODO: Backend should include these fields in list_jobs response for step progress visualization
  steps?: JobStepInfo[];  // Step-level progress info (for stepper visualization)
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
  qe_bin_dir: string | null;
  version: string | null;
  executables: string[];
  mode?: 'internal' | 'external';
  error?: string;
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
  parent_calculation_id: string | null;
  parameters: Record<string, Record<string, unknown>>;
  cards: Record<string, Record<string, unknown>>;
  species_overrides: Record<string, Record<string, unknown>>;
  parameter_scan?: Record<string, { values: unknown[] }>;  // scan_id -> { values: [...] }
  prefix_outdir_injection?: {
    effective_prefix?: string;
    effective_outdir?: string;
    ignored_step_prefix?: string;
    ignored_step_outdir?: string;
  } | null;
}

// =============================================================================
// Data Types - Pseudopotential Archives
// =============================================================================

export interface ArchiveStatus {
  asset_name: string;
  relative_path: string;
  sha256: string;
  size_bytes: number;
  library_name: string;
  library_version: string;
  xc?: string;
  quality?: string;
  type?: string;
  relativistic?: string;
  category?: string;
  installed: boolean;
  corrupt?: boolean;
  warning?: string;
  upstream_url?: string;
}

export interface ArchiveInstallResult {
  success: boolean;
  messages: string[];
  errors: string[];
  archive_status?: ArchiveStatus;
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
  list_qe_engines: {
    payload: Record<string, never>;
    result: {
      current_mode: 'internal' | 'external';
      current_bin_dir: string | null;
      internal_engines: Array<{
        bin_dir: string;
        engine_path: string;
        pw_path: string;
      }>;
    };
  };
  discover_qe_engines: {
    payload: Record<string, never>;
    result: {
      discovered_engines: Array<{
        engine_id: string;
        label: string;
        qe_home: string;
        pw_path: string;
      }>;
      cached_at: number;
    };
  };
  set_qe_engine: {
    payload: {
      bin_dir?: string | null;
    };
    result: {
      success: boolean;
    };
  };
  
  // Pseudopotential configuration
  get_pseudo_config: {
    payload: Record<string, never>;
    result: {
      store_dir: string;
      seed_dir: string;
      allow_download: boolean;
      repo_pseudo_dir: string;
      default_store_dir: string;
      default_seed_dir: string;
    };
  };
  set_pseudo_config: {
    payload: {
      store_dir?: string;
      seed_dir?: string;
      allow_download?: boolean;
    };
    result: {
      store_dir: string;
      seed_dir: string;
      allow_download: boolean;
      repo_pseudo_dir: string;
      default_store_dir: string;
      default_seed_dir: string;
    };
  };
  validate_pseudo_config: {
    payload: Record<string, never>;
    result: {
      ok: boolean;
      repo_pseudo_exists: boolean;
      store_dir_exists: boolean;
      store_dir_writable: boolean;
      seed_dir_exists: boolean;
      seed_has_sssp: boolean;
      messages: string[];
      warnings: string[];
      errors: string[];
    };
  };
  init_pseudo_dirs: {
    payload: Record<string, never>;
    result: {
      store_dir_created: boolean;
      seed_dir_created: boolean;
      messages: string[];
      errors: string[];
    };
  };
  install_seed_to_store: {
    payload: {
      version?: string;
      flavor?: string;
    };
    result: {
      success: boolean;
      installed?: Array<{ version: string; flavor: string; files: number }>;
      skipped?: Array<{ version: string; flavor: string }>;
      failed?: Array<{ version: string; flavor: string; errors: string[] }>;
      messages: string[];
      errors?: string[];
    };
  };
  list_installed_sssp: {
    payload: Record<string, never>;
    result: {
      libraries: Array<{
        version: string;
        flavor: string;
        installed: boolean;
        path: string | null;
        file_count: number;
        has_cutoffs: boolean;
        has_manifest: boolean;
      }>;
    };
  };
  list_seed_archives: {
    payload: Record<string, never>;
    result: {
      archives: Array<{
        filename: string;
        path: string;
        size_bytes: number;
        sha256: string | null;
        version: string | null;
        flavor: string | null;
      }>;
    };
  };
  import_seed_archives: {
    payload: {
      file_paths: string[];
    };
    result: {
      imported: string[];
      skipped: string[];
      errors: string[];
    };
  };
  download_sssp_library: {
    payload: {
      flavor: 'efficiency' | 'precision';
      version?: string;
      force?: boolean;
    };
    result: {
      success: boolean;
      version: string;
      flavor: string;
      files_installed: number;
      messages: string[];
      errors: string[];
      warnings: string[];
      installed_libraries: Array<{
        version: string;
        flavor: string;
        installed: boolean;
        path: string | null;
        file_count: number;
        has_cutoffs: boolean;
        has_manifest: boolean;
      }>;
    };
  };
  list_pseudo_archives_status: {
    payload: Record<string, never>;
    result: {
      archives: ArchiveStatus[];
      grouped_by_library?: Record<string, ArchiveStatus[]>;
      error?: string;
    };
  };
  install_pseudo_archive: {
    payload: {
      asset_name: string;
      force?: boolean;
    };
    result: ArchiveInstallResult;
  };
  download_all_sssp: {
    payload: {
      force?: boolean;
    };
    result: {
      success: boolean;
      installed: Array<{ version: string; flavor: string; files: number }>;
      skipped: Array<{ version: string; flavor: string }>;
      failed: Array<{ version: string; flavor: string; errors: string[] }>;
      messages: string[];
      installed_libraries: Array<{
        version: string;
        flavor: string;
        installed: boolean;
        path: string | null;
        file_count: number;
        has_cutoffs: boolean;
        has_manifest: boolean;
      }>;
    };
  };
  list_qe_ui_parameters: {
    payload: {
      module: string;
      step_type: string;
    };
    result: {
      parameters: Array<{
        namelist: string;
        name: string;
        label: string;
        type: string;
        unit?: string;
        description?: string;
        options?: string[] | null;
        importance?: string;
      }>;
    };
  };
  list_qe_parameter_metadata: {
    payload: {
      operation: 'list_modules' | 'list_sections' | 'list_parameters' | 'search';
      module?: string;
      section?: string;
      query?: string;
    };
    result: {
      modules?: Array<{
        id: string;
        label: string;
        doc_url?: string;
      }>;
      sections?: Array<{
        id: string;
        name: string;  // Clean name without '&' prefix
        kind: 'namelist' | 'card';
        label: string;  // Display label from metadata (includes '&' for namelists, raw for cards)
      }>;
      parameters?: Array<{
        name: string;
        type: string | null;
        default: string | number | null;
        enum: string[] | null;
        description: string | null;
        section: string;
        module: string;
        indexing?: {
          kind: 'bounded' | 'unbounded';
          index_name: string;
          start?: number;
          end?: number;
          keyword_pattern: string;
        };
      }>;
      results?: Array<{
        module: string;
        section: string;
        name: string;
        key: string; // unique per param, e.g. `${module}::${section}::${name}`
        type: string | null;
        default: string | number | null;
        enum: string[] | null;
        description: string | null;
        indexing?: {
          kind: 'bounded' | 'unbounded';
          index_name: string;
          start?: number;
          end?: number;
          keyword_pattern: string;
        };
      }>;
      metadata_path_abs?: string | null;
      schema_version?: number | null;
    };
  };
  reload_qe_parameter_metadata: {
    payload: Record<string, never>;
    result: {
      modules: Array<{
        id: string;
        label: string;
        doc_url?: string;
      }>;
      metadata_path_abs?: string | null;
      schema_version?: number | null;
    };
  };
  get_qe_parameter_metadata_debug_info: {
    payload: Record<string, never>;
    result: {
      loaded_via: 'cache' | 'disk' | 'not_loaded';
      loaded_at: string | null;
      schema_version: number | null;
      path_abs: string | null;
    };
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
  list_calculations: {
    payload: { project_root: string };
    result: { calculations: CalculationInfo[]; count: number };
  };
  rebuild_project_registry: {
    payload: { project_root: string };
    result: {
      project_root: string;
      index_stats: {
        structures: number;
        calculations: number;
        steps: number;
      };
      dag_diff: {
        structures_added: Array<{ id: string; slug: string; name: string; suffix: string }>;
        structures_removed: Array<{ id: string; slug: string; name: string; suffix: string }>;
        calculations_added: Array<{ id: string; slug: string; name: string; suffix: string }>;
        calculations_removed: Array<{ id: string; slug: string; name: string; suffix: string }>;
        calculations_changed: Array<{
          calculation_id: string;
          calculation_slug: string;
          calculation_name: string;
          suffix: string;
          steps_added: Array<{ id: string; suffix: string }>;
          steps_removed: Array<{ id: string; suffix: string }>;
        }>;
      };
    };
  };
  
  // Analysis - ensure artifacts exist
  ensure_calculation_analysis: {
    payload: {
      project_root: string;
      calculation: string;
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
      display_mode?: 'primitive' | 'supercell' | 'conventional' | 'box';
      box_bounds?: [number, number, number, number, number, number]; // [xmin, xmax, ymin, ymax, zmin, zmax]
      trace_id?: string;
    };
    result: StructureVisData;
  };
  get_scf_convergence: {
    payload: {
      project_root: string;
      calculation: string;
      step: string;
    };
    result: ScfConvergenceData;
  };
  get_dos_data: {
    payload: {
      project_root: string;
      calculation: string;
      step?: string;
    };
    result: DosData;
  };
  get_band_structure_data: {
    payload: {
      project_root: string;
      calculation: string;
      step?: string;
    };
    result: BandStructureData;
  };
  
  get_reference_analysis: {
    payload: {
      project_root: string;
      calculation: string;
      analysis_type: 'scf' | 'dos' | 'bands';
    };
    result: {
      data: ScfConvergenceData | DosData | BandStructureData | null;
      has_reference: boolean;
    };
  };
  
  list_step_artifacts: {
    payload: {
      project_root: string;
      calculation: string;
      step: string;
    };
    result: {
      raw_dir: string;
      artifacts: Array<{
        path_relative_to_raw: string;
        kind: string;
        size_bytes: number;
        mtime: number;
        is_default_candidate: boolean;
      }>;
    };
  };
  
  read_step_artifact_text: {
    payload: {
      project_root: string;
      calculation: string;
      step: string;
      artifact_path: string;
      head_lines?: number;
      tail_lines?: number;
    };
    result: {
      content: string;
      truncated: boolean;
      total_bytes: number;
      resolved_path: string;
    };
  };
  
  // Job management
  run_calculation: {
    payload: {
      project_root: string;
      calculation: string;
      strict?: boolean;
      verbose?: boolean;
      run_mode?: 'incremental' | 'full'; // Default: 'incremental'
    };
    result: JobSubmitResult;
  };
  run_single_step: {
    payload: {
      project_root: string;
      calculation: string;
      step_ulid: string;
      verbose?: boolean;
    };
    result: JobSubmitResult;
  };
  run_step: {
    payload: {
      project_root: string;
      calculation: string;
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
  // Online structure operations
  structure_get_online_candidate: {
    payload: {
      project_root: string;
      session_id: string;
      candidate_id: string;
      supercell?: [number, number, number];
      repeat_boundary?: boolean;
      display_mode?: 'primitive' | 'supercell' | 'conventional' | 'box';
      box_bounds?: [number, number, number, number, number, number];
      trace_id?: string;
    };
    result: {
      structure_vis: StructureVisData;
      formula: string;
      provenance?: {
        provider?: string;
        database?: string;
        entry_id?: string;
        url?: string;
        cod_id?: string;
      };
    };
  };
  structure_import_online_candidate: {
    payload: {
      project_root: string;
      session_id: string;
      candidate_id: string;
    };
    result: {
      new_structure_id: string;
      name: string;
    };
  };
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
      using_calculations: string[];
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
  
  // Calculation templates
  list_calculation_templates: {
    payload: Record<string, never>;
    result: {
      templates: CalculationTemplateInfo[];
      count: number;
    };
  };
  
  create_calculation: {
    payload: {
      project_root: string;
      name: string;
      structure?: string;
      template?: string;
    };
    result: {
      calculation_id: string;
      name: string;
      slug: string;
      n_steps: number;
    };
  };
  
  // Calculation management
  rename_calculation: {
    payload: {
      project_root: string;
      calculation_ulid?: string;  // Preferred: ULID
      selector?: string;  // Legacy: selector (for backwards compat)
      new_name: string;
    };
    result: {
      success: boolean;
      old_name: string;
      new_name: string;
      new_slug: string;
    };
  };
  can_delete_calculation: {
    payload: {
      project_root: string;
      selector: string;
    };
    result: {
      calculation_name: string;
      dependent_calculations: string[];
      has_dependencies: boolean;
    };
  };
  delete_calculation: {
    payload: {
      project_root: string;
      calculation_ulid?: string;  // Preferred: ULID
      selector?: string;  // Legacy: selector (for backwards compat)
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
      calculation: string;
      step: string;
    };
    result: StepDetail;
  };
  get_common_cards: {
    payload: {
      project_root: string;
      calculation: string;
      step: string;
    };
    result: {
      k_points?: {
        raw: string;
        mode: string;
        automatic?: {
          nk1: number;
          nk2: number;
          nk3: number;
          sk1: number;
          sk2: number;
          sk3: number;
        };
        points?: Array<{
          x: number;
          y: number;
          z: number;
          w: number;
        }>;
        parse_ok?: boolean;
        canonical_raw?: string;
        warnings?: string[];
        errors?: string[];
        summary?: string;
      };
    };
  };
  set_common_card: {
    payload: {
      project_root: string;
      calculation: string;
      step: string;
      card_name: string;
      view_model: {
        raw?: string;
        mode: string;
        automatic?: {
          nk1: number;
          nk2: number;
          nk3: number;
          sk1: number;
          sk2: number;
          sk3: number;
        };
        points?: Array<{
          x: number;
          y: number;
          z: number;
          w: number;
        }>;
        warnings?: string[];
      };
    };
    result: StepDetail;
  };
  get_pseudo_mapping: {
    payload: {
      project_root: string;
      calculation: string;
      step: string;
    };
    result: {
      species: string[];
      mapping: Record<string, string>;
      pseudo_dir: string;
      available_pseudos: string[];
      warnings: string[];
      library_preference?: 'precision' | 'efficiency';
      sssp_defaults?: Record<string, { precision: string; efficiency: string }>;
      sssp_installed?: { precision: boolean; efficiency: boolean };
    };
  };
  set_pseudo_mapping: {
    payload: {
      project_root: string;
      calculation: string;
      step: string;
      mapping: Record<string, string>;
      library_preference?: 'precision' | 'efficiency';
    };
    result: StepDetail;
  };
  import_pseudo_files: {
    payload: {
      project_root: string;
      file_paths: string[];
    };
    result: {
      imported: string[];
      renamed: Record<string, string>;
      skipped: string[];
      errors: string[];
    };
  };
  search_legacy_pseudos: {
    payload: {
      element: string;
      project_root?: string;
    };
    result: {
      candidates: Array<{
        filename: string;
        url: string;
        element: string;
        xc?: string | null;
      }>;
      errors: string[];
    };
  };
  download_pseudo_by_filename: {
    payload: {
      project_root: string;
      filename: string;
      dest_dir?: string;
    };
    result: {
      filename: string;
      renamed: boolean;
      skipped: boolean;
      errors: string[];
    };
  };
  download_pseudo_candidate: {
    payload: {
      project_root: string;
      candidate: {
        filename?: string;
        url?: string;
      };
      dest_dir?: string;
    };
    result: {
      filename: string;
      renamed: boolean;
      skipped: boolean;
      errors: string[];
    };
  };
  get_relax_final_structure_preview: {
    payload: {
      project_root: string;
      calculation: string;
      step: string;
    };
    result: {
      cell: number[][];  // 3x3 matrix in Angstrom
      species: string[];
      positions: number[][];  // Nx3 in Angstrom (Cartesian)
      volume: number;  // Angstrom^3
      n_atoms: number;
    };
  };
  save_relax_final_structure: {
    payload: {
      project_root: string;
      calculation: string;
      step: string;
      parent_structure_ulid: string;
      slug_hint?: string;
    };
    result: {
      structure_ulid: string;
      already_exists: boolean;
    };
  };
  update_step_params: {
    payload: {
      project_root: string;
      calculation: string;
      step: string;
      parameters: Record<string, Record<string, unknown>>;
      cards?: Record<string, Record<string, unknown>>;
      parameter_scan?: Record<string, { values: unknown[] }>;
    };
    result: StepDetail;
  };
  reset_step_params: {
    payload: {
      project_root: string;
      calculation: string;
      step: string;
    };
    result: StepDetail;
  };
  import_step_from_qe_input: {
    payload: {
      project_root: string;
      calculation: string;
      input_file: string;
      step_name?: string;
    };
    result: CalculationDetailResult;
  };
  add_step_to_calculation: {
    payload: {
      project_root: string;
      calculation: string;
      step_type: string;
      step_name?: string;
    };
    result: CalculationDetailResult;
  };
  
  // Calculation configuration
  get_calculation_detail: {
    payload: {
      project_root: string;
      calculation: string;
    };
    result: CalculationDetailResult;
  };
  reorder_calculation_steps: {
    payload: {
      project_root: string;
      calculation: string;
      new_order: string[];
    };
    result: CalculationDetailResult;
  };
  change_calculation_structure: {
    payload: {
      project_root: string;
      calculation: string;
      new_structure: string;
      update_steps?: boolean;
    };
    result: CalculationStructureChangeResult;
  };
  get_calculation_pseudo_mapping: {
    payload: {
      project_root: string;
      calculation: string;
    };
    result: CalculationPseudoMappingResult;
  };
  update_calculation_species_map: {
    payload: {
      project_root: string;
      calculation: string;
      species_map: Record<string, { pseudopot?: string; mass?: number }>;
    };
    result: CalculationDetailResult & { old_species_map?: Record<string, { pseudopot?: string; mass?: number }> };
  };
  get_pseudo_options_for_calculation: {
    payload: {
      project_root: string;
      calculation: string;
    };
    result: {
      options_by_element: Record<string, Array<{
        sha256: string;
        sha_family: string;
        element: string;
        display_basename: string;
        all_basenames: string[];
        sources: Array<{
          kind: 'project' | 'internal' | 'library';
          label: string;
          installed: boolean;
          corrupt?: boolean;
          warning?: string;
          archive_asset?: string;
        }>;
        availability: { any_installed: boolean };
      }>>;
    };
  };
  materialize_pseudo_file: {
    payload: {
      project_root: string;
      element: string;
      sha256: string;
      preferred_basename?: string;
    };
    result: {
      success: boolean;
      file_path?: string;
      source?: 'project' | 'internal' | 'library';
      error?: string;
      needs_install: boolean;
      archive_asset?: string;
    };
  };
  analyze_project_pseudo_effects: {
    payload: {
      project_root: string;
      selections: Array<{
        element: string;
        requested_basename: string;
        requested_sha256?: string;
        requested_sha_family?: string;
        source_kind?: 'project' | 'internal' | 'lib';
        source_path?: string;
      }>;
    };
    result: {
      actions: Array<{
        action: 'noop' | 'copy' | 'overwrite' | 'rename_existing' | 'error';
        element: string;
        detail: string;
        source_path?: string | null;
        dest_path?: string | null;
        renamed_from?: string | null;
        renamed_to?: string | null;
      }>;
      warnings: string[];
      errors: string[];
    };
  };
  
  // Pre-flight checks
  preflight_check: {
    payload: {
      project_root: string;
      calculation?: string;
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
  
  // Online structure search
  structure_search_online: {
    payload: {
      project_root: string;
      query: string;
      max_results?: number;
    };
    result: {
      session_id: string;
      candidates: Array<{
        candidate_id: string;
        label: string;
        source: string;
        source_id: string;
        nsites: number;
        spacegroup?: string | null;
        flags: string[];
        score: number;
      }>;
    };
  };
  
  // Set daemon log level
  set_log_level: {
    payload: {
      level: 'INFO' | 'DEBUG';
    };
    result: {
      ok: boolean;
      level: 'INFO' | 'DEBUG';
    };
  };
  // Set resolution debug flag
  set_debug_resolution: {
    payload: {
      enabled: boolean;
    };
    result: {
      ok: boolean;
      enabled: boolean;
    };
  };
  // Get resolution debug flag
  get_debug_resolution: {
    payload: Record<string, never>;
    result: {
      ok: boolean;
      enabled: boolean;
    };
  };
  
  // Get preset catalog (UI's single source of truth)
  get_preset_catalog: {
    payload: Record<string, never>;
    result: {
      dimensions: Array<{
        dimension: string;
        label: string;
        description: string;
        order: number;
        options: Array<{ value: string; label: string }>;
        default: string;
        scope: {
          type: 'variant_step_types' | 'variants';
          step_types?: string[];
          variants?: Array<{
            name: string;
            step_types: string[];
            notes: string;
          }>;
        };
      }>;
      schema_version: number;
    };
  };
  
  // Preset detection (Constitution §10.4.1: Detector B is sole state source)
  detect_presets: {
    payload: {
      project_root: string;
      calculation: string;
    };
    result: PresetDetectionResult;
  };
  
  // Workflow detection (runtime-only, informational)
  detect_workflow: {
    payload: {
      project_root: string;
      calculation: string;
    };
    result: WorkflowDetectionResult;
  };
  detect_workflow_for_calculation: {
    payload: {
      project_root: string;
      calculation_ulid: string;
    };
    result: DetectWorkflowForCalculationResult;
  };
  list_workflow_templates: {
    payload: Record<string, never>;
    result: ListWorkflowTemplatesResult;
  };
  instantiate_workflow: {
    payload: {
      workflow_id: string;
      calculation_path: string;
      structure_id: string;
      calculation_id: string;
    };
    result: InstantiateWorkflowResult;
  };
  
  // Apply presets to step (Constitution §10.3.3: overwrite, not merge)
  apply_presets_to_step: {
    payload: {
      project_root: string;
      calculation: string;
      step: string;
      presets: {
        spin?: SpinValue;
        soc?: SOCValue;
        occupations_scheme?: OccupationsSchemeValue;
        precision?: PrecisionValue;
      };
      validate_physics?: boolean;
    };
    result: ApplyPresetsResult;
  };
  
  // Apply presets to all steps (BROADCAST)
  apply_presets_to_calculation: {
    payload: {
      project_root: string;
      calculation: string;
      presets: Record<string, string>;  // dimension -> option_value
      validate_physics?: boolean;
    };
    result: ApplyPresetsToCalcResult;
  };
  
  // Get preset footprints for all steps
  get_step_preset_footprints: {
    payload: {
      project_root: string;
      calculation: string;
    };
    result: StepFootprintsResult;
  };
  
  // History RPC commands
  get_project_history: {
    payload: {
      project_root: string;
      limit?: number;
      calc_id?: string;
    };
    result: {
      timeline: HistoryTimelineEntry[];
      latest_run_id: string | null;
      total: number;
    };
  };
  
  get_latest_run_for_step: {
    payload: {
      project_root: string;
      step_id: string;
    };
    result: {
      run_id: string | null;
      can_pin: boolean;
      reason: string | null;
    };
  };
  
  can_pin_to_run: {
    payload: {
      project_root: string;
      run_id: string;
      step_id: string;
    };
    result: {
      allowed: boolean;
      reason: string | null;
    };
  };
  
  pin_analysis_to_history: {
    payload: {
      project_root: string;
      run_id: string;
      step_id: string;
      analysis_kind: string;
      png_data_base64?: string;
      json_payload?: Record<string, unknown>;
    };
    result: {
      success: boolean;
      pin_path?: string;
      error?: string;
    };
  };
  
  delete_project_history: {
    payload: {
      project_root: string;
      confirm: boolean;
    };
    result: {
      success: boolean;
      error?: string;
      deleted_path?: string;
      message?: string;
    };
  };
}

// =============================================================================
// Extended Result Types
// =============================================================================

export interface CalculationDetailResult {
  id: string;
  name: string;
  slug: string;
  path: string;
  absolute_path: string;
  structure: string | null;
  structure_id: string | null;
  structure_elements: string[];  // Element symbols from structure composition
  mode: string;
  n_steps: number;
  steps: Array<{
    id: string;
    slug: string;
    type: string;
    step_file: string;
  }>;
  // Calculation-level pseudo mapping (authoritative source)
  species_map: Record<string, { pseudopot?: string; mass?: number }> | null;
}

// Calculation-level pseudo mapping result
export interface CalculationPseudoMappingResult {
  species: string[];
  mapping: Record<string, string>;
  species_map: Record<string, { pseudopot?: string; mass?: number }> | null;
  available_pseudos: string[];
  pseudo_dir: string;
  warnings: string[];
  sssp_defaults?: Record<string, { precision: string; efficiency: string }>;
  sssp_installed?: { precision: boolean; efficiency: boolean };
  installed_sources?: {
    internal: boolean;
    sssp_precision: boolean;
    sssp_efficiency: boolean;
  };
  candidates_by_element?: Record<string, Array<{
    filename: string;
    source: 'internal' | 'sssp_precision' | 'sssp_efficiency' | 'project';
    path?: string | null;
  }>>;
  resolved_by_element?: Record<string, {
    filename: string;
    source: 'internal' | 'sssp_precision' | 'sssp_efficiency' | 'project' | null;
    resolved: boolean;
    in_project?: boolean;
  }>;
}

export interface CalculationStructureChangeResult extends CalculationDetailResult {
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

// History types (for get_project_history)
export interface HistoryTimelineEntry {
  id: string;
  timestamp: string;
  event_type: string;
  calc_id?: string;
  step_id?: string;
  run_id?: string;
  step_ids?: string[];
  step_types?: string[];
  calc_name?: string;
  status?: string;
  duration_seconds?: number;
  step_count?: number;
  success_count?: number;
  failure_count?: number;
  error_summary?: string;
  run_digest?: {
    total_energy_ry?: number;
    fermi_energy_ev?: number;
    converged?: boolean;
  };
  step_digests?: Array<{
    step_id: string;
    step_type: string;
    status: string;
    total_energy?: { value: number | null; status: string };
    fermi_energy?: { value: number | null; status: string };
  }>;
  doc_type?: string;
  doc_path?: string;
  summary?: string;
  actor?: string;
  analysis_kind?: string;
  pin_path?: string;
  structure_ids?: string[];
  calculation_ids?: string[];
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
  calculation: {
    calculation_id: string;
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

// =============================================================================
// Pseudo Selection Types (sha256-keyed, filename-first, constitution-compliant)
// =============================================================================

export interface PseudoVariant {
  sha256: string;  // Primary selection key
  sha_family: string;  // For warnings/collision detection only
  basename: string;
  element: string;
  sources: PseudoSource[];
  size_bytes?: number | null;
  upf_format?: string | null;
  is_project_local_unknown?: boolean;  // True if project has basename but sha256 not in index
  family_match_warnings?: string[];  // Warnings about family matches with different sha256
  display_label: string;  // Computed label (e.g., "Si: Si.upf" or "Si: Si.upf (project-local)")
  availability: {
    any_installed: boolean;
  };
}

export interface PseudoSource {
  kind: "project" | "internal" | "lib";
  label: string;
  installed: boolean;  // lib-only meaningful (project/internal always installed if file exists)
  corrupt?: boolean;
  warning?: string | null;
  
  // lib metadata when kind==="lib"
  library_name?: string | null;
  library_version?: string | null;
  archive_asset?: string | null;
  archive_sha256?: string | null;
  
  // optional: basename/path if backend provides
  basename?: string | null;
}

// Legacy PseudoOption (sha256-based) - kept for backward compatibility
export interface PseudoOption {
  sha256: string;
  sha_family: string;
  element: string;
  display_basename: string;
  all_basenames: string[];
  sources: Array<{
    kind: 'project' | 'internal' | 'library';
    label: string;
    installed: boolean;
    corrupt?: boolean;
    warning?: string;
    archive_asset?: string;
  }>;
  availability: { any_installed: boolean };
}

// =============================================================================
// Preset Types (Constitution Chapter 10 compliant)
// =============================================================================

/** Preset dimension values - corresponds to Python SpinOption, SOCOption, OccupationsSchemeOption, PrecisionOption */
export type SpinValue = 'nonspin' | 'collinear' | 'noncollinear';
export type SOCValue = 'no_soc' | 'with_soc';
export type OccupationsSchemeValue = 'fixed' | 'smearing_gaussian' | 'tetrahedra';
export type PrecisionValue = 'low' | 'med' | 'high';
export type PresetValue = SpinValue | SOCValue | OccupationsSchemeValue | PrecisionValue | 'Custom';

/** Detected workflow type */
export type WorkflowType = 'SCF' | 'DOS' | 'BandStructure' | 'Relaxation' | 'Phonon' | 'MD' | 'NSCF' | 'Unknown';

/** Preset detection result from daemon */
export interface PresetDetectionResult {
  dimension_states: Record<string, string | 'Custom'>;
}

/** Workflow detection result from daemon */
export interface WorkflowDetectionResult {
  workflow: WorkflowType;
}

/** Apply presets result from daemon (single step) */
export interface ApplyPresetsResult {
  status: 'applied' | 'error';
  presets: {
    spin: SpinValue | 'Custom';
    soc: SOCValue | 'Custom';
    occupations_scheme: OccupationsSchemeValue | 'Custom';
    precision: PrecisionValue | 'Custom';
  };
  error?: {
    code: string;
    message: string;
  };
}

/** Step apply result in BROADCAST apply */
export interface StepApplyResult {
  step_file: string;
  step_type: string;
  status: 'updated' | 'skipped' | 'error';
  applied_presets?: string[];  // List of dimension names applied (e.g., ['spin', 'soc'])
  reason?: string;  // For skipped/error: why it was skipped
  updated_fields?: string[];  // List of fields that were updated (e.g., ['ecutwfc', 'ecutrho', 'K_POINTS'])
  skipped_fields?: string[];  // List of fields that were skipped with reasons (e.g., ['K_POINTS: kpath preserved'])
}

/** Apply presets to calculation result (BROADCAST) */
export interface ApplyPresetsToCalcResult {
  status: 'applied';
  steps_updated: number;
  steps_skipped: number;
  step_results: StepApplyResult[];
  dimension_states: Record<string, string | 'Custom'>;
}

/** Step preset footprint for display */
export interface StepPresetFootprint {
  params: Record<string, unknown>;
  spin: SpinValue;
  soc: SOCValue;
  occupations_scheme: OccupationsSchemeValue;
}

/** Step footprints result from daemon */
export interface StepFootprintsResult {
  footprints: Record<string, StepPresetFootprint>;
}

/** Preset options for each dimension */
// DEPRECATED: These constants are no longer used.
// UI now uses preset catalog from backend (get_preset_catalog RPC).
// Keeping for backward compatibility only - will be removed in future version.
/** @deprecated Use preset catalog from backend instead */
export const SPIN_OPTIONS: SpinValue[] = ['nonspin', 'collinear', 'noncollinear'];
/** @deprecated Use preset catalog from backend instead */
export const SOC_OPTIONS: SOCValue[] = ['no_soc', 'with_soc'];
/** @deprecated Use preset catalog from backend instead */
export const OCCUPATIONS_SCHEME_OPTIONS: OccupationsSchemeValue[] = ['fixed', 'smearing_gaussian', 'tetrahedra'];
/** @deprecated Use preset catalog from backend instead */
export const PRECISION_OPTIONS: PrecisionValue[] = ['low', 'med', 'high'];

/** @deprecated Use preset catalog from backend instead */
export const PRESET_LABELS: Record<string, string> = {
  // Spin
  nonspin: 'Non-spin-polarized',
  collinear: 'Collinear spin',
  noncollinear: 'Non-collinear spin',
  // SOC
  no_soc: 'No SOC',
  with_soc: 'With SOC',
  // Occupations scheme
  fixed: 'Fixed',
  smearing_gaussian: 'Smearing (Gaussian 0.02 Ry)',
  tetrahedra: 'Tetrahedra',
  // Precision
  low: 'Low (fast screening)',
  med: 'Medium (production)',
  high: 'High (accurate)',
  // Custom
  Custom: 'Custom (mixed)',
};

// =============================================================================
// Journal Types
// =============================================================================

/** A single journal entry recording a YAML document change */
export interface JournalEntry {
  id: string;
  target_ulid: string;
  doc_type: 'step' | 'calc' | 'project' | 'unknown';
  timestamp: string;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
  summary: string;
  path: string | null;
}

/** Response from list_journal_entries */
export interface ListJournalEntriesResult {
  entries: JournalEntry[];
  total: number;
}

/** Response from get_journal_entry */
export interface GetJournalEntryResult {
  entry: JournalEntry | null;
}

// =============================================================================
// Workflow Types
// =============================================================================

/** A workflow template definition */
export interface WorkflowTemplate {
  id: string;
  name: string;
  description: string;
  step_sequence: string[];
}

/** Result of workflow detection */
export interface WorkflowMatch {
  workflow_id: string | null;
  workflow_name: string;
  coverage: number;
  present_steps: string[];
  missing_steps: string[];
  extra_steps: string[];
  ordering_valid: boolean;
}

/** Response from list_workflow_templates */
export interface ListWorkflowTemplatesResult {
  templates: WorkflowTemplate[];
}

/** Response from detect_workflow */
export interface DetectWorkflowResult {
  match: WorkflowMatch;
}

/** Response from instantiate_workflow */
export interface InstantiateWorkflowResult {
  step_paths: string[];
}

/** Workflow issue from validation */
export interface WorkflowIssue {
  code: 'error' | 'warning';
  message: string;
  step_type?: string;
}

/** Response from detect_workflow_for_calculation */
export interface DetectWorkflowForCalculationResult {
  workflow_id: string | null;
  workflow_name: string;
  workflow_label: string;  // Formatted label like "DOS (3/3)" or "Bands (2/3)"
  coverage: {
    present: number;
    required: number;
  };
  present_steps?: string[];  // Optional list of present step types
  missing_step_types: string[];
  issues: WorkflowIssue[];
}

// Extend Window interface
declare global {
  interface Window {
    qv: QVApi;
  }
}
