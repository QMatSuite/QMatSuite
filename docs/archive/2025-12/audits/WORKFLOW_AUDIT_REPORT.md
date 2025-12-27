# Workflow 命名审计报告

## 1. 搜索方法说明

### 使用的搜索工具
- **主要工具**: `grep -i "workflow"` (通过 Cursor 的 grep 工具，大小写不敏感)
- **辅助工具**: `codebase_search` 用于语义搜索外部引用
- **文件搜索**: `glob_file_search` 用于查找特定模式的文件

### 搜索范围
- **包含**: 所有源代码（Python/TypeScript/JavaScript）、配置文件（YAML/JSON/TOML）、文档（Markdown）、测试文件、项目示例、demo 项目
- **排除**: 
  - `.git/` 目录（版本控制）
  - `node_modules/`（前端依赖）
  - `dist/`、`build/`（构建产物）
  - `.pytest_cache/`（测试缓存）
  - `.venv/`、`env/`（虚拟环境，如果存在）
  - `WORKFLOW_AUDIT_REPORT.md`（本审计报告本身，避免在重命名时误处理）

### 搜索结果统计
- **总命中行数**: 1941 行
- **包含 workflow 的文件数**: 269 个文件
- **确认**: 除了上述排除目录外，整个 repo 已被完整扫描

---

## 2. 外部 workflow 列表（不参与重命名）

### 2.1 GitHub Actions 相关

#### 文件路径和内容
1. **`.github/workflows/tests.yml`**
   - 文件本身：GitHub Actions workflow 配置文件
   - 判定理由：这是 GitHub Actions 的标准 workflow 文件，属于 CI/CD 外部概念
   - 原始大小写：`workflow`（在路径中）

2. **`docs/ci/legacy/tests.yml.before_qe_install_cache`** (第 246 行)
   - 出现：`if: github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'`
   - 原始 token：`workflow_dispatch`
   - 判定理由：GitHub Actions 的标准触发事件关键字

3. **`tests/docs/archive/REFACTORING_COMPLETE.md`** (第 110 行)
   - 出现：`- ⏸️ **手动触发**: 通过 workflow_dispatch`
   - 原始 token：`workflow_dispatch`
   - 判定理由：文档中描述 GitHub Actions 功能

#### 文档中提及 GitHub Actions workflow
4. **`docs/ARCHITECTURE_OVERVIEW.md`** (第 19 行)
   - 出现：`- '.github/workflows/' - CI/CD (GitHub Actions)`
   - 原始 token：`workflows`（路径部分）
   - 判定理由：明确指代 GitHub Actions

5. **`docs/ARCHITECTURE_OVERVIEW.md`** (第 102 行)
   - 出现：`- **File**: '.github/workflows/tests.yml'`
   - 原始 token：`workflows`（路径部分）
   - 判定理由：明确指代 GitHub Actions

6. **`README_TESTS.md`** (第 94 行)
   - 出现：`- ✅ After QE compilation completes (QE required for workflow tests)`
   - 原始 token：`workflow tests`
   - 判定理由：指代 GitHub Actions 中的 workflow 测试，但这里的 "workflow tests" 可能指 "workflow 的测试"，需要进一步判断
   - **注意**: 这个可能需要根据上下文判断，如果是指"workflow 的测试"则应该重命名

7. **`README_TESTS.md`** (第 98 行)
   - 出现：`- ⏸️ Manual workflow dispatch only`
   - 原始 token：`workflow dispatch`
   - 判定理由：明确指代 GitHub Actions 的 `workflow_dispatch` 功能

8. **`README_TESTS.md`** (第 102 行)
   - 出现：`See '.github/workflows/tests.yml' for details.`
   - 原始 token：`workflows`（路径部分）
   - 判定理由：明确指代 GitHub Actions

