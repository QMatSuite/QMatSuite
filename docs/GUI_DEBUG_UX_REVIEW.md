# GUI Frontend Debug/Diagnostics UX Review

## 0) 目标

快速理解界面/选项卡结构、state ownership、RPC调用模式、以及Debug/Diagnostics信息的展示位置和缺失，便于统一优化debug体验。

---

## 1) 界面总览（ViewType → Panel）

| ViewType | Panel组件 | 文件路径 | 职责 | 自动触发动作 | 关键UI布局 |
|----------|-----------|---------|------|-------------|-----------|
| `'home'` | `ProjectSummaryPanel` / `DemoGalleryPanel` | `gui/src/components/panels/ProjectSummaryPanel.tsx` (1-200) | 项目概览、快速操作、Demo展示 | mount时：`get_project_summary` (如果projectRoot存在) | 单列布局，卡片式项目信息 |
| `'structures'` | `StructureListPanel` + `StructureDetailPanel` + `StructureViewer3D` | `gui/src/components/panels/StructureListPanel.tsx` (1-271)<br>`gui/src/components/panels/StructureDetailPanel.tsx`<br>`gui/src/components/panels/StructureViewer3D.tsx` | 结构列表、详情、3D可视化 | `currentView === 'structures'` 时：`fetchStructures()` → `list_structures` | 左列表 + 右详情/3D（ResizablePane） |
| `'workflows'` | `WorkflowListPanel` + `WorkflowDetailPanel` + `StepDetailPanel` | `gui/src/components/panels/WorkflowListPanel.tsx` (1-893)<br>`gui/src/components/panels/WorkflowDetailPanel.tsx`<br>`gui/src/components/panels/StepDetailPanel.tsx` | 工作流列表、详情、步骤编辑 | `currentView === 'workflows'` 时：`fetchWorkflows()` → `list_workflows`<br>选择workflow时：`get_workflow_detail` | 左列表 + 右详情（可垂直分割显示步骤详情） |
| `'jobs'` | `JobsPanel` | `gui/src/components/panels/JobsPanel.tsx` (1-600) | 任务队列、详情、日志 | mount时：`useJobs({ autoStart: true, pollInterval: 5000 })` → `list_jobs` + `job_counts` (轮询)<br>选择job时：`useJobDetail({ jobId })` → `get_job_status` + `get_job_logs` (轮询) | 左列表 + 右详情（日志、io_dir、步骤进度） |
| `'analysis'` | `AnalysisPanel` | `gui/src/components/panels/AnalysisPanel.tsx` | SCF收敛、DOS、能带分析 | 手动触发：`load_scf_convergence` / `load_dos` / `load_bands` | 图表展示区域 |
| `'resources'` | `QEParameterBrowserPanel` | `gui/src/components/panels/QEParameterBrowserPanel.tsx` (1-1401) | QE参数元数据浏览、搜索 | mount时：`list_qe_parameter_metadata({ operation: 'list_modules' })`<br>选择module时：`list_sections`<br>选择section时：`list_parameters`<br>全局搜索：`search` (Enter/按钮触发) | 顶部filters row (Module/Section + Search) + 参数表格 + Popover搜索结果 |
| `'settings'` | `SettingsPanel` | `gui/src/components/panels/SettingsPanel.tsx` (1-578) | QE检测、环境信息、主题、诊断 | mount时：`get_env_info` + `detect_qe`<br>展开Diagnostics时：`get_qe_parameter_metadata_debug_info` | 单列滚动布局，Diagnostics折叠区域 |

**Sidebar定义**：`gui/src/components/layout/Sidebar.tsx` (18行) - `ViewType = 'home' | 'structures' | 'workflows' | 'jobs' | 'analysis' | 'resources' | 'settings'`

---

## 2) 全局/跨页面 State Ownership

### 2.1 路由状态（App Shell）

**定义位置**：`gui/src/App.tsx` (74行)
```typescript
const [currentView, setCurrentView] = useState<ViewType>('home');
```

