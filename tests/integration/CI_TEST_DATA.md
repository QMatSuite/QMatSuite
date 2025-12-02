# CI Test Data

## 概述

CI 测试数据存储在 `tests/data/` 目录中，包含：
- QE 输入文件（`.in`）
- 参考输出文件（benchmark files，如果有）
- 元数据文件（`manifest.json`）

## 目的

1. **独立性**: 测试可以在没有 QE test-suite 的环境中运行
2. **一致性**: 确保所有用户使用相同的测试文件
3. **可分发**: 测试文件随软件一起分发，保证一致性

## 文件结构

```
tests/data/
├── manifest.json              # 元数据
├── pw_single_tests/          # 所有 PW 单步测试文件
│   ├── atom.in
│   ├── metal.in
│   ├── metal-gaussian.in
│   ├── metal-fermi_dirac.in
│   ├── scf-mixing_localTF.in
│   ├── scf-cg.in
│   ├── plugin-pw2casino_2.in
│   ├── uspp-cg-gamma.in
│   └── benchmark files...
├── ph_1d/                    # PH 测试
└── ph_2d/                    # PH 测试
```

## 更新流程

当需要更新测试数据时：

1. 运行统计收集（如果需要更新选定的测试）:
   ```bash
   python3 extended-tests/scripts/run_pw_all_with_stats.py --nprocs 4
   ```

2. 复制测试文件:
   ```bash
   python3 tests/integration/scripts/copy_ci_test_files.py
   ```

3. 验证文件:
   ```bash
   python3 tests/integration/test_ci_validation.py
   ```

## 测试使用

测试代码会自动：
1. 首先查找 `tests/data/`（本地副本）
2. 如果不存在，回退到 QE test-suite 目录

这确保了：
- CI 环境可以使用本地副本（不依赖 test-suite）
- 本地开发可以使用 test-suite（如果可用）

## Git 管理

这些文件应该**包含在 Git 仓库中**，以便：
- 所有用户使用相同的测试文件
- CI 可以独立运行
- 保证测试结果的一致性

## 文件大小

测试文件通常很小（几 KB），不会显著增加仓库大小。

