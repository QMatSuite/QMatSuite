# QMatSuite Distribution 实施规划 v2

## 总体原则

- **Code change阶段**（步骤1-3, 6）：每步结束必须 pytest 全绿 + Playwright e2e 全绿
- **打包阶段**（步骤5, 7）：不改核心 Python code，只加 CI/installer 脚本
- 每一步是一个独立 CLI agent session，有明确入口和出口条件
- Agent 自查自纠：每步结束运行 full test suite，失败自己修，修不了在 worklog 里标注
- **架构纪律**：步骤2和3必须先读项目 constitution/laws/specs，kernel vs API 分层必须正确，daemon/CLI/MCP 只调 API
- 你（Haonan）只做：一次性配 GitHub Secrets（Apple 证书 + MS Trusted Signing 凭证 + PyPI token），最终验收

## 依赖关系图

```
步骤1 (Foundation) ──→ 步骤2 (Engine Registry) ──→ 步骤3 (Micromamba)
     │                                                      │
     └──→ 步骤4 (PyPI发布)                                  │
                  │                                          │
                  └──→ 步骤5 (Runtime Tarball CI) ←──────────┘
                              │
                              └──→ 步骤6 (Electron + GUI Engine Manager)
                                          │
                                          └──→ 步骤7 (Release CI: Build + Sign + Publish)
```

## 步骤详情

---

### 步骤1：Foundation ⚙️
| 项目 | 内容 |
|------|------|
| **做什么** | paths.py 重构（4级resolution chain）、删 ase/bs4/pyscf 死依赖、pymatgen/matplotlib/scipy lazy import、package_data 修复 |
| **改Code** | ✅ Python |
| **预估** | 1天 |
| **入口条件** | pytest 全绿 |
| **出口条件** | pytest 全绿 + `pip install .`（非editable）不 crash + daemon 启动 <500ms |
| **Prompt** | `PROMPT_STEP1_FOUNDATION.md`（已交付agent执行中） |

---

### 步骤2：Engine Registry 🔧
| 项目 | 内容 |
|------|------|
| **做什么** | `engines.json` registry 模块 + `ENGINE_META`（15引擎含Python引擎）+ 替换 QE two-state resolver 为 registry lookup + 集成所有 engine handler + `list_engines` MCP tool 返回真实 installed 状态 |
| **改Code** | ✅ Python |
| **预估** | 2-3天 |
| **入口条件** | 步骤1完成 |
| **出口条件** | pytest 全绿 + `list_engines(installed_only=True)` 只返回真实安装的引擎 + QE 通过 registry 跑计算 |
| **架构要求** | Agent 必须先读完所有 constitution/laws/specs for API layer，在 worklog 写出 kernel vs API 分层设计。engine 发现/registry 读写/binary 验证 → kernel。list_engines/set_active/verify → API。daemon/CLI/MCP 只调 API。 |
| **测试要求** | mock engine binary（tmp dir 放假 pw.x echo 脚本）测试发现逻辑、engines.json CRUD、list_engines 在 mock 环境下只返回真实安装的引擎。Windows 平台差异（pw.exe vs pw.x）要有测试。 |
| **Prompt** | 待写 |

---

### 步骤3：Micromamba Module 📦
| 项目 | 内容 |
|------|------|
| **做什么** | micromamba 下载/SHA256 验证模块、conda env 创建/管理、engine install/verify/set-active daemon RPC 命令、CLI 命令 `qv engine install xtb`、GitHub Release 下载机制（QE binary 双版本） |
| **改Code** | ✅ Python |
| **预估** | 3-5天 |
| **入口条件** | 步骤2完成 |
| **出口条件** | pytest 全绿 + `qv engine install xtb` 装到 micromamba env + `list_engines` 显示 xTB installed + 能用装好的 xTB 跑计算 |
| **架构要求** | 同步骤2——先读 law/spec，kernel vs API 分层。micromamba binary 管理/conda env CRUD → kernel。engine_install()/engine_uninstall() → API。daemon RPC/CLI/MCP 只调 API。 |
| **测试要求** | micromamba 下载用 mock HTTP。conda env 创建标记 `@pytest.mark.integration`（CI 有 micromamba 时跑）。端到端：如果 xTB conda 包可用，真实装一个验证。 |
| **Prompt** | 待写 |