**设置触发点**：
- Sidebar点击：`onViewChange(view)` → `setCurrentView(view)` (App.tsx 1295-1300行)
- 内部导航：`handleGoToJobs()` → `setCurrentView('jobs')` (App.tsx 1050行)

**依赖链**：
- `currentView` 改变 → 触发 `renderView()` switch (App.tsx 1080-1320行)
- 各Panel mount时触发各自的useEffect（见RPC Matrix）

---

### 2.2 选择状态（Selection States）

#### `selectedStructure`
- **定义**：`gui/src/App.tsx` (89行) - `useState<StructureInfo | null>(null)`
- **设置**：`handleSelectStructure()` (App.tsx 520行) → `setSelectedStructure(structure)`
- **依赖链**：
  - `selectedStructure` 改变 → `useEffect(() => loadStructureVis(...), [selectedStructure, ...])` (App.tsx 621-625行)
  - 触发：`get_structure_vis_data` (3D可视化数据)
- **清除**：打开新项目时清空 (App.tsx 228, 276, 403行)

#### `selectedWorkflowSummary` + `selectedWorkflowDetail`
- **定义**：`gui/src/App.tsx` (93-94行)
  - `selectedWorkflowSummary: WorkflowInfo | null`
  - `selectedWorkflowDetail: WorkflowDetailResult | null`
- **设置**：`handleSelectWorkflow()` (App.tsx 540行) → `setSelectedWorkflowSummary()` + `get_workflow_detail` → `setSelectedWorkflowDetail()`
- **依赖链**：
  - `selectedWorkflowSummary` 改变 → `handleSelectStep()` 可能触发 (App.tsx 823行)
  - `selectedWorkflowDetail` 改变 → `StepDetailPanel` 更新 (App.tsx 1241-1248行)
- **风险**：`selectedWorkflowDetail` 更新可能触发重复的 `get_workflow_detail`（已通过 `onWorkflowDetailUpdated` 回调优化，App.tsx 1229-1238行）

#### `selectedJobId`
- **定义**：`gui/src/components/panels/JobsPanel.tsx` (431行) - `useState<string | null>(null)`
- **设置**：
  - 自动选择：`useEffect(() => { if (!selectedJobId && jobs.length > 0) setSelectedJobId(mostRecent.id) }, [jobs, selectedJobId])` (JobsPanel.tsx 443-455行)
  - 手动选择：`onSelect(job)` → `setSelectedJobId(job.id)`
- **依赖链**：
  - `selectedJobId` 改变 → `useJobDetail({ jobId })` → `get_job_status` + `get_job_logs` (轮询，JobsPanel.tsx 455行)
- **风险**：自动选择可能覆盖用户选择（已用 `didAutoSelectRef` 防护，JobsPanel.tsx 436行）

#### QE Parameter Browser selections
- **定义**：`gui/src/components/panels/QEParameterBrowserPanel.tsx`
  - `selectedModule` (42行)
  - `selectedSection` (48行)
  - `selectedParamKey` (95行)
- **设置**：用户点击dropdown/表格行
- **依赖链**：
  - `selectedModule` 改变 → `handleModuleChange()` → `list_qe_parameter_metadata({ operation: 'list_sections', module })` (QEParameterBrowserPanel.tsx 269-290行)
  - `selectedSection` 改变 → `handleSectionChange()` → `list_qe_parameter_metadata({ operation: 'list_parameters', module, section })` (QEParameterBrowserPanel.tsx 321-345行)
- **风险**：**低** - 事件驱动，无自动触发

---

### 2.3 状态联动风险

**已识别的潜在重复RPC风险**：

1. **JobsPanel轮询**：
   - `useJobs` hook (JobsPanel.tsx 126行) 每5秒轮询 `list_jobs` + `job_counts`
   - `useJobDetail` hook (JobsPanel.tsx 455行) 每2秒轮询 `get_job_status` + `get_job_logs`
   - **状态**：正常，轮询是预期行为

2. **Workflow detail更新**：
   - `handleSelectWorkflow()` → `get_workflow_detail` (App.tsx 540行)
   - `onWorkflowUpdated()` → `get_workflow_detail` (App.tsx 1199-1228行)
   - **已优化**：`onWorkflowDetailUpdated` 直接更新state，避免重复fetch (App.tsx 1229-1238行)

