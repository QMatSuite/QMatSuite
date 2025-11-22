# QE Module Tests Debug Summary

## 测试结果

- **总模块数**: 10
- **通过**: 2 (cp, xsd_pw)
- **失败**: 8
- **总时间**: 60.3 秒

## 失败原因分析

### 1. 缺失的可执行文件

以下模块因为缺少可执行文件而失败：

- **ph**: 缺少 `ph.x`
- **hp**: 缺少 `hp.x`
- **zg**: 缺少 `ZG.x`
- **all_currents**: 缺少 `all_currents.x`
- **kcw**: 缺少 `kcw.x`
- **epw**: 缺少 `epw.x` 和 `ph.x`
- **tddfpt**: 缺少 `turbo_lanczos.x`, `turbo_spectrum.x`, `turbo_eels.x`

### 2. 伪势文件问题

- **pp**: 伪势文件 `C_ONCV_PBE-1.0.upf` 下载失败 (404 错误)

### 3. 执行错误

- **pp**: `ppacf_fock.in` 测试失败 (`pp.x returned 1`)
- **kcw**: `pw.x` 执行失败
- **epw**: `pw.x` 执行失败

## 解决方案

### 方案 1: 安装缺失的 QE 模块

某些模块可能需要在编译 QE 时启用特定选项：

```bash
# 检查 QE 编译配置
cd <HOME>/src/q-e-qe-7.5
cat make.inc | grep -i "enable\|with"
```

可能需要重新编译 QE 并启用：
- `--enable-phonon` (ph.x)
- `--enable-hp` (hp.x)
- `--enable-epw` (epw.x)
- `--enable-tddfpt` (turbo_*)
- `--enable-kcw` (kcw.x)

### 方案 2: 跳过缺失模块的测试

修改测试脚本，如果可执行文件不存在则跳过测试而不是失败。

### 方案 3: 修复伪势下载

检查伪势文件 URL 或使用本地伪势文件。

## 当前可运行的模块

✅ **cp**: 所有可执行文件存在
✅ **xsd_pw**: 不需要可执行文件（XML 验证）

## 部分可运行的模块

⚠️ **pp**: `pp.x` 存在，但测试中有失败
⚠️ **tddfpt**: `pw.x` 存在，但缺少 `turbo_*` 可执行文件

## 建议

1. 首先检查 QE 安装配置，确认哪些模块已编译
2. 对于缺失的模块，要么重新编译 QE，要么跳过这些测试
3. 修复伪势文件下载问题
4. 调试 `pw.x` 执行失败的原因（可能是 MPI 或环境配置问题）