---

### 步骤4：PyPI 发布 🚀
| 项目 | 内容 |
|------|------|
| **做什么** | TestPyPI 测试 → PyPI 正式发布 → 干净 env 验证 |
| **改Code** | ❌ 不改 |
| **预估** | 半天 |
| **入口条件** | 步骤1完成 |
| **出口条件** | `pip install quantumvitas` 工作、`qv --help` 正常、MCP server 能启动 |
| **你的参与** | 配 PyPI token 到 GitHub Secrets 或手动 `twine upload` |
| **Prompt** | 待写 |

---

### 步骤5：Runtime Tarball CI 🏗️
| 项目 | 内容 |
|------|------|
| **做什么** | GitHub Actions workflow：micromamba env → pip install quantumvitas → tar --zstd → upload artifact。矩阵：macOS-arm64 + Windows-x64。 |
| **改Code** | ❌ 只加 CI workflow YAML |
| **预估** | 1天 |
| **入口条件** | 步骤4完成（PyPI wheel 可用）|
| **出口条件** | CI 产出 runtime tarball，解压后 python 能 import quantumvitas |
| **Prompt** | 待写 |

---

### 步骤6：Electron 集成 + GUI Engine Manager 🖥️
| 项目 | 内容 |
|------|------|
| **做什么** | (A) Electron Python integration (B) GUI Engine Manager Panel |
| **改Code** | ⚠️ Electron/TypeScript + React + Python daemon RPC |
| **预估** | 4-5天 |
| **入口条件** | 步骤3和5都完成 |
| **出口条件** | Playwright e2e 全绿 + Engine Manager Panel 可用 + 首次启动解压 flow 工作 |

**Part A: Electron Python Integration**
- `findPythonPath()` 加 runtime env 检测（priority 4 slot）
- `QMATSUITE_ELECTRON=1` 环境变量传递给 Python daemon
- 首次启动检测 compressed tarball → 解压 → 进度条 UI → 验证 → 启动 daemon
- `electron-builder.json5` 生产配置（appId: `com.qmatsuite.app`、product name、icons）

**Part B: GUI Engine Manager Panel**

两个入口点，**无弹窗打断用户探索**：

**入口1：Run 时缺 engine → inline 引导（不是 modal 弹窗）**
- 用户点 Run → daemon 返回 `ENGINE_NOT_INSTALLED` structured error
- GUI 在结果区域显示 **inline 引导 panel**（不是弹窗）：
  ```
  ⚠️ Quantum ESPRESSO is not installed
  
  This calculation requires pw.x.
  
  [Install QE]  [Configure existing QE path]  [Open Engine Manager]
  ```
- 用户可以处理，也可以关掉继续探索其他功能
- 安装完成后 panel 变成 "QE 7.5 installed ✓ — Run again?"

**入口2：Settings → Engine Manager（Settings 页面最上方）**
- Engine Availability section 在 Settings 页面顶部
- 显示所有引擎：名称、版本、source、installed/not installed
- 操作：Install（micromamba one-click）、Configure Path（user_path 引擎）、Set Active（多版本切换）、Uninstall
- 安装进度条（micromamba install 实时输出）

**UX 原则：不主动打断用户**
- **lite 首次启动不弹窗**。用户可以自由探索 GUI、浏览 demo reference results（已有 `get_demo_results`）、了解功能
- 只在用户主动 Run 且缺引擎时才出 inline 引导
- demo store 的预计算参考结果让 lite 用户无引擎也能看 band structure plot、DOS 等输出

**后端接口**（步骤3的 API 层已实现）：
- `list_engines()` → 引擎列表 + installed 状态
- `install_engine(name, version, source)` → micromamba install / GitHub download
- `set_active_engine(name, installation_id)` → 切换活跃版本
- `verify_engine(name)` → 检查 binary 可用性
- `configure_engine_path(name, path, env_vars)` → user_path 注册
- `uninstall_engine(name, installation_id)` → 删除

| **Prompt** | 待写 |

---

