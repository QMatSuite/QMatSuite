# QE Tutorial Examples Test Suite

## 数据来源

所有教程示例来自：
**https://github.com/quantumNerd/Quantum-Espresso-Tutorial-2019-Projects**

这是 QuantumNerd YouTube 频道的 Quantum ESPRESSO 教程项目。

## 自动下载

教程示例会在需要时自动下载到 `temp/downloads/qe_tutorial_examples/`。

### 下载机制

1. 测试运行时检查 `temp/downloads/qe_tutorial_examples/` 是否存在
2. 如果不存在，自动调用下载脚本
3. 使用 git clone 或 zip 下载（如果 git 不可用）

### 手动下载

```bash
# 下载到默认位置
python3 extended-tests/utils/download_tutorial_examples.py

# 指定输出目录
python3 extended-tests/utils/download_tutorial_examples.py --output-dir /path/to/output

# 强制重新下载
python3 extended-tests/utils/download_tutorial_examples.py --force
```

## 测试结构

测试套件会自动发现所有 `.in` 文件并创建测试用例。

### 测试类型

- **解析测试**: 验证输入文件可以正确解析
- **生成测试**: 验证可以生成有效的输入文件
- **执行测试**: 运行 QE 并验证输出（需要 QE 安装）

## 文件位置

- **下载位置**: `temp/downloads/qe_tutorial_examples/`
- **Git 状态**: `temp/` 目录在 `.gitignore` 中（不跟踪）
- **源仓库**: https://github.com/quantumNerd/Quantum-Espresso-Tutorial-2019-Projects

## 优势

1. ✅ **减小仓库大小**: 不包含大型示例文件
2. ✅ **自动更新**: 可以随时重新下载最新版本
3. ✅ **一致性**: 所有用户使用相同的源
4. ✅ **可追溯**: 明确指向 GitHub 仓库

## 迁移说明

旧的 `tests/examples/qe_tutorial_examples/` 目录已删除。
所有引用已更新为使用自动下载的版本。