9. **`tests/SUMMARY.md`** (第 29 行)
   - 出现：`✅ '.github/workflows/tests.yml'`
   - 原始 token：`workflows`（路径部分）
   - 判定理由：明确指代 GitHub Actions

10. **`tests/SUMMARY.md`** (第 64 行)
    - 出现：`└── .github/workflows/     # CI 配置`
    - 原始 token：`workflows`（路径部分）
    - 判定理由：明确指代 GitHub Actions

11. **`tests/docs/archive/REFACTORING_COMPLETE.md`** (第 27 行)
    - 出现：`- ✅ '.github/workflows/tests.yml'`
    - 原始 token：`workflows`（路径部分）
    - 判定理由：明确指代 GitHub Actions

12. **`tests/docs/archive/REFACTORING_COMPLETE.md`** (第 63 行)
    - 出现：`└── .github/workflows/     # CI 配置`
    - 原始 token：`workflows`（路径部分）
    - 判定理由：明确指代 GitHub Actions

13. **`docs/tests_overview.md`** (第 224 行)
    - 出现：`**GitHub Actions** ('.github/workflows/tests.yml'):`
    - 原始 token：`workflows`（路径部分）
    - 判定理由：明确指代 GitHub Actions

14. **`AI_understanding.md`** (第 3272 行)
    - 出现：`The GitHub Actions workflow ('.github/workflows/tests.yml') runs E2E tests...`
    - 原始 token：`workflow`（描述 GitHub Actions）
    - 判定理由：明确指代 GitHub Actions workflow

15. **`temporary_ai_prompts`** (多处)
    - 出现：多处提及 `.github/workflows/tests.yml`
    - 原始 token：`workflows`（路径部分）
    - 判定理由：明确指代 GitHub Actions

### 2.2 URL / 外部链接中的 workflow

16. **`gui/package-lock.json`** (多处)
    - 出现：大量 `https://github.com/...` URL
    - 原始 token：`github.com`（URL 中的域名）
    - 判定理由：外部 URL，不涉及领域模型

17. **`development_notes`** (第 2, 81 行)
    - 出现：`https://raw.githubusercontent.com/...`
    - 原始 token：`githubusercontent.com`（URL 中的域名）
    - 判定理由：外部 URL

18. **`src/quantumvitas/data/qe_module_parameters*.json`** (多处)
    - 出现：`https://github.com/aoterodelaroza/postg/blob/master/xdm.param`
    - 原始 token：`github.com`（URL 中的域名）
    - 判定理由：外部 URL 引用

### 2.3 描述性文本中的 workflow（应重命名）

19. **`pyproject.toml`** (第 8 行)
   - 出现：`description = "Python rewrite of QuantumVITAS - a workflow engine and GUI layer..."`
   - 原始 token：`workflow engine`
   - 判定理由：**应重命名** - 这是对本项目的定义，描述 QuantumVITAS 本身的功能
   - **建议**: 改为 "calculation engine"

20. **`README.md`** (第 2 行)
   - 出现：`> I am working on a full Python rewrite (v2) with a modern workflow engine,`
   - 原始 token：`workflow engine`
   - 判定理由：**应重命名** - 同上，描述 QuantumVITAS 本身
   - **建议**: 改为 "calculation engine"

### 2.4 外部 workflow 统计
- **GitHub Actions 相关**: 15 处
- **URL/外部链接**: 3 处（不计入 package-lock.json 中的大量 URL）

**总计**: 约 18 处外部 workflow 引用（不包括 package-lock.json 中的大量第三方库 URL）

**注意**: `pyproject.toml` 和 `README.md` 中的 "workflow engine" 是对本项目的定义，应归类为内部 workflow，需要重命名为 "calculation engine"

---

## 3. 内部 workflow 用法分类汇总（应该重命名）

### 3.1 模型 / 数据结构层

#### 类 / 类型定义

**Python 类**:
1. **`src/quantumvitas/workflow/workflow.py`**
   - `class Workflow` (第 23 行)
   - 原始大小写：`Workflow` (PascalCase)

