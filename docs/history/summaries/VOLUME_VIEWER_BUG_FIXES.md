# Volume Viewer Core Bug Fixes

## 修复证据与调用链分析

### P0: 竞态/串台（Phase0 根因）

**直接证据（修复前）：**
1. **分散的状态更新**：
   - `volumeData` (line 156): `setVolumeData(data)` 
   - `debugInfo.dims` (line 172, 245): `setDebugInfo(prev => ({ ...prev, dims }))`
   - 两个状态在不同的异步调用中分别更新，如果用户快速切换 fixture，可能导致：
     - 请求 A 设置 `volumeData` (来自 fixture1，1000 个值)
     - 请求 B 设置 `dims` (来自 fixture2，40x40x40 = 64000)
     - 结果：Phase0 验证失败 `values.length(1000) != nx*ny*nz(64000)`

2. **requestId 检查不够强**：
   - `loadBlob` 只检查 `currentRequestId !== latestRequestIdRef.current`，但没有检查是否来自同一个 fixture/band/resolution
   - 如果用户点击 fixture1 → 点击 fixture2 → fixture1 响应先返回，会错误地应用 fixture1 的数据到 fixture2 的界面

3. **缺少 AbortController**：
   - 没有取消机制，旧请求会继续执行并可能覆盖新状态

**修复方案：**
1. **原子状态 `CompiledVolumeState`**：
   ```typescript
   interface CompiledVolumeState {
     key: string; // `${fixturePath}|${kind}|${resolution}|${bandIndex}`
     seq: number;
     fixture: Fixture;
     volume: CompiledVolume;
     blobId: string;
     blobData: Float32Array;
     dims: [number, number, number];
     // ... 所有相关状态原子化
   }
   ```

2. **compileKey + seq 双重检查**：
   ```typescript
   const compileKey = generateCompileKey(fixture, resolution, bandIndex);
   const currentSeq = ++seqRef.current;
   latestSeqRef.current = currentSeq;
   latestKeyRef.current = compileKey;
   
   // 在 loadBlob 返回时检查：
   if (currentSeq !== latestSeqRef.current || compileKey !== latestKeyRef.current) {
     // 丢弃旧响应
     return;
   }
   ```

3. **AbortController**：
   ```typescript
   const abortController = new AbortController();
   abortControllerRef.current = abortController;
   // 在 loadBlob 中检查 signal.aborted
   ```

4. **validateVolumeGrid 函数**：
   ```typescript
   function validateVolumeGrid(values, dims, data_order, context) {
     if (values.length !== dims[0] * dims[1] * dims[2]) {
       throw new Error(
         `Phase0 validation failed: values.length(${values.length}) != nx*ny*nz(${expectedValues}) ` +
         `key=${context.key}, seq=${context.seq}, blobId=${context.blobId}`
       );
     }
   }
   ```

**关键 diff：**
- `gui/src/components/panels/VolumeViewerSandbox.tsx`:
  - 移除分散的 `volumeData`, `debugInfo.dims`, `selectedVolume` state
  - 新增原子状态 `compiledVolume: CompiledVolumeState | null`
  - `compileFixture` 中引入 `compileKey` 和 `seq` 追踪
  - `loadBlob` 中添加双重检查（seq + key）
  - 添加 `validateVolumeGrid` 函数

### P1: BXSF 能量参考系（inferEnergyReference 未定义）

**直接证据（修复前）：**
- Line 338: `energyRef = inferEnergyReference(...)` 但没有任何 import
- 运行时错误：`ReferenceError: inferEnergyReference is not defined`

**修复方案：**
```typescript
import { inferEnergyReference, type EnergyReferenceResult } from '../../utils/energyReference';
```

**能量推断逻辑（已实现，符合要求）：**
- Rule A: `fermi_energy` 在 `[min, max]` 范围内 => `reference="absolute"`, `iso=fermi_energy`
- Rule B: `0` 在范围内且 `abs(Ef) > 2*(max-min)` => `reference="relative_to_fermi"`, `iso=0`
- Rule C: 其他 => `reference="unknown"`, `iso=(min+max)/2`

**UI 改进：**
- Debug 面板显示：`Fermi Energy`, `Energy Reference`, `ISO Default Reason`
- 添加两个按钮：`Set iso = Ef` 和 `Set iso = 0`

**关键 diff：**
- `gui/src/components/panels/VolumeViewerSandbox.tsx`:
  - Line 9: 添加 import
  - Line 338: 调用逻辑已存在，现在可以正常工作

### P2: Band dropdown 必须真正影响 mesh

**直接证据（修复前）：**
- Band dropdown 改变时调用 `compileFixture(selectedFixture, newBand)`
- 但 `compileKey` 没有包含 `bandIndex`，导致相同的 fixture 在不同 band 时 key 相同
- `IsosurfaceMesh` 的 `useMemo` 依赖没有包含 `bandIndex`

**修复方案：**
1. **compileKey 包含 bandIndex**：
   ```typescript
   const generateCompileKey = (fixture, resolution, bandIndex) => {
     const band = bandIndex !== undefined ? `${bandIndex}` : 'default';
     return `${fixture.path}|${fixture.kind}|${resolution}|${band}`;
   };
   ```

2. **band 改变触发重新 compile**：
   ```typescript
   const handleBandChange = useCallback((newBand: number) => {
     setSelectedBandIndex(newBand);
     if (compiledVolume && compiledVolume.fixture.kind === 'bxsf') {
       compileFixture(compiledVolume.fixture, newBand, compiledVolume.resolution);
     }
   }, [compiledVolume, compileFixture]);
   ```