3. **QE metadata reload**：
   - `reload_qe_parameter_metadata` → 清除后端cache → 前端需要重新fetch modules
   - **当前**：reload后手动触发 `handleLoadModules()` (QEParameterBrowserPanel.tsx 587-600行)
   - **建议**：reload响应可包含 `metadata_path_abs` + `schema_version`，自动更新 `metadataInfo` state

---

## 3) RPC/IPC 调用矩阵（按Panel）

### JobsPanel

| Command | 触发条件 | 频率 | 返回数据用途 | 缓存 |
|---------|---------|------|-------------|------|
| `list_jobs` | mount时 + 轮询 (5s) | 轮询 | 左侧job列表 | 无（每次fetch最新） |
| `job_counts` | mount时 + 轮询 (5s) | 轮询 | Sidebar badge计数 | 无 |
| `get_job_status` | `selectedJobId` 改变 + 轮询 (2s，仅pending/running) | 轮询 | 右侧详情（status, io_dir, steps, result） | 无 |
| `get_job_logs` | `selectedJobId` 改变 + 轮询 (2s) | 轮询 | 右侧日志区域 | 无 |
| `cancel_job` | 用户点击"Cancel"按钮 | 一次性 | 更新job status | 无 |

**文件位置**：`gui/src/hooks/useJobs.ts` (63-112行：fetchJobs), (189-208行：fetchJob), (210-225行：fetchLogs)

---

### QEParameterBrowserPanel

| Command | 触发条件 | 频率 | 返回数据用途 | 缓存 |
|---------|---------|------|-------------|------|
| `list_qe_parameter_metadata` (operation: 'list_modules') | mount时 (useEffect) | 一次性 | 顶部Module dropdown | 后端 `@lru_cache` (qe_metadata.py) |
| `list_qe_parameter_metadata` (operation: 'list_sections') | `selectedModule` 改变 (handleModuleChange) | 事件驱动 | Section dropdown | 后端cache |
| `list_qe_parameter_metadata` (operation: 'list_parameters') | `selectedSection` 改变 (handleSectionChange) | 事件驱动 | 参数表格 | 后端cache |
| `list_qe_parameter_metadata` (operation: 'search') | Enter键或搜索按钮点击 | 事件驱动 | Popover搜索结果 | 后端cache |
| `reload_qe_parameter_metadata` | 用户点击"Reload metadata"按钮 | 一次性 | 清除后端cache，触发重新load | 清除后端cache |

**文件位置**：`gui/src/components/panels/QEParameterBrowserPanel.tsx`
- mount时：194-210行
- module change：269-290行
- section change：321-345行
- search：548-570行
- reload：587-600行

**响应数据**：`list_qe_parameter_metadata` 返回 `metadata_path_abs` + `schema_version`，用于subtitle显示 (QEParameterBrowserPanel.tsx 58-64行, 210行)

---

### SettingsPanel

| Command | 触发条件 | 频率 | 返回数据用途 | 缓存 |
|---------|---------|------|-------------|------|
| `get_env_info` | mount时 | 一次性 | Python环境信息显示 | 无 |
| `detect_qe` | mount时 + 用户点击"Re-detect" | 事件驱动 | QE检测结果 | 无 |
| `get_qe_parameter_metadata_debug_info` | `showDiagnostics` 展开时 | 一次性 | Diagnostics区域显示 (loaded_via, loaded_at, schema_version, path_abs) | 后端 `QE_METADATA_LOAD_STATE` (qe_metadata.py 31-36行) |
| `ping` | 用户点击"Ping Daemon"按钮 | 事件驱动 | Diagnostics连接测试 | 无 |

**文件位置**：`gui/src/components/panels/SettingsPanel.tsx`
- env info：67-94行
- QE detect：103-121行
- debug info：52-64行, 97-101行
- ping：130-142行

---

### WorkflowListPanel / StructureListPanel