2. **`src/quantumvitas/workflow/runner.py`**
   - `class WorkflowRunner` (第 54 行)
   - 原始大小写：`WorkflowRunner` (PascalCase)

3. **`src/quantumvitas/workflow/results.py`**
   - `class WorkflowResult` (需确认)
   - `class WorkflowImportResult` (需确认)
   - 原始大小写：`Workflow*` (PascalCase)

4. **`src/quantumvitas/core/models.py`**
   - `class WorkflowStepEntry` (第 36 行)
   - `class WorkflowModel` (需确认)
   - 原始大小写：`Workflow*` (PascalCase)

5. **`src/quantumvitas/project/model.py`**
   - `class WorkflowRef` (第 73 行)
   - 原始大小写：`WorkflowRef` (PascalCase)

6. **`src/quantumvitas/workflow/io.py`**
   - `class WorkflowIO` (需确认)
   - 原始大小写：`WorkflowIO` (PascalCase)

7. **`src/quantumvitas/workflow/naming.py`**
   - `class WorkflowFileNaming` (需确认)
   - 原始大小写：`WorkflowFileNaming` (PascalCase)

**TypeScript/React 类型**:
8. **`gui/src/types/qv.ts`**
   - `interface WorkflowInfo` (需确认)
   - `interface WorkflowDetailResult` (需确认)
   - 原始大小写：`Workflow*` (PascalCase)

#### 字段 / 属性名

**Python 变量/字段**:
- `workflow_id` (全小写，下划线分隔) - 出现在大量文件中
- `workflow_slug` (全小写，下划线分隔)
- `workflow_dir` (全小写，下划线分隔)
- `workflow_selector` (全小写，下划线分隔)
- `workflow_name` (全小写，下划线分隔)
- `workflow_path` (全小写，下划线分隔)
- `workflows` (复数，全小写) - 列表/字典变量
- `workflow` (单数，全小写) - 单个对象变量
- `workflow_meta` (全小写，下划线分隔)
- `workflow_yaml` (全小写，下划线分隔)
- `workflow_data` (全小写，下划线分隔)
- `workflow_entry` (全小写，下划线分隔)
- `workflow_steps` (全小写，下划线分隔)
- `workflowSlug` (camelCase) - 前端使用

**TypeScript/React 变量**:
- `workflows` (复数，全小写)
- `workflow` (单数，全小写)
- `workflowSlug` (camelCase)
- `workflowId` (camelCase)
- `selectedWorkflow` (camelCase)
- `selectedWorkflowSummary` (camelCase)
- `selectedWorkflowDetail` (camelCase)
- `isLoadingWorkflows` (camelCase)
- `showCreateWorkflow` (camelCase)
- `renameWorkflow` (camelCase)
- `deleteWorkflow` (camelCase)

### 3.2 存储 / Schema / 项目结构

#### 文件 / 目录命名

**目录**:
- `workflows/` (复数，全小写) - 项目根目录下的 workflows 目录
  - 出现在：`project.qv.yml` 配置、代码中的路径构建
  - 示例路径：`workflows/si-dos/`, `workflows/si-bands/`

**文件**:
- `workflow.yaml` (单数，全小写) - 每个 workflow 目录下的配置文件
- `workflow.py` (单数，全小写) - `src/quantumvitas/workflow/workflow.py`
- `workflow_*.py` (前缀，全小写) - 如 `workflow_analysis.py`

#### YAML / JSON Schema 字段

**project.qv.yml**:
- `workflows:` (复数，全小写) - 顶级键
- `workflow_id:` (全小写，下划线) - workflow 条目中的字段
- `workflows_dir:` (全小写，下划线) - 配置中的目录名

**workflow.yaml**:
- `workflow:` (单数，全小写) - 顶级键（包含 workflow 元数据）
- `kind: "workflow"` (全小写，字符串值)