3. **mesh 依赖 compileSeq**：
   ```typescript
   <IsosurfaceMesh
     compileSeq={compiledVolume.seq} // band 改变会触发新的 seq
     ...
   />
   ```

**关键 diff：**
- `gui/src/components/panels/VolumeViewerSandbox.tsx`:
  - `generateCompileKey` 包含 bandIndex
  - `handleBandChange` 回调触发重新 compile
  - `IsosurfaceMesh` 接收 `compileSeq` prop，确保 band 改变时重新计算 mesh

### P3: 停止无操作刷屏

**直接证据（修复前）：**
1. **IsosurfaceMesh geometry useMemo 过度重新计算**：
   - 依赖数组包含 `onMeshGenerated` (line 123)
   - 父组件每次 rerender 时，如果 `onMeshGenerated` 是新的函数引用，就会重新计算 mesh
   - OrbitControls 的 `onChange` 会导致 rerender，进而导致 mesh 重新计算

2. **console.log 无限制输出**：
   - Line 96-98: 每次 mesh 计算都打印 stats
   - 没有检查是否是重复计算

**修复方案：**
1. **compileSeq 追踪**：
   ```typescript
   const lastSeqRef = useRef<number>(-1);
   const geometry = useMemo(() => {
     if (compileSeq <= lastSeqRef.current) {
       return geometryRef.current || new THREE.BufferGeometry();
     }
     lastSeqRef.current = compileSeq;
     // ... 计算 mesh
   }, [volumeData, metadata, isovalue, meshKey, compileSeq, onMeshGenerated, onError]);
   ```
   - 只有当 `compileSeq` 增加时才重新计算
   - 依赖数组仍包含 `onMeshGenerated`，但通过 `compileSeq` 检查避免了不必要的计算

2. **Gate debug logs**：
   ```typescript
   if (process.env.NODE_ENV === 'development' && stats.current.nActiveCubes > 0) {
     console.log(`[MC] seq=${compileSeq} iso=${isovalue.toFixed(4)} triangles=${result.indices.length / 3} activeCubes=${stats.current.nActiveCubes}`);
   }
   ```

3. **frameloop="demand"**：
   ```typescript
   <Canvas frameloop="demand">
   ```
   - 只在需要时渲染，而不是每帧都渲染

**关键 diff：**
- `gui/src/components/panels/VolumeViewerSandbox.tsx`:
  - `IsosurfaceMesh` 接收 `compileSeq` prop
  - `geometry` useMemo 中检查 `compileSeq`，避免重复计算
  - 减少 console.log 输出（仅 dev 模式，且有条件）
  - Canvas 使用 `frameloop="demand"`

### P4: 主题可读性

**直接证据（修复前）：**
- `.volume-viewer-debug` 使用 `rgba(255, 255, 255, 0.98)` 背景，但文字颜色不够深
- `.volume-viewer-sandbox-fixture-item.selected` 可能在某些主题下文字对比度不足

**修复方案：**
```css
/* P4: Debug panel - white background with dark text for readability */
.volume-viewer-debug {
  background: #ffffff;
  /* ... */
}

.volume-viewer-debug h4 {
  color: #1a1a1a;
  /* ... */
}

.debug-label {
  color: #333;
}

.debug-value {
  color: #000;
}

.volume-viewer-sandbox-fixture-item.selected {
  color: #000;
}

.volume-viewer-sandbox-fixture-item.selected .fixture-name {
  color: #000;
  font-weight: 600;
}

.volume-viewer-control-value {
  color: #1a1a1a;
  font-weight: 500;
}
```

**关键 diff：**
- `gui/src/components/panels/VolumeViewerSandbox.css`:
  - 统一使用白色背景 (#ffffff) 和深色文字 (#000, #1a1a1a, #333)
  - 确保所有文本在深色 canvas 背景下清晰可读

## 最小可复现步骤验证

### Phase0 不再出现
1. 启动 daemon + GUI
2. 打开 `/dev/volume-viewer`
3. 快速连续点击不同的 fixture（例如：gaas_00001.xsf → diamond_00001.xsf → gaas_00002.xsf）
4. **预期**：不再出现 `Phase0 validation failed` 错误
5. **验证**：Debug 面板中的 `Compile Key` 和 `Seq` 应该与当前显示的数据一致

### Band 切换确实改变 mesh
1. 打开 `lead.bxsf`
2. 记录 Debug 面板中的 `Triangles` 数量
3. 切换到 Band 2
4. **预期**：`Triangles` 数量应该变化（可能变为 0 或不同的值）
5. **验证**：Debug 面板中的 `Compile Key` 应该包含新的 band 编号

### Console 不再无操作刷屏
1. 打开任意 fixture
2. 等待 mesh 加载完成
3. 不要进行任何操作，等待 10 秒
4. **预期**：Console 中不应再出现持续的 mesh 计算日志
5. **验证**：只有在实际改变 iso 或切换 fixture/band/resolution 时才应该有新的日志

## 文件修改清单

1. `gui/src/components/panels/VolumeViewerSandbox.tsx` - 完全重构状态管理，引入原子状态和竞态保护
2. `gui/src/components/panels/VolumeViewerSandbox.css` - 修复主题可读性
3. `gui/src/utils/energyReference.ts` - 已存在，现在正确 import