| Command | 触发条件 | 频率 | 返回数据用途 | 缓存 |
|---------|---------|------|-------------|------|
| `list_workflows` | `currentView === 'workflows'` 时 (fetchWorkflows) | 一次性 | 左侧workflow列表 | 无（App.tsx state） |
| `list_structures` | `currentView === 'structures'` 时 (fetchStructures) | 一次性 | 左侧structure列表 | 无（App.tsx state） |
| `get_workflow_detail` | `selectedWorkflowSummary` 改变 | 事件驱动 | 右侧workflow详情 | 无（App.tsx state） |
| `rebuild_project_registry` | 用户点击"Refresh"按钮 | 事件驱动 | 重建registry，然后刷新列表 | 后端ResourceIndex cache |

**文件位置**：`gui/src/App.tsx`
- fetchWorkflows：463-487行
- fetchStructures：437-461行
- get_workflow_detail：540-560行

---

## 4) Debug/Diagnostics 信息“在哪里、缺什么”

### 4.1 当前已展示的Debug信息

#### QE Metadata Load State
- **位置**：`gui/src/components/panels/SettingsPanel.tsx` (399-460行) - Diagnostics折叠区域
- **数据源**：`get_qe_parameter_metadata_debug_info` RPC
- **显示内容**：
  - `loaded_via`: "cache" | "disk" | "not_loaded"
  - `loaded_at`: ISO timestamp (转换为本地时间 HH:MM:SS)
  - `schema_version`: number
  - `path_abs`: 绝对路径（tooltip显示）
- **单一真相来源**：后端 `QE_METADATA_LOAD_STATE` (`src/quantumvitas/data/qe_metadata.py` 31-36行)

#### QE Parameter Browser Metadata Info
- **位置**：`gui/src/components/panels/QEParameterBrowserPanel.tsx` (58-64行, 210行, 600行) - subtitle row右侧
- **显示**：`<filename> · v<schema_version>` (tooltip显示绝对路径)
- **数据源**：`list_qe_parameter_metadata` / `reload_qe_parameter_metadata` 响应中的 `metadata_path_abs` + `schema_version`

#### Daemon Status
- **位置**：
  - Sidebar：`gui/src/components/layout/Sidebar.tsx` (93-102行) - 连接状态dot
  - SettingsPanel Diagnostics：`gui/src/components/panels/SettingsPanel.tsx` (399-460行) - Python path, project root
- **数据源**：`useDaemonStatus()` hook → `window.qv.getDaemonStatus()`

#### Daemon Logs
- **位置**：
  - DebugPanel（底部resizable panel）：`gui/src/components/panels/DebugPanel.tsx` (23-101行)
  - SettingsPanel Diagnostics：`gui/src/components/panels/SettingsPanel.tsx` (460-500行)
- **数据源**：`useQVLogs()` hook → `window.qv.onLog()` (stderr转发)

#### Job I/O Directory
- **位置**：`gui/src/components/panels/JobsPanel.tsx` (295-315行) - Job detail panel
- **显示**：`io_dir` 路径 + "Reveal in Finder"按钮
- **数据源**：`get_job_status` 响应中的 `io_dir` 字段
- **单一真相来源**：后端 `compute_io_dir_from_workflow_model()` (`src/quantumvitas/workflow/runner.py` 18-42行)

---

### 4.2 缺失的Debug信息（仅在console/log）

1. **RPC调用计数/频率**
   - **现状**：`useQVClient.ts` (148-155行) 有 `console.time/timeEnd` 日志
   - **缺失**：GUI无入口查看RPC调用历史/频率统计
   - **数据源**：前端 `window.qv.request()` 调用

2. **ResourceIndex cache状态**
   - **现状**：后端 `DaemonState.project_caches` (`src/quantumvitas/daemon/server.py` 94-100行) 维护per-project cache
   - **缺失**：GUI无入口查看cache命中率、invalidation事件
   - **数据源**：后端daemon state

3. **Workflow execution trace**
   - **现状**：`WorkflowResult` 包含 `steps` 数组，但无详细execution trace
   - **缺失**：GUI无入口查看step执行顺序、依赖关系、失败原因
   - **数据源**：后端 `WorkflowRunner.run()` (`src/quantumvitas/workflow/runner.py`)

