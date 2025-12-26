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
  parent_calculation_id: string | null;
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
  
  // Job management
  run_calculation: {
    payload: {
      project_root: string;
      calculation: string;
      strict?: boolean;
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
    };
  };
  set_pseudo_mapping: {
    payload: {
      project_root: string;
      calculation: string;
      step: string;
      mapping: Record<string, string>;
      pseudo_dir?: string;
    };
    result: StepDetail;
  };
  update_step_params: {
    payload: {
      project_root: string;
      calculation: string;
      step: string;
      parameters: Record<string, Record<string, unknown>>;
      cards?: Record<string, Record<string, unknown>>;
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
      success: boolean;
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
  mode: string;
  n_steps: number;
  steps: Array<{
    id: string;
    slug: string;
    type: string;
    step_file: string;
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

// Extend Window interface
declare global {
  interface Window {
    qv: QVApi;
  }
}