### 步骤7：Release CI Workflows 📀✍️
| 项目 | 内容 |
|------|------|
| **做什么** | Windows NSIS + Trusted Signing CI、macOS DMG/pkg + codesign + notarize CI、PyPI release CI、QE OpenMP bundling、SSSP bundling、GitHub Release |
| **改Code** | ❌ CI YAML + installer 脚本 |
| **预估** | 3-5天 |
| **入口条件** | 步骤6完成 + QE OpenMP binary 可用 |
| **出口条件** | CI workflow 手动触发 → 签名 installer → GitHub Release → 干净机器无警告安装 |

**CI Workflow 矩阵：**
```
.github/workflows/
├── tests.yml                      # 已有：pytest + Playwright (Ubuntu + macOS)
├── build-runtime-tarball.yml      # 步骤5产出
├── release-windows.yml            # NSIS + MS Trusted Signing + Release
├── release-macos.yml              # DMG/pkg + codesign + notarize + Release
└── release-pip.yml                # Build wheel + upload PyPI
```

所有 release workflow 用 `workflow_dispatch` 触发：手动 Run，选参数（版本号、lite/full、sign、publish）。

**Windows workflow**（参照 `qmatsuite-toolchain` 已有 Trusted Signing 配置）：
1. Build Electron → NSIS installer
2. Bundle runtime tarball + QE + SSSP（full）
3. Microsoft Trusted Signing
4. Upload GitHub Release asset

**macOS workflow**：
1. Build Electron → DMG（lite）或 .pkg（full）
2. Bundle runtime tarball + QE + SSSP（full）
3. Import Developer ID cert → `codesign`
4. `xcrun notarytool submit` → 等 Apple 审核（~2-5min）
5. `xcrun stapler staple`
6. Upload GitHub Release asset

**Agent 工作方式**：先在本地 macOS 打包 + debug → 确认可行后写 CI YAML。避免 CI runner 反复 debug 浪费时间。

**你的一次性配置（GitHub Secrets）：**
| Secret | 用途 |
|--------|------|
| `APPLE_CERTIFICATE_P12` | Developer ID 证书 base64 |
| `APPLE_CERTIFICATE_PASSWORD` | .p12 密码 |
| `APPLE_TEAM_ID` | Apple Team ID |
| `APPLE_NOTARY_ISSUER_ID` | App Store Connect API |
| `APPLE_NOTARY_KEY_ID` | API key ID |
| `APPLE_NOTARY_KEY` | API private key (.p8) |
| `AZURE_TENANT_ID` | MS Trusted Signing |
| `AZURE_CLIENT_ID` | MS Trusted Signing |
| `AZURE_CLIENT_SECRET` | MS Trusted Signing |
| `PYPI_API_TOKEN` | PyPI upload |

配完后全自动，你只需要点 "Run workflow"。

**前置工作**：qmatsuite-toolchain 加 QE OpenMP-only CI workflow（可与步骤7同步）。

| **Prompt** | 待写 |

---

## 最终验收测试矩阵

| 场景 | 平台 | 预期用户旅程 |
|------|------|-------------|
| full→Si bands | Win x64 | 下载290MB → NSIS安装 → 启动 → Load demo → Run → band plot |
| full→Si bands | macOS arm64 | 下载290MB → .pkg安装 → 启动 → Load demo → Run → band plot |
| lite→探索→装QE→跑 | macOS arm64 | 下载190MB → 拖装 → 首次启动解压(30s) → 浏览demo ref results → 点Run→引导装QE → 跑demo |
| lite→配VASP | Win x64 | 下载190MB → 安装 → Settings→Engine Manager → Configure VASP path → Run VASP SCF |
| pip→MCP | Linux x64 | `pip install quantumvitas[mcp]` → MCP server → agent 跑 QE 计算 |
| pip→CLI engine | macOS arm64 | `pip install quantumvitas` → `qv engine install xtb` → xTB 计算完成 |

## 不在 Launch 范围内（defer post-launch）

- Linux AppImage
- Electron auto-update（`electron-updater`）
- QE universal binary (arm64 + x86_64 lipo)
- Engine update notification ("xTB 6.8.0 available")
- Offline installer（air-gapped HPC）
- Contributing guide for new engines