4. **QE metadata schema migration history**
   - **现状**：有legacy v0/v1/v2 JSON文件，但无迁移历史记录
   - **缺失**：GUI无入口查看schema版本历史、迁移路径
   - **数据源**：文件系统（`src/quantumvitas/data/*.json`）

5. **IPC bridge request/response latency**
   - **现状**：preload/main process有日志，但无聚合统计
   - **缺失**：GUI无入口查看IPC延迟分布、错误率
   - **数据源**：Electron main process (`gui/electron/main.ts`)

---

### 4.3 数据源单一真相来源总结

| Debug信息 | 单一真相来源 | 文件路径 |
|-----------|-------------|---------|
| QE metadata load state | 后端 `QE_METADATA_LOAD_STATE` | `src/quantumvitas/data/qe_metadata.py` (31-36行) |
| Job io_dir | 后端 `compute_io_dir_from_workflow_model()` | `src/quantumvitas/workflow/runner.py` (18-42行) |
| Daemon status | Electron main process | `gui/electron/main.ts` (daemonStatus对象) |
| ResourceIndex cache | 后端 `DaemonState.project_caches` | `src/quantumvitas/daemon/server.py` (94-100行) |

---

### 4.4 Debug/Settings页面布局问题

**SettingsPanel滚动问题**（已修复）：
- **文件**：`gui/src/components/panels/SettingsPanel.css` (93-126行)
- **修复**：移除了嵌套scroll容器，统一由 `.app-shell__content` 处理滚动
- **状态**：✅ 已解决

**Diagnostics区域**：
- **文件**：`gui/src/components/panels/SettingsPanel.tsx` (399-500行)
- **布局**：折叠区域，展开时显示logs（200行，自动滚动到底部）
- **潜在问题**：logs区域可能过长，但已有 `max-height` 和滚动处理 (SettingsPanel.tsx 124-128行)

---

## 5) 前端样式/交互一致性审计

### 5.1 硬编码颜色问题

**已发现的位置**：

1. **JobsPanel.css** (685, 691行)：
   ```css
   .job-step-stepper__dot--running { color: white; }
   .job-step-stepper__dot--completed { color: white; }
   ```
   - **问题**：dark theme下可能不可读
   - **建议**：使用 `var(--text-on-primary)` 或 `var(--text-on-success)`

2. **AnalysisPanel.css** (160行)：
   ```css
   .analysis-chart__tooltip { color: white; }
   ```
   - **问题**：tooltip背景可能不是primary色
   - **建议**：使用 `var(--text-primary)` 或根据背景选择

3. **Sidebar.css** (211, 317行)：
   ```css
   .sidebar__tab--active { color: white; }
   .sidebar__action-btn { color: white; }
   ```
   - **问题**：active tab背景是primary色，但light theme下可能不可读
   - **建议**：使用 `var(--text-on-primary)`

4. **StepDetailPanel.css** (145, 163, 224行)：
   ```css
   .step-detail__run-btn { color: white; }
   .step-detail__cancel-btn { color: white; }
   ```
   - **问题**：按钮背景是primary/danger色，但light theme下可能不可读
   - **建议**：使用 `var(--text-on-primary)` / `var(--text-on-danger)`

**修复状态**：部分已修复（见 `docs/JOB_IO_DIRECTORY_SEMANTICS.md`），但上述位置仍需检查

---

### 5.2 cursor/hover样式缺失

**已检查的位置**（JobsPanel有cursor:pointer，但其他Panel可能缺失）：

1. **QEParameterBrowserPanel**：
   - 搜索icon按钮：需要检查 `cursor: pointer` (QEParameterBrowserPanel.tsx 570-580行)
   - Popover关闭按钮：需要检查 (QEParameterBrowserPanel.tsx 650-660行)

2. **WorkflowListPanel**：
   - Reorder按钮：有 `title` 但可能缺少 `cursor: pointer` (WorkflowListPanel.tsx 789-810行)

3. **SettingsPanel**：
   - Theme切换按钮：需要检查 (SettingsPanel.tsx 296-308行)
   - Diagnostics展开按钮：需要检查 (SettingsPanel.tsx 399行)