**API 响应 JSON**:
- `"kind": "workflow"` (全小写，字符串值)
- `"workflow_id"` (全小写，下划线)
- `"workflow_slug"` (全小写，下划线)
- `"workflows"` (复数，全小写) - 数组键名

### 3.3 CLI / API / 命令行接口

#### CLI 命令字符串

**Typer 命令**:
- `qv init workflow <id>` (全小写)
- `qv run workflow <selector>` (全小写)
- `qv list-workflows` (kebab-case，复数)
- `qv delete workflow <selector>` (全小写)
- `qv rename workflow <selector>` (全小写)
- `qv configure workflow <selector>` (全小写)

**CLI 选项/参数**:
- `--workflow` (全小写，kebab-case) - 选项名
- `workflow:` (全小写) - 函数参数名

#### HTTP/IPC 接口

**Daemon API 方法名** (在 `src/quantumvitas/daemon/server.py`):
- `list_workflows` (全小写，下划线，复数)
- `get_workflow_detail` (全小写，下划线)
- `create_workflow` (全小写，下划线)
- `rename_workflow` (全小写，下划线)
- `delete_workflow` (全小写，下划线)
- `can_delete_workflow` (全小写，下划线)
- `reorder_workflow_steps` (全小写，下划线)
- `add_step_to_workflow` (全小写，下划线)
- `change_workflow_structure` (全小写，下划线)
- `ensure_workflow_analysis` (全小写，下划线)
- `run_workflow` (全小写，下划线)
- `list_workflow_templates` (全小写，下划线)

**API 请求/响应字段**:
- `"workflow"` (全小写) - 请求 payload 中的字段
- `"workflow_id"` (全小写，下划线)
- `"workflow_slug"` (全小写，下划线)
- `"workflows"` (复数，全小写) - 响应中的数组键

**Job 类型字符串**:
- `"run_workflow"` (全小写，下划线) - job_type 值

### 3.4 前端 / GUI

#### React/TSX 组件

**组件名**:
- `WorkflowListPanel` (PascalCase)
- `WorkflowDetailPanel` (PascalCase)
- `CreateWorkflowDialog` (PascalCase)

**文件路径**:
- `gui/src/components/panels/WorkflowListPanel.tsx`
- `gui/src/components/panels/WorkflowListPanel.css`
- `gui/src/components/panels/WorkflowDetailPanel.tsx` (推测)
- `gui/src/components/dialogs/CreateWorkflowDialog.tsx` (推测)

#### UI 文案 / 字符串

**用户可见文本**:
- `"Workflows"` (复数，首字母大写) - 面板标题
- `"New workflow"` (全小写)
- `"Run workflow"` (全小写)
- `"Workflow"` (单数，首字母大写) - 标签/标题
- `"Workflows panel"` (复数，首字母大写)
- `"This project uses a legacy workflow format"` (全小写)

**测试文件**:
- `gui/tests/e2e/demo_workflow.spec.ts`
- `gui/tests/e2e/demo_workflow_run.spec.ts`

### 3.5 文档 / README / 教程

#### 用户文档

**README.md**:
- `"with a modern workflow engine"` (第 2 行，项目描述 - **应重命名**为 "calculation engine")
- `"qv run workflow"` (CLI 命令示例)
- `"workflows/<id>/reference/"` (路径示例)
- `"workflow.yaml"` (文件名)
- `"workflow:"` (YAML 键)
- `"Each workflow owns an I/O directory"` (描述性文本)
- `"workflow execution"` (描述性文本)
- `"QE workflows"` (测试分类标题)

**docs/SCHEMA.md**:
- `"workflows:"` (YAML 键)
- `"workflow.yaml"` (文件名)
- `"workflow_id"` (字段名)
- `"WorkflowModel"` (类名)
- `"WorkflowEntry"` (类名)
- `"workflow-local metadata"` (描述性文本)
- `"Legacy workflow.yaml"` (描述性文本)

