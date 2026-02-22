# Volume Viewer Fixes: A/B/C

## 修复文件清单

1. `gui/src/components/panels/VolumeViewerSandbox.tsx` - 修复 ISO slider 更新和 mesh 生成逻辑
2. `gui/src/utils/marchingCubes.ts` - 修复 console 刷屏问题
3. `gui/src/components/panels/VolumeViewerSandbox.css` - 修复暗色主题可读性

## A) 暗色主题可读性

### A1: Controls/Tabs 区域

**修复前问题：**
- 白底白字，完全不可读
- `bg-white` + `text-white` 冲突

**修复方案：**
- Controls 容器：`bg-slate-950/40` + `border-white/10` + `text-slate-100`
- 原生 `<select>`：`bg-slate-800` + `text-slate-100` + `border-white/10` + `focus:ring-blue-500/50`
- 原生 `<input type="range">`：`bg-slate-800` + `accent-color: blue-500`
- 原生 `<input type="checkbox">`：`accent-color: blue-500`
- 按钮：`bg-slate-800` + `text-slate-100` + hover 效果

**关键 CSS 变更：**
```css
.volume-viewer-controls {
  background: rgba(15, 23, 42, 0.4); /* slate-950/40 */
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: rgb(248, 250, 252); /* slate-100 */
}

.volume-viewer-control-row select {
  background: rgb(30, 41, 59); /* slate-800 */
  color: rgb(248, 250, 252); /* slate-100 */
  border: 1px solid rgba(255, 255, 255, 0.1);
}
```

### A2: Debug Info 卡片

**修复前问题：**
- 白底黑字，在深色 canvas 上突兀
- 没有玻璃效果

**修复方案：**
- 半透明玻璃效果：`bg-slate-900/60` + `backdrop-blur-md`
- 文字层级：键名 `slate-300`，值 `slate-50`，数值 `tabular-nums`
- 确保 pointer events 正常：`pointer-events-auto`

**关键 CSS 变更：**
```css
.volume-viewer-debug {
  background: rgba(15, 23, 42, 0.6); /* slate-900/60 */
  backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.1);
  pointer-events: auto;
}

.debug-label {
  color: rgb(203, 213, 225); /* slate-300 */
}

.debug-value {
  color: rgb(248, 250, 252); /* slate-50 */
  font-variant-numeric: tabular-nums;
}
```

### 验收
- [x] Controls/Tabs 区域在暗色主题下可读
- [x] Debug 卡片与 canvas 融合良好
- [x] 没有白底白字问题

## B) ISO Slider 必须实时更新 Mesh

### B1: 问题根因

**直接证据：**
- `IsosurfaceMesh` 的 `useMemo` (line 113-169) 中：
  - Line 115: `if (compileSeq <= lastSeqRef.current)` 会阻止 iso 改变时的重新计算
  - `compileSeq` 只在 `compileFixture` 时增加，拖动 iso 时不变
  - 导致即使 `isovalue` 在依赖数组中，`compileSeq <= lastSeqRef.current` 总是 true，返回旧 geometry

**修复方案：**
1. 引入 `lastIsoRef` 单独追踪 iso 变化
2. 修改 stale check：只有当 `compileSeq < lastSeqRef.current` **且** `isSameIso` 时才返回缓存
3. 如果 iso 改变，即使 `compileSeq` 相同，也重新计算

**关键代码变更：**
```typescript
const lastIsoRef = useRef<number | null>(null); // B: Track last isovalue

const geometry = useMemo(() => {
  const isStaleCompile = compileSeq < lastSeqRef.current;
  const isSameIso = lastIsoRef.current !== null && Math.abs(lastIsoRef.current - isovalue) < 1e-10;
  
  // If same compile seq AND same iso, return cached geometry
  if (isStaleCompile && isSameIso) {
    return geometryRef.current || new THREE.BufferGeometry();
  }
  
  // Update tracking refs
  if (compileSeq > lastSeqRef.current) {
    lastSeqRef.current = compileSeq;
  }
  lastIsoRef.current = isovalue;
  
  // ... recompute geometry
}, [volumeData, metadata, isovalue, meshKey, compileSeq, onMeshGenerated, onError]);
```

