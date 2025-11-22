# CI Quick Tests

## 测试结构

### 1. `test_pw_quick_tests.py`
- **用途**: 运行从 QE test-suite 选定的实际测试
- **要求**: 需要 QE 安装和 test-suite
- **标记**: `@pytest.mark.quick` + `@pytest.mark.requires_qe`
- **行为**: 如果 QE 不可用，测试会优雅地跳过

### 2. `test_pw_quick_tests_ci.py`
- **用途**: CI 友好的测试，不依赖 QE 安装
- **要求**: 仅需要 Python 和 quantumvitas 库
- **标记**: `@pytest.mark.quick`
- **行为**: 总是运行，测试解析和生成功能

## CI 行为

在 GitHub Actions 中：
- ✅ `test_pw_quick_tests_ci.py` 总是运行（不依赖 QE）
- ⏭️ `test_pw_quick_tests.py` 会跳过（QE 不可用）

在有 QE 的环境中：
- ✅ 两个测试文件都会运行
- ✅ `test_pw_quick_tests.py` 会运行实际的 QE 测试

## 运行测试

### 在 CI 中（无 QE）
```bash
pytest tests/ -m quick
# 只会运行 test_pw_quick_tests_ci.py
```

### 在本地（有 QE）
```bash
pytest tests/integration/test_pw_quick_tests.py -v
# 运行选定的 QE 测试
```

### 仅运行 CI 友好测试
```bash
pytest tests/integration/test_pw_quick_tests_ci.py -v
# 总是运行，不依赖 QE
```

## 测试数据

选定的 QE 测试从 `extended-tests/pw_test_stats.json` 加载。
如果文件不存在或无法加载，测试会跳过。

## 环境变量

- `QE_BIN_DIR`: QE bin 目录路径（可选）
- 如果未设置，会尝试默认位置 `$HOME/src/q-e-qe-7.5/bin`
- 如果都找不到，测试会跳过