**建议**：全局添加 `.btn, button { cursor: pointer; }` 或使用CSS变量统一管理

---

### 5.3 tooltip/aria-label一致性

**当前状态**：
- **JobsPanel**：大部分按钮有 `title` 属性 (JobsPanel.tsx 77, 94, 178, 303, 310, 354行)
- **WorkflowListPanel**：reorder按钮有 `title` (WorkflowListPanel.tsx 789, 797, 808行)
- **QEParameterBrowserPanel**：搜索按钮有 `title="Search all modules"` (QEParameterBrowserPanel.tsx 570行)

**缺失**：
- Icon-only按钮可能缺少 `aria-label`（仅依赖 `title`）
- **建议**：统一使用 `aria-label` + `title` 双重保障

---

## 6) Top 5 最值得先改的小改动

### 1. 统一硬编码颜色为CSS变量
- **改动点**：替换 `color: white` 为语义token（`var(--text-on-primary)`, `var(--text-on-danger)`）
- **涉及文件**：
  - `gui/src/components/panels/JobsPanel.css` (685, 691行)
  - `gui/src/components/panels/AnalysisPanel.css` (160行)
  - `gui/src/components/layout/Sidebar.css` (211, 317行)
  - `gui/src/components/panels/StepDetailPanel.css` (145, 163, 224行)
- **收益**：dark/light theme自动适配，提升可读性
- **风险**：低（已有CSS变量定义在 `gui/src/index.css`）

---

### 2. 添加RPC调用统计到Diagnostics
- **改动点**：在SettingsPanel Diagnostics区域添加"RPC Statistics"section，显示最近N次调用的command、耗时、错误率
- **涉及文件**：
  - `gui/src/hooks/useQVClient.ts` (148-155行) - 添加统计收集
  - `gui/src/components/panels/SettingsPanel.tsx` (399-460行) - 添加显示区域
- **收益**：快速诊断RPC性能问题、重复调用
- **风险**：中（需要维护统计state，可能影响性能）

---

### 3. 统一icon按钮的cursor/hover样式
- **改动点**：全局CSS规则 `.btn, button, [role="button"] { cursor: pointer; }` + hover效果
- **涉及文件**：
  - `gui/src/index.css` - 添加全局规则
  - 各Panel CSS文件 - 移除重复定义
- **收益**：提升交互一致性，减少遗漏
- **风险**：低（纯CSS改动）

---

### 4. 增强Job io_dir显示（添加计算来源提示）
- **改动点**：在JobsPanel的io_dir显示旁添加tooltip，说明"Computed from workflow.working_dir (default: raw)"
- **涉及文件**：
  - `gui/src/components/panels/JobsPanel.tsx` (295-315行)
- **收益**：帮助用户理解io_dir来源，便于debug路径问题
- **风险**：低（仅UI增强）

---

### 5. 添加ResourceIndex cache状态到Diagnostics
- **改动点**：新增RPC `get_project_cache_info`，返回当前project的cache状态（hit/miss计数、invalidation事件）
- **涉及文件**：
  - `src/quantumvitas/daemon/server.py` - 添加handler
  - `gui/src/components/panels/SettingsPanel.tsx` - 添加显示
- **收益**：诊断registry同步问题、cache效率
- **风险**：中（需要后端改动，可能暴露内部实现细节）

---

## 总结

**核心发现**：
1. **State管理**：基本清晰，但workflow detail更新有优化空间（已通过callback优化）
2. **RPC调用**：JobsPanel轮询正常，QE metadata有后端cache，但缺少前端统计
3. **Debug信息**：QE metadata load state已展示，但RPC统计、ResourceIndex cache状态缺失
4. **样式问题**：硬编码颜色需统一为CSS变量，cursor/hover需全局统一
5. **布局问题**：SettingsPanel嵌套滚动已修复

**优先级建议**：
- **P0**：硬编码颜色修复（影响可读性）
- **P1**：RPC统计、ResourceIndex cache状态（提升debug能力）
- **P2**：cursor/hover统一、io_dir tooltip增强（UX polish）