**docs/STRUCTURE_AND_CLI_USAGE.md**:
- 大量 workflow 相关描述

**docs/CLI_API_REFERENCE.md**:
- CLI 命令文档

**docs/DAEMON_API_REFERENCE.md**:
- API 方法文档

**docs/GUI_ARCHITECTURE.md**:
- GUI 组件文档

**docs/ARCHITECTURE.md**:
- 架构文档中的 workflow 概念

**docs/ARCHITECTURE_OVERVIEW.md**:
- 架构概览中的 workflow 概念

**docs/JOB_IO_DIRECTORY_SEMANTICS.md**:
- Job I/O 目录语义中的 workflow 引用

**docs/FRONTEND_RPC_PATTERNS.md**:
- 前端 RPC 模式中的 workflow 引用

**docs/GUI_DAEMON_API_MAPPING.md**:
- GUI-Daemon API 映射中的 workflow 引用

**docs/GUI_FIXES_DETAILED_EXPLANATION.md**:
- GUI 修复说明中的 workflow 引用

**docs/GUI_DEBUG_UX_REVIEW.md**:
- GUI 调试 UX 审查中的 workflow 引用

**docs/AI_CANONICAL_DOCS.md**:
- AI 规范文档中的 workflow 引用

**docs/testing_guide.md**:
- 测试指南中的 workflow 引用

**docs/tests_overview.md**:
- 测试概览中的 workflow 引用

**docs/STANDALONE_QE.md**:
- 独立 QE 文档中的 workflow 引用

**docs/SNAPSHOTS.md**:
- 快照文档中的 workflow 引用

**docs/QE_* 系列文档**:
- 各种 QE 相关文档中的 workflow 引用

### 3.6 测试 / Fixture

#### 测试文件命名

**测试文件**:
- `tests/cli/test_si_bands_workflow_cli.py`
- `tests/cli/test_si_dos_workflow_cli.py`
- `tests/cli/test_si_bands_auto_workflow_cli.py`
- `tests/cli/test_si_bands_manual_workflow_cli.py`
- `tests/cli/test_si_dos_workflow_comprehensive.py`
- `tests/cli/test_si_bands_workflow_comprehensive.py.backup`
- `tests/cli/test_template_workflow.py`
- `tests/cli/test_graphene_workflow_setup.py`
- `tests/daemon/test_gui_workflow_detail.py`
- `tests/daemon/test_si_bands_workflow_daemon.py`
- `tests/integration/test_si_dos_workflow.py`
- `tests/integration/test_si_bands_workflow.py`
- `tests/unit/test_workflow_importers.py`
- `tests/unit/test_workflow_dag_constitution.py`
- `tests/unit/test_workflow_inputs.py`
- `gui/tests/e2e/demo_workflow.spec.ts`
- `gui/tests/e2e/demo_workflow_run.spec.ts`

#### 测试函数/方法名

**Python 测试函数**:
- `test_*_workflow_*` (全小写，下划线)
- `test_workflow_*` (全小写，下划线)

#### 测试数据 / Fixture

**测试项目目录**:
- `tests/data/project_examples/project1/workflows/`
- `tests/data/project_examples/project2_bands/workflows/`
- `tests/data/project_examples/project2_bands_kauto/workflows/`
- `manual_tests/project1/workflows/`
- `manual_tests/project2_bands/workflows/`
- `manual_tests/project2_bands_kauto/workflows/`
- `manual_tests/project3_graphene_bands/workflows/`
- `debug_metadata_project/workflows/`
- `final_test/workflows/` (推测)
- `test_final/workflows/` (推测)

**测试工具函数**:
- `tests/utils/workflow_projects.py` - 工具模块

### 3.7 函数 / 方法名

#### Python 函数

