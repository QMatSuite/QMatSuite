# CI Test Data Distribution

## 概述

CI 测试数据文件已从 QE test-suite 复制到 `tests/data/`，确保：

1. **独立性**: 测试可以在没有 QE test-suite 的环境中运行
2. **一致性**: 所有用户使用相同的测试文件
3. **可分发**: 测试文件随软件一起分发

## 文件位置

```
tests/data/
├── manifest.json              # 元数据（测试列表）
├── README.md                  # 说明文档
├── pw_single_tests/          # 所有 PW 单步测试文件
│   ├── atom.in               # 输入文件
│   ├── metal.in
│   ├── metal-gaussian.in
│   ├── metal-fermi_dirac.in
│   ├── scf-mixing_localTF.in
│   ├── scf-cg.in
│   ├── plugin-pw2casino_2.in
│   ├── uspp-cg-gamma.in
│   └── benchmark files...   # 参考输出文件
├── ph_1d/                    # PH 测试
└── ph_2d/                    # PH 测试
```

## 包含的文件

- **10 个输入文件** (`.in`): 选定的 CI quick tests
- **7 个参考文件** (benchmark): 用于结果验证
- **1 个 manifest.json**: 测试元数据

**总大小**: ~136 KB

## Git 管理

这些文件**包含在 Git 仓库中**，确保：
- ✅ 所有用户使用相同的测试文件
- ✅ CI 可以独立运行（不依赖外部 test-suite）
- ✅ 测试结果一致

## 更新流程

当需要更新测试数据时：

```bash
# 1. 更新选定的测试（如果需要）
python3 extended-tests/scripts/run_pw_all_with_stats.py --nprocs 4

# 2. 复制新的测试文件
python3 tests/integration/scripts/copy_ci_test_files.py

# 3. 验证
python3 tests/integration/test_ci_validation.py
```

## 测试使用

测试代码会自动：
1. 首先查找 `tests/data/`（本地副本）
2. 如果不存在，回退到 QE test-suite 目录

这确保了：
- **CI 环境**: 使用本地副本（不依赖 test-suite）
- **本地开发**: 可以使用 test-suite（如果可用）

## 分发给客户

这些文件会随软件一起分发，客户可以：
- 运行 CI quick tests 而无需安装 QE test-suite
- 获得一致的测试结果
- 验证软件功能

## 文件来源

所有文件都从 QE 官方 test-suite 原样复制，保证：
- ✅ 与官方测试一致
- ✅ 可追溯性（manifest.json 记录来源）
- ✅ 完整性（包含输入和参考输出）

