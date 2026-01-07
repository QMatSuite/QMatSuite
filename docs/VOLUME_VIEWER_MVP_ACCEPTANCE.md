# Volume Viewer MVP - Acceptance Checklist

## 实现完成情况

### ✅ Step 0: Dev Route
- [x] ViewType 添加 'dev-volume'
- [x] App.tsx 添加 VolumeViewerSandbox 路由
- [x] Sidebar 添加 "Volume (DEV)" 按钮

### ✅ Step 1: 3D Canvas
- [x] Canvas with ambientLight + directionalLight
- [x] OrbitControls for interaction
- [x] Grid helper for reference

### ✅ Step 2: Marching Cubes
- [x] `marchingCubes.ts` MVP implementation
- [x] Support FORTRAN (i-fastest) and C (k-fastest) data order
- [x] IsosurfaceMesh component
- [x] Blob loading via preload API

### ✅ Step 3: UI Controls
- [x] Isovalue slider (range based on value_min/value_max)
- [x] ±iso toggle for dual surfaces
- [x] Loading states

## 如何启动并验收

### 启动步骤

1. **启动后端 daemon:**
```bash
cd /Users/kfranke/QMatSuite
source .venv/bin/activate
python -m quantumvitas.daemon.server
```

2. **启动前端 (另一个终端):**
```bash
cd /Users/kfranke/QMatSuite/gui
npm run dev
```

3. **打开 Volume Viewer:**
   - 在 Sidebar 最下方点击 "Volume (DEV)" 按钮
   - 或直接访问 dev-volume view

### 验收清单 (Step 4)

#### [ ] example01/gaas_00001.xsf
- [ ] 点击 fixture 后能编译成功
- [ ] 能看到 isosurface mesh (蓝色)
- [ ] 拖动 iso slider，mesh 实时更新
- [ ] 开启 ±iso，出现红色对称 surface
- [ ] OrbitControls 可旋转/缩放

#### [ ] example05/diamond_00001.xsf
- [ ] 同上测试流程
- [ ] Mesh 形状合理（不崩溃）

#### [ ] example02/lead.bxsf
- [ ] 能编译 (band=1, E=0 default)
- [ ] 能显示 Fermi surface (即使粗糙)
- [ ] 控件可用

#### [ ] example04/copper.bxsf
- [ ] 同上测试流程
- [ ] Fermi surface 显示正常

## 已知限制 (MVP)

### 算法限制
- **非正交 grid_vectors 暂不支持**: 当前假设 grid_vectors 近似正交（fixtures 通常满足）
- **简化的三角化**: 使用 fan triangulation，不是完整 MC33 的 256 cases
- **Flat shading**: 法线未平滑，表面可能有锯齿
- **无 vertex deduplication**: 内存占用较高

### 功能限制
- **仅 preview blob**: 未实现 full-res refine
- **BXSF 仅 band 1**: 多 band 选择未实现
- **无 BZ clipping**: Fermi surface 未做 Brillouin zone 裁剪
- **无 supercell tiling**: MLWF 周期影像未实现
- **无 structure overlay**: 原子/晶格框未叠加

### 性能限制
- **主线程计算**: 未使用 WebWorker (preview 网格足够小)
- **无 debounce**: slider 拖动时可能卡顿（需添加）

## 构建检查

### TypeScript 编译
```bash
cd /Users/kfranke/QMatSuite/gui
npm run build
```

预期：无 TypeScript 错误

### Linter
```bash
npm run lint
```

预期：无严重错误（warning 可接受）

## 下一步 (Post-MVP)

1. **完整 MC33 triangulation table**
2. **Vertex deduplication + normal smoothing**
3. **WebWorker for heavy computation**
4. **Full-res blob loading (on-demand)**
5. **Multi-band selector for BXSF**
6. **Structure overlay (atoms + lattice box)**
7. **Supercell tiling for MLWF**
8. **BZ clipping for Fermi surfaces**
9. **非正交 grid_vectors 支持**
10. **Export mesh (STL/OBJ)**

## 技术债务

- [ ] 添加 debounce 到 isovalue slider (150ms)
- [ ] 添加 error boundary 到 Canvas
- [ ] 添加 unit tests for marchingCubes.ts
- [ ] 优化 geometry 更新（避免每次重建）
- [ ] 添加 loading progress for large blobs