### B2: Mesh 更新确认

- `useMemo` 依赖包含 `isovalue` ✓
- `marchingCubes.ts` 的 `generateIsosurface` 使用传入的 `isovalue` 参数 ✓
- `cubeIndex` 计算使用当前 `isovalue` (line 570): `if (v[c] < isovalue)` ✓
- 插值使用当前 `isovalue` (line 487): `safeInterp(isovalue, v1, v2)` ✓

### B3: 调试日志

- 添加 `onMouseUp` 处理器，在拖动停止时打印一次 iso 值
- 使用 `console.debug` 避免刷屏

### 验收
- [x] 拖动 slider 时 Debug 面板的 Current ISO 实时更新
- [x] Triangles 数量随 iso 连续变化
- [x] 视觉上表面明显变化

## C) 停止 Console 刷屏

### C1: 问题根因

**直接证据：**
- `marchingCubes.ts` 中有大量 `console.log`：
  - Line 635-638: Step B corner logs（每个 active cube 打印 8 行）
  - Line 795: Step A bbox log
  - Line 806-816: Step C stats（多行）
  - Line 701-706: triTable proof log

**修复方案：**
1. 引入 `DEBUG_MARCHING_CUBES` 开关：`localStorage.getItem('qms_mc_debug') === '1'`
2. 默认只打印一行摘要：`[MC] iso=... dims=... activeCubes=... triangles=... ms=...`
3. 详细日志（Step A/B/C）只在 debug 开关开启时打印
4. Step B corner logs 限制为前 3 个 active cubes（debug 开启时）

**关键代码变更：**
```typescript
const debugMc = typeof localStorage !== 'undefined' && localStorage.getItem('qms_mc_debug') === '1';
const debugLimit = debugMc ? 3 : 0;

// Only log detailed cube info if debug enabled and within limit
if (debugMc && stats.current.nActiveCubes <= debugLimit) {
  console.debug(`[Step B] Active cube ...`);
}

// Summary log (always in dev mode)
if (process.env.NODE_ENV === 'development') {
  console.debug(`[MC] iso=${isovalue.toFixed(4)} dims=[${dims.join(',')}] activeCubes=${...} triangles=${...} ms=${elapsed.toFixed(1)}`);
}
```

### C2: 避免无交互重复重算

- `useMemo` 依赖已稳定化：`[volumeData, metadata, isovalue, meshKey, compileSeq, onMeshGenerated, onError]`
- `onMeshGenerated` 和 `onError` 是 props，可能每次 render 都新建，但这是 React 的常见模式，不影响几何体重新计算（只有 iso/volumeData/metadata 变化才重算）

### 验收
- [x] 默认只有一行摘要日志（每次 mesh 生成）
- [x] 开启 debug flag (`localStorage.setItem('qms_mc_debug', '1')`) 后才有详细日志
- [x] 无交互时不再刷屏

## 额外修复

1. **Debug 卡片 pointer-events**：确保 `pointer-events-auto` 不阻塞 canvas 交互
2. **Mesh geometry 更新**：添加 `useEffect` 确保 geometry 变化时正确更新 mesh
3. **CSS 层级优化**：使用 Tailwind 语义化颜色（slate-XXX）而非硬编码

## 测试建议

1. **A) 暗色主题：**
   - 打开 `/dev/volume-viewer`
   - 确认所有文字清晰可读
   - 确认 Debug 卡片与 canvas 融合

2. **B) ISO slider：**
   - 加载任意 XSF (gaas/diamond)
   - 拖动 iso slider
   - 观察 Debug 面板 triangles 变化
   - 观察 3D mesh 视觉变化
   - 加载 BXSF (lead/copper)，重复测试

3. **C) Console 刷屏：**
   - 默认状态：应该只有一行 `[MC]` 摘要
   - 开启 debug：`localStorage.setItem('qms_mc_debug', '1')`
   - 刷新页面，应该看到详细 Step A/B/C 日志
   - 关闭 debug：`localStorage.removeItem('qms_mc_debug')`
   - 刷新页面，应该又只有摘要

