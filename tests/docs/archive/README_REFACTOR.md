# Test Framework Refactoring

## 新的测试框架结构

测试代码已重构为更可管理的结构，使用面向对象的设计和统一的接口。

## 目录结构

```
tests/
├── core/                    # 测试框架核心
│   ├── __init__.py
│   ├── base.py             # 基类：TestSuite, TestCase, TestResult
│   └── runner.py           # TestRunner：统一运行器
│
├── suites/                  # 测试套件（按类型组织）
│   ├── __init__.py
│   ├── qe_testsuite/       # QE官方测试套件
│   │   ├── __init__.py
│   │   ├── suite.py        # QETestSuite
│   │   └── cases.py        # QETestCase, QECategoryTestCase
│   │
│   └── bidirectional/      # 双向转换测试
│       ├── __init__.py
│       └── suite.py        # BidirectionalTestSuite (待实现)
│
├── utils/                   # 工具函数
│   ├── __init__.py
│   └── qe_module_base.py   # QE模块测试基础功能
│
└── run_*_tests.py          # 命令行脚本（向后兼容）
```

## 核心概念

### 1. TestResult
测试结果数据类，包含：
- `name`: 测试名称
- `status`: 状态 (PENDING, RUNNING, PASSED, FAILED, SKIPPED, ERROR)
- `message`: 消息
- `error`: 错误信息
- `time_taken`: 执行时间
- `details`: 详细信息字典

### 2. TestCase
单个测试用例的基类：
- `run()`: 执行测试
- `setup()`: 测试前准备
- `teardown()`: 测试后清理

### 3. TestSuite
测试套件的基类：
- `discover_tests()`: 发现测试用例
- `run_all()`: 运行所有测试
- `get_summary()`: 获取统计信息
- `print_summary()`: 打印摘要

### 4. TestRunner
统一测试运行器：
- `register_suite()`: 注册测试套件
- `run_suite()`: 运行指定套件
- `run_all()`: 运行所有套件
- `export_results()`: 导出结果

## 使用示例

### 创建 QE 测试套件

```python
from tests.suites.qe_testsuite import QETestSuite
from pathlib import Path

# 创建测试套件
suite = QETestSuite(
    test_suite_dir=Path("/path/to/qe/test-suite"),
    qe_bin_dir=Path("/path/to/qe/bin"),
    module_prefix="pw_",
    description="PW module tests"
)

# 运行所有测试
results = suite.run_all(timeout=60)

# 查看摘要
suite.print_summary()
```

### 使用 TestRunner

```python
from tests.core.runner import TestRunner
from tests.suites.qe_testsuite import QETestSuite

# 创建运行器
runner = TestRunner()

# 注册多个测试套件
runner.register_suite(QETestSuite(...))  # pw tests
runner.register_suite(QETestSuite(..., module_prefix="ph_"))  # ph tests
# runner.register_suite(BidirectionalTestSuite(...))  # bidirectional tests

# 运行所有套件
runner.run_all()

# 或运行特定套件
runner.run_suite("QE Test Suite (pw)")

# 导出结果
runner.export_results(Path("results.json"), format="json")
```

### 命令行使用

```python
# tests/run_tests.py (待创建)
from tests.core.runner import TestRunner
from tests.suites.qe_testsuite import QETestSuite

def main():
    parser = TestRunner.create_cli()
    args = parser.parse_args()
    
    runner = TestRunner()
    
    # 注册所有测试套件
    runner.register_suite(QETestSuite(...))
    # ... 其他套件
    
    if args.suite:
        runner.run_suite(args.suite, timeout=args.timeout)
    else:
        runner.run_all(timeout=args.timeout)
    
    runner.print_overall_summary()
    
    if args.output:
        runner.export_results(args.output, format=args.format)

if __name__ == "__main__":
    main()
```

## 优势

1. **统一接口**: 所有测试类型都实现相同的接口
2. **易于扩展**: 添加新测试类型只需创建新的 TestSuite 子类
3. **代码复用**: 共享的工具函数和基础类
4. **结果管理**: 统一的测试结果格式和导出
5. **向后兼容**: 保留原有的命令行脚本

## 迁移计划

1. ✅ 创建核心框架 (core/)
2. ✅ 创建 QE 测试套件 (suites/qe_testsuite/)
3. ✅ 移动工具函数到 utils/
4. ⏳ 创建双向转换测试套件 (suites/bidirectional/)
5. ⏳ 创建统一命令行入口 (run_tests.py)
6. ⏳ 更新文档

## 未来扩展

可以轻松添加新的测试类型：

- `suites/performance/` - 性能测试
- `suites/integration/` - 集成测试
- `suites/regression/` - 回归测试
- `suites/custom/` - 自定义测试

每个新类型只需：
1. 创建 TestSuite 子类
2. 实现 `discover_tests()` 方法
3. 创建相应的 TestCase 子类
4. 注册到 TestRunner

