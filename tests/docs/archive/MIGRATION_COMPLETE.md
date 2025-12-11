# 测试迁移完成

## ✅ 迁移总结

所有依赖 QE test-suite 的测试文件已成功迁移到 `extended-tests/`。

### 迁移的文件

#### 测试套件
- `tests/test_bidirectional_conversion.py` → `extended-tests/suites/bidirectional/`
- `tests/test_official_testsuite.py` → `extended-tests/`

#### 工具函数
- `tests/test_qe_roundtrip_execution.py` → `extended-tests/utils/`
- `tests/utils/qe_module_base.py` → `extended-tests/utils/` (之前已移动)

#### 测试脚本
- `tests/run_*_tests.py` (所有模块测试脚本) → `extended-tests/scripts/`
- `tests/run_tests.py` → `extended-tests/scripts/`
- `tests/run_first_10_pw_categories.py` → `extended-tests/scripts/`
- `tests/run_multiple_pw_tests.py` → `extended-tests/scripts/`
- `tests/run_pw_tests_official_style.py` → `extended-tests/scripts/`

### Quick Tests 保留

`tests/` 目录中保留的文件（不依赖 test-suite）：
- `tests/unit/` - 单元测试（3 个文件）
- `tests/integration/` - 集成测试（2 个文件）
- `tests/core/` - 测试框架核心（2 个文件）
- `tests/conftest.py` - Pytest 配置

### 目录结构

```
.
├── tests/                    # Quick tests (CI)
│   ├── unit/               # 单元测试
│   ├── integration/        # 集成测试
│   ├── core/               # 测试框架核心
│   └── conftest.py         # Pytest 配置
│
├── extended-tests/         # Extended tests (developer)
│   ├── suites/            # 测试套件
│   │   ├── bidirectional/ # 双向转换测试
│   │   └── qe_testsuite/ # QE 官方测试套件
│   ├── utils/            # 工具函数
│   ├── scripts/          # 测试脚本
│   ├── conftest.py       # Pytest 配置
│   ├── run_all.py        # 统一运行器
│   └── analyze_results.py # 结果分析
```

## 验证

✅ 所有依赖 test-suite 的文件已移动到 `extended-tests/`
✅ `tests/` 中不再有 test-suite 代码依赖
✅ 导入路径已更新
✅ 文档已更新

## 使用

### Quick Tests (CI)
```bash
pytest tests/ -m quick
```

### Extended Tests (Developer)
```bash
# 统一运行器
python3 extended-tests/run_all.py --all

# 或使用脚本
python3 extended-tests/scripts/run_pw_tests_official_style.py --category pw_atom
```