**核心函数** (在 `src/quantumvitas/` 中):
- `load_workflow()` (全小写，下划线)
- `save_workflow()` (全小写，下划线)
- `require_workflow()` (全小写，下划线)
- `resolve_workflow()` (全小写，下划线)
- `find_workflow_entry()` (全小写，下划线)
- `find_enclosing_workflow()` (全小写，下划线)
- `workflow_directory()` (全小写，下划线)
- `workflow_identifiers()` (全小写，下划线)
- `workflows_using_structure()` (全小写，下划线)
- `workflows_depending_on()` (全小写，下划线)
- `apply_workflow_rename()` (全小写，下划线)
- `delete_workflow_entry()` (全小写，下划线)
- `ensure_workflow_entry_defaults()` (全小写，下划线)
- `extract_workflow_selector_from_entry()` (全小写，下划线)
- `get_workflow_selector_from_entry_or_raise()` (全小写，下划线)
- `list_workflow_templates()` (全小写，下划线)
- `copy_workflow_template()` (全小写，下划线)
- `build_workflow_from_qe_inputs()` (全小写，下划线)
- `compute_io_dir_from_workflow_model()` (全小写，下划线)

**前端函数** (在 `gui/src/` 中):
- `fetchWorkflows()` (camelCase)
- `handleSelectWorkflow()` (camelCase)
- `handleCreateWorkflowSuccess()` (camelCase)
- `handleRunWorkflow()` (camelCase)
- `handleViewAnalysisFromJob()` (包含 workflowSlug 参数)

### 3.8 导入 / 导出

#### Python import 语句

**模块导入**:
- `from quantumvitas.workflow import Workflow, WorkflowRunner, ...`
- `from quantumvitas.workflow.workflow import Workflow`
- `from quantumvitas.workflow.runner import WorkflowRunner`
- `from quantumvitas.workflow.results import WorkflowResult`
- `from quantumvitas.workflow.importers import WorkflowImportResult`
- `from quantumvitas.core.models import WorkflowModel, WorkflowStepEntry`
- `from quantumvitas.project.model import WorkflowRef`

**函数导入**:
- `from quantumvitas.core.resolution import require_workflow, resolve_workflow`
- `from quantumvitas.core.selectors import extract_workflow_selector_from_entry`
- `from quantumvitas.core.project_utils import workflow_directory, workflows_using_structure`

#### TypeScript import 语句

**类型导入**:
- `import { WorkflowInfo, WorkflowDetailResult } from './types/qv'`

**组件导入**:
- `import { WorkflowListPanel, WorkflowDetailPanel } from './components/panels'`
- `import { CreateWorkflowDialog } from './components/dialogs'`

### 3.9 错误消息 / 异常

**Python 异常消息**:
- `"Workflow not found"`
- `"Legacy workflow detected"`
- `"This project uses a legacy workflow format"`
- `"Workflow '{name}' already exists"`
- `"Cannot run workflow: {error}"`
- `"Registry is out of sync. Click 'Refresh' in the Workflows panel"`

**错误代码**:
- `kind='workflow'` (在 ResourceNotFoundError 等异常中)

### 3.10 注释 / 文档字符串

**Python docstring**:
- `"""Workflow representation (loaded from workflow.yaml)."""`
- `"""Workflow abstractions (steps, runner, verification, results)."""`
- `"""An entry in the workflow's step list."""`
- `"""Load workflow from workflow.yaml."""`
- `"""Create a new workflow."""`
- `"""Rename a workflow."""`
- `"""Delete a workflow."""`
- `"""Get detailed workflow information."""`
- 等等...

**代码注释**:
- `# Workflow Handling`
- `# Clear selected workflow and step when opening a new project`
- `# CRITICAL: Separate workflow summary (from list_workflows) from workflow detail`
- `# Refresh workflows list and summary`
- 等等...

---

## 4. 大小写变体统计

### 4.1 全小写 (workflow)

