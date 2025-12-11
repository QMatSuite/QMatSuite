# Tutorial Examples 迁移说明

## 变更总结

### 删除
- ❌ `tests/examples/qe_tutorial_examples/` - 已删除，不再包含在仓库中

### 新增
- ✅ `temp/downloads/qe_tutorial_examples/` - 自动下载的教程示例
- ✅ `extended-tests/utils/download_tutorial_examples.py` - 自动下载脚本
- ✅ `extended-tests/suites/tutorial_examples/` - 教程示例测试套件

## 数据来源

所有教程示例来自：
**https://github.com/quantumNerd/Quantum-Espresso-Tutorial-2019-Projects**

## 自动下载

教程示例会在需要时自动下载到 `temp/downloads/qe_tutorial_examples/`。

### 手动下载

```bash
python3 extended-tests/utils/download_tutorial_examples.py
```

### 强制重新下载

```bash
python3 extended-tests/utils/download_tutorial_examples.py --force
```

## 临时文件夹结构

```
temp/
├── downloads/          # 下载的仓库和文件
│   └── qe_tutorial_examples/  # 教程示例
├── cache/             # 缓存文件
└── tmp/               # 临时文件
```

## Git 管理

- ✅ `temp/` 目录在 `.gitignore` 中（不跟踪下载的文件）
- ✅ 下载脚本和测试代码在仓库中
- ✅ 用户首次运行时会自动下载

## 优势

1. **减小仓库大小**: 不包含大型示例文件
2. **自动更新**: 可以随时重新下载最新版本
3. **一致性**: 所有用户使用相同的源
4. **可追溯**: 明确指向 GitHub 仓库

## 迁移步骤

1. ✅ 创建临时文件夹结构
2. ✅ 创建下载脚本
3. ✅ 创建测试套件
4. ⏳ 删除旧目录（用户确认后）
5. ⏳ 更新所有引用

