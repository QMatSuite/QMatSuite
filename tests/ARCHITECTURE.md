# 测试框架架构

## 设计理念

采用**混合方案**：既保持代码组织（文件夹结构），又提供统一的接口（类继承）。

### 为什么选择这种方案？

1. **文件夹组织** - 按测试类型清晰分类，易于查找和维护
2. **类接口统一** - 所有测试类型实现相同接口，便于统一管理
3. **易于扩展** - 添加新测试类型只需创建新文件夹和类
4. **向后兼容** - 保留原有命令行脚本

## 目录结构

```
tests/
├── core/                          # 测试框架核心（抽象层）
│   ├── base.py                   # TestSuite, TestCase, TestResult 基类
│   └── runner.py                  # TestRunner 统一运行器
│
├── suites/                        # 测试套件（具体实现）
│   ├── qe_testsuite/            # QE官方测试套件
│   │   ├── suite.py             # QETestSuite 实现
│   │   └── cases.py             # QETestCase 实现
│   │
│   └── bidirectional/           # 双向转换测试（待实现）
│       └── suite.py             # BidirectionalTestSuite 实现
│
├── utils/                        # 工具函数（共享代码）
│   └── qe_module_base.py        # QE模块测试基础功能
│
└── run_*_tests.py               # 命令行脚本（向后兼容）
```

## 核心组件

### 1. TestResult (数据类)
```python
@dataclass
class TestResult:
    name: str
    status: TestStatus  # PASSED, FAILED, SKIPPED, ERROR
    message: str
    error: Optional[str]
    time_taken: float
    details: Dict[str, Any]
```

### 2. TestCase (抽象基类)
```python
class TestCase(ABC):
    def run(self) -> TestResult: ...
    def setup(self) -> None: ...
    def teardown(self) -> None: ...
```

### 3. TestSuite (抽象基类)
```python
class TestSuite(ABC):
    def discover_tests(self) -> List[TestCase]: ...
    def run_all(self) -> List[TestResult]: ...
    def get_summary(self) -> Dict[str, Any]: ...
```

### 4. TestRunner (统一运行器)
```python
class TestRunner:
    def register_suite(self, suite: TestSuite): ...
    def run_suite(self, name: str): ...
    def run_all(self): ...
    def export_results(self, path: Path): ...
```

## 使用方式

### 方式 1: 统一命令行入口（推荐）

```bash
# 列出所有测试套件
python3 tests/run_tests.py --list

# 运行特定套件
python3 tests/run_tests.py --suite qe-pw
python3 tests/run_tests.py --suite qe-ph --timeout 120

# 运行所有套件
python3 tests/run_tests.py --all

# 导出结果
python3 tests/run_tests.py --suite qe-pw --output results.json
```

### 方式 2: 编程接口

```python
from tests.core.runner import TestRunner
from tests.suites.qe_testsuite import QETestSuite

# 创建运行器
runner = TestRunner()

# 注册测试套件
suite = QETestSuite(
    test_suite_dir=Path("/path/to/test-suite"),
    qe_bin_dir=Path("/path/to/qe/bin"),
    module_prefix="pw_"
)
runner.register_suite(suite)

# 运行
runner.run_all()
runner.print_overall_summary()
```

### 方式 3: 直接使用套件

```python
from tests.suites.qe_testsuite import QETestSuite

suite = QETestSuite(...)
results = suite.run_all()
suite.print_summary()
```

### 方式 4: 原有命令行脚本（向后兼容）

```bash
# 仍然可以使用原有的脚本
python3 tests/run_pw_tests_official_style.py --category pw_atom
python3 tests/run_ph_tests.py
```

## 添加新测试类型

### 步骤 1: 创建套件目录
```bash
mkdir tests/suites/my_new_test
```

### 步骤 2: 实现 TestSuite 子类
```python
# tests/suites/my_new_test/suite.py
from tests.core.base import TestSuite, TestCase

class MyNewTestSuite(TestSuite):
    def discover_tests(self) -> List[TestCase]:
        # 发现测试用例的逻辑
        return [...]
```

### 步骤 3: 实现 TestCase 子类
```python
# tests/suites/my_new_test/cases.py
from tests.core.base import TestCase, TestResult, TestStatus

class MyNewTestCase(TestCase):
    def run(self) -> TestResult:
        # 执行测试的逻辑
        return TestResult(...)
```

### 步骤 4: 注册到运行器
```python
# tests/run_tests.py
from tests.suites.my_new_test import MyNewTestSuite

suites["my-new-test"] = MyNewTestSuite(...)
```

## 优势总结

### ✅ 统一管理
- 所有测试类型通过相同接口访问
- 统一的测试结果格式
- 统一的报告和导出

### ✅ 易于扩展
- 添加新测试类型只需实现接口
- 不需要修改核心框架
- 清晰的职责分离

### ✅ 代码组织
- 按类型分文件夹，结构清晰
- 共享工具函数统一管理
- 向后兼容原有脚本

### ✅ 灵活使用
- 可以单独运行某个套件
- 可以运行所有套件
- 可以编程方式集成

## 当前支持的测试类型

1. **QE Test Suite** - QE官方测试套件
   - pw, ph, pp, cp, hp, tddfpt, kcw, epw, zg, all_currents

2. **Bidirectional** - 双向转换测试（待实现）

3. **Future types** - 可以轻松添加：
   - Performance tests
   - Integration tests
   - Regression tests
   - Custom tests

## 迁移状态

- ✅ 核心框架已创建
- ✅ QE测试套件已实现
- ✅ 统一命令行入口已创建
- ⏳ 双向转换测试套件（待实现）
- ⏳ 文档完善（进行中）