**出现位置**:
- 变量名：`workflow`, `workflows`, `workflow_id`, `workflow_dir`, `workflow_slug` 等
- 函数名：`load_workflow()`, `save_workflow()`, `run_workflow()` 等
- 文件/目录名：`workflow.yaml`, `workflow.py`, `workflows/`
- CLI 命令：`qv run workflow`, `qv init workflow`
- API 方法：`list_workflows`, `get_workflow_detail`
- YAML/JSON 键：`workflow:`, `workflows:`, `workflow_id:`
- 字符串值：`"workflow"`, `"run_workflow"`
- 文档中的描述性文本

**估计数量**: 约 1500+ 处

### 4.2 首字母大写 / PascalCase (Workflow)

**出现位置**:
- 类名：`Workflow`, `WorkflowRunner`, `WorkflowResult`, `WorkflowRef`, `WorkflowModel`, `WorkflowStepEntry`, `WorkflowIO`, `WorkflowFileNaming`, `WorkflowInfo`, `WorkflowDetailResult`, `WorkflowImportResult`
- 组件名：`WorkflowListPanel`, `WorkflowDetailPanel`, `CreateWorkflowDialog`
- 文档标题/标签：`"Workflows"`, `"Workflow"`

**估计数量**: 约 200+ 处

### 4.3 全大写 (WORKFLOW)

**出现位置**:
- 未发现明显的全大写 `WORKFLOW` 用法（除了可能的常量，但搜索未发现）

**估计数量**: 0 处（或极少）

### 4.4 camelCase (workflow)

**出现位置**:
- TypeScript/React 变量：`workflowSlug`, `workflowId`, `selectedWorkflow`, `fetchWorkflows`, `handleSelectWorkflow` 等

**估计数量**: 约 100+ 处

### 4.5 kebab-case (workflow)

**出现位置**:
- CLI 命令：`list-workflows`
- 文件路径中的目录名：`workflows/`（虽然这是复数）

**估计数量**: 约 50+ 处

---

## 5. 重命名策略建议

### 5.1 替换规则

对于所有**内部 workflow** 用法，按以下规则替换：

1. **全小写 `workflow`** → `calculation`
2. **PascalCase `Workflow`** → `Calculation`
3. **复数 `workflows`** → `calculations`
4. **复数 PascalCase `Workflows`** → `Calculations`
5. **camelCase `workflow`** → `calculation` (如 `workflowSlug` → `calculationSlug`)
6. **kebab-case `workflow`** → `calculation` (如 `list-workflows` → `list-calculations`)

### 5.2 后缀保持不变

- `workflow_id` → `calculation_id` (保留 `_id` 后缀)
- `workflow_slug` → `calculation_slug` (保留 `_slug` 后缀)
- `workflow_dir` → `calculation_dir` (保留 `_dir` 后缀)
- `WorkflowRunner` → `CalculationRunner` (保留 `Runner` 后缀)
- `WorkflowResult` → `CalculationResult` (保留 `Result` 后缀)
- `run_workflow` → `run_calculation` (保留 `run_` 前缀，但 workflow 部分替换)

### 5.3 特殊情况

1. **文件/目录路径**:
   - `workflows/` → `calculations/`
   - `workflow.yaml` → `calculation.yaml`
   - `workflow.py` → `calculation.py` (但模块名 `workflow/` → `calculation/`)

2. **CLI 命令**:
   - `qv init workflow` → `qv init calculation`
   - `qv run workflow` → `qv run calculation`
   - `qv list-workflows` → `qv list-calculations`

3. **API 方法**:
   - `list_workflows` → `list_calculations`
   - `get_workflow_detail` → `get_calculation_detail`
   - `run_workflow` → `run_calculation`

4. **YAML/JSON Schema**:
   - `workflows:` → `calculations:`
   - `workflow_id:` → `calculation_id:`
   - `kind: "workflow"` → `kind: "calculation"`

---

## 6. 需要进一步判断的边界情况

### 6.1 描述性文本

以下位置的 "workflow" 需要根据上下文判断：

1. **`pyproject.toml`** (第 8 行):
   - `"a workflow engine"` - 如果这是描述 QuantumVITAS 本身的功能，应该改为 "calculation engine"

2. **`README.md`** (第 2 行):
   - `"with a modern workflow engine"` - 同上

3. **测试文档中的 "workflow tests"**:
   - 如果指"workflow 的测试"，应该改为 "calculation tests"
   - 如果指"GitHub Actions workflow 的测试"，则保持不变

### 6.2 外部库引用

检查是否有外部 Python 包名为 `*workflow*` 的导入：
- 搜索结果显示没有发现外部 workflow 库的导入
- 所有 `from quantumvitas.workflow import ...` 都是内部模块

---

## 7. 总结

### 7.1 外部 workflow（不重命名）
- **GitHub Actions**: 约 15 处
- **URL/外部链接**: 约 3 处（不计 package-lock.json）

**总计**: 约 18 处

**注意**: `pyproject.toml` 和 `README.md` 中的 "workflow engine" 已归类为内部 workflow（见 3.5 节）

### 7.2 内部 workflow（需要重命名）
- **类/类型**: 约 15+ 个类
- **函数/方法**: 约 100+ 个函数
- **变量/字段**: 约 500+ 个变量
- **文件/目录**: 约 50+ 个文件/目录
- **CLI 命令**: 约 10+ 个命令
- **API 方法**: 约 15+ 个 API 方法
- **前端组件**: 约 10+ 个组件
- **文档**: 约 30+ 个文档文件（包括 `pyproject.toml` 和 `README.md` 中的 "workflow engine"）
- **测试**: 约 20+ 个测试文件

**总计**: 约 1941 行代码/文档中包含 workflow，其中约 1922+ 处需要重命名（包括 2 处 "workflow engine" 描述）

### 7.3 大小写分布
- **全小写 `workflow`**: 约 1500+ 处
- **PascalCase `Workflow`**: 约 200+ 处
- **camelCase `workflow`**: 约 100+ 处
- **kebab-case `workflow`**: 约 50+ 处
- **全大写 `WORKFLOW`**: 0 处

### 7.4 重命名优先级建议

1. **高优先级**（核心模型）:
   - 类名：`Workflow` → `Calculation`
   - 模块名：`workflow/` → `calculation/`
   - Schema 字段：`workflow_id`, `kind: "workflow"`

2. **中优先级**（API/CLI）:
   - CLI 命令：`qv run workflow` → `qv run calculation`
   - API 方法：`list_workflows` → `list_calculations`
   - 文件/目录：`workflows/`, `workflow.yaml`

3. **低优先级**（文档/注释）:
   - 文档中的描述性文本
   - 代码注释
   - 错误消息

---

## 8. 注意事项

1. **向后兼容性**: 重命名后需要考虑：
   - 旧项目文件（`workflow.yaml`, `workflows/` 目录）的迁移
   - API 版本兼容性
   - CLI 命令的别名支持（可选）

2. **测试覆盖**: 重命名后需要：
   - 更新所有测试文件
   - 更新测试数据（项目示例）
   - 验证 E2E 测试

3. **文档更新**: 需要更新：
   - 所有用户文档
   - API 文档
   - 架构文档
   - README
   - `pyproject.toml` 中的项目描述

4. **Git 历史**: 考虑使用 `git mv` 保留文件重命名的历史

5. **排除审计报告**: 重命名时**必须排除** `WORKFLOW_AUDIT_REPORT.md` 文件，否则会误处理本报告中的大量 workflow 引用

---

**报告生成时间**: 2025-01-27
**审计工具**: grep -i "workflow" (通过 Cursor IDE)
**扫描文件数**: 269 个文件
**总命中行数**: 1941 行

